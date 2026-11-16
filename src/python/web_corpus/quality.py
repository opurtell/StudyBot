"""Score the web question bank for quality with a local LM Studio model, and retire the weak questions.

The model only scores: relevance, how many things a question asks, whether a scenario matters, whether it stands
alone, whether the source answers it, and a trivia label. Every decision is made here in code, from those scores,
so thresholds can change without re-running the model. Nothing is deleted: the SQL sets status 'retired' with
status_reason 'quality_review', and wording fixes are fixed word swaps done by script.

Run from the repo root, with the LM Studio server running:

    cd web && CLOUDFLARE_ENV=production npx wrangler d1 execute DB --remote --json --command \\
      "SELECT q.id, q.document_id, d.title AS document, q.chunk_id, q.question_type, q.difficulty, q.question_text, \\
       q.content_hash, q.source_text FROM question_bank q JOIN corpus_documents d ON d.id = q.document_id \\
       WHERE q.status = 'active'" > corpus-build/quality/questions.json
    PYTHONPATH=src/python python3 -m web_corpus.quality score [--labels LABELS.csv] [--limit N]
    PYTHONPATH=src/python python3 -m web_corpus.quality calibrate --labels LABELS.csv [--split tune|holdout|all]
    PYTHONPATH=src/python python3 -m web_corpus.quality export [--rescue review.csv]

``score`` appends to ``scores.jsonl`` and skips questions already scored with the same prompt and model, so it can
be stopped and resumed. ``export`` writes ``review.csv`` (every retirement and fix, plus a sample of keeps) and,
unless a source would lose more than MAX_SOURCE_SHARE of its questions, ``quality.sql``. Mark rows to keep with
"Y" in the ``rescue`` column and pass the file back with ``--rescue`` to produce the final SQL.

Undo every retirement with:
    UPDATE question_bank SET status = 'active', status_reason = NULL WHERE status_reason = 'quality_review';
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from paths import APP_ROOT
from web_corpus.questions import content_hash, normalise, parse_json_object

OUT_DIR = APP_ROOT / "web" / "corpus-build" / "quality"
DEFAULT_MODEL = "qwen/qwen3.8-27b"
MAX_SOURCE_SHARE = 0.35
KEEP_SAMPLE = 50
DUPLICATE_SIMILARITY = 0.6

MIN_RELEVANCE = 3
MAX_ASKS = 3
TRIVIA_RELEVANCE_LIMIT = 3

TRIVIA = ["none", "device", "administration", "vocabulary", "genetics_histology", "statistics", "hospital_only",
          "not_australian"]

CAPS: list[tuple[str, int, tuple[str, ...]]] = [
    ("Corpuls cpr", 6, ("CMG_CSM.C07_",)),
    ("HEMCO Patient Restraint", 6, ("CMG_CSM.M04_",)),
    ("Securing Baby Capsule", 6, ("CMG_CSM.M09_",)),
    ("Skills Matrix", 6, ("CMG_CSM.M07_",)),
    ("Stretcher positioning skills", 6, ("CMG_CSM.P0",)),
    ("Palliative Care and VAD", 20, ("CMG_45_",)),
]

SYSTEM = """You review questions in a study app for Australian ambulance paramedics. You score one question against
its source text. You never rewrite the question.

Many questions in this bank were generated from textbooks and equipment manuals, and a large share are weak. Your job is
to find them. A question being accurate and answerable does not make it good. Equally, do not mark down core
clinical knowledge: the labels below are for the narrow kinds of trivia they describe, and most clinical questions
are "none".
Judge what the student is asked to recall, not the topic it sits under. A question in a cardiac or resuscitation
guideline can still be trivia.

Work in this order.

1. trivia: decide first what kind of fact the answer is. Pick the first label that fits, or "none" only if none fits:
  genetics_histology = the answer is a gene, mutation or inheritance pattern, or a change that can only be seen
    under a microscope (fibrosis, sclerosis, infiltration or degeneration of a named microscopic structure).
    Mechanisms of disease, sequences such as ischaemia leading to necrosis, gross pathology, anatomy and physiology
    (which muscles, hormones, receptors or organs are involved) are "none"
  hospital_only = the answer is a laboratory value or blood test result (blood count indices, serum levels), a
    hospital investigation, or a complication of hospital care (prolonged infusions, ward procedures, bedside
    measurement techniques a paramedic does not use)
  not_australian = the question names a drug that is withdrawn, no longer marketed, or not used in Australia, or
    uses a US drug name or US term where Australia uses another (acetaminophen, epinephrine, albuterol, complete
    blood count)
  statistics = the answer is a percentage, proportion, prevalence, incidence or demographic figure describing a
    population. A clinical threshold or criterion that changes management is not statistics
  vocabulary = the question asks what a word, prefix or acronym means, or for another name of a condition. The
    expansion of a clinical assessment tool used on scene (a stroke or trauma mnemonic), and a diagnostic
    threshold, ECG criterion or the definition of an ECG rhythm or measurement, are not vocabulary
  device = the answer is about the machine or equipment itself: how to mount, attach, release, unlock, secure, store,
    check, clean, label or carry it, its controls, or a tolerance or limit of the equipment. A device question stays
    device even when it is wrapped in a patient case. Test: if the answer depends on the patient (their size, age,
    condition or rhythm), it is not device. Choosing what to give the patient is "none": a drug or oxygen dose,
    volume or flow rate, an airway or cannula size for a patient, where to place ECG electrodes, which ECG leads
    show a finding, or a step performed on the patient's body
  administration = documentation, forms, stamps, reporting, rosters, policy logistics
  none = a clinical fact: assessment, recognition, a drug's dose, indication or contraindication, a management step,
    or pathophysiology that explains what a paramedic sees in a patient

2. relevance (1 to 5): would a working paramedic need this from memory on scene, or does it explain something they
will see in patients?
  5 = core prehospital knowledge (doses, indications, recognising a life threat, key management steps, choosing an
    airway, cannula or oxygen flow for a patient)
  4 = useful clinical knowledge, ECG interpretation, or pathophysiology that explains what a paramedic sees
  3 = background knowledge, rarely needed but reasonable to know
  2 = trivia, a detail a paramedic would look up rather than recall, or a question so obvious that anyone without
    training could answer it
  1 = irrelevant to a paramedic: genes, histology, laboratory tests, hospital-only care, drugs not used in Australia
  A question that restates its own premise as the answer (asks for symptoms the question already names, or where
  something occurs when the question already says where) is 2.

3. asks: how many separate things must the student answer? Count each distinct item asked for ("state X, outline Y
and explain Z" is 3). Parts of one idea ("the dose and route", "your management of this patient") count as 1.

4. scenario: true if the question opens with a patient case (age, vitals, presentation).

5. scenario_needed: for a scenario, true if the patient details change the answer. false if the case is decoration
and the answer would be the same without it (the answer is the same table, list or device step for any patient).
For a non-scenario, true.

6. list_recital: true if the answer is mainly a list copied from the page (steps, criteria, contents of a table).

7. stands_alone: false if the question refers to something the student cannot see ("Example 3", "the figure", "the
provided text", "this ECG"), or if the question gives away its own answer. Naming a guideline ("according to the
ACTAS ... guideline") is fine: the student is expected to know the guidelines.

8. answerable: true if the source text states the answer.

9. reason: one short sentence a reviewer can read, naming the main weakness (or "No issues").

Respond with valid JSON only, in this key order:
{"trivia": "none", "relevance": 4, "asks": 1, "scenario": false, "scenario_needed": true, "list_recital": false,
 "stands_alone": true, "answerable": true, "reason": "No issues"}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "relevance": {"type": "integer", "minimum": 1, "maximum": 5},
        "asks": {"type": "integer", "minimum": 1},
        "scenario": {"type": "boolean"},
        "scenario_needed": {"type": "boolean"},
        "list_recital": {"type": "boolean"},
        "stands_alone": {"type": "boolean"},
        "answerable": {"type": "boolean"},
        "trivia": {"type": "string", "enum": TRIVIA},
        "reason": {"type": "string"},
    },
    "required": ["relevance", "asks", "scenario", "scenario_needed", "list_recital", "stands_alone", "answerable",
                 "trivia", "reason"],
}

SOURCES = [("CMG_CSM.", "csm"), ("ACTAS_", "csm"), ("CMG_", "cmg"), ("MED_", "med"), ("LITFL_", "LITFL"),
           ("OPENRN_", "Open RN"), ("STATPEARLS_", "StatPearls")]

EXAMPLE_REF = re.compile(r"\bExample\s+\d+\b")

_WORD_SWAPS = [
    ("norepinephrine", "noradrenaline"),
    ("epinephrine", "adrenaline"),
    ("acetaminophen", "paracetamol"),
    ("albuterol", "salbutamol"),
    ("meperidine", "pethidine"),
    ("complete blood count", "full blood count"),
    ("labored", "laboured"),
    ("labor", "labour"),
    ("color", "colour"),
    ("colors", "colours"),
    ("behavior", "behaviour"),
    ("behaviors", "behaviours"),
    ("behavioral", "behavioural"),
    ("tumor", "tumour"),
    ("tumors", "tumours"),
    ("fiber", "fibre"),
    ("fibers", "fibres"),
    ("liter", "litre"),
    ("liters", "litres"),
    ("milliliter", "millilitre"),
    ("milliliters", "millilitres"),
    ("center", "centre"),
    ("centered", "centred"),
    ("centers", "centres"),
    ("feces", "faeces"),
    ("fecal", "faecal"),
    ("heme", "haem"),
]

_PATTERN_SWAPS = [
    (r"(?<![a-z])(peri|)hem(?=o|at)", r"\1haem"),
    (r"(?<![a-z])(\w*?)(isch|an|glyc|kal|natr|calc|magnes|phosphat|ox|ur|bacter|vir|septic|lipid|leuk|acid|alkal|vol)"
     r"em(ia|ias|ic)\b", r"\1\2aem\3"),
    (r"\b(\w*?)(?<!o)edema", r"\1oedema"),
    (r"(?<![a-z])esophag", "oesophag"),
    (r"(?<![a-z])diarrhea", "diarrhoea"),
    (r"(?<![a-z])(\w*?)pne(a|ic)\b", r"\1pnoe\2"),
    (r"(?<![a-z])pediatric", "paediatric"),
    (r"(?<![a-z])orthopedic", "orthopaedic"),
    (r"(?<![a-z])(\w*?)anesthe", r"\1anaesthe"),
    (r"(?<![a-z])estrogen", "oestrogen"),
]

_IZE = re.compile(r"\b([A-Za-z]{3,}?)iz(e|es|ed|ing|ation|ations|er|ers)\b")
_IZE_KEEP = {"caps", "res", "overs", "unders", "downs", "seiz", "pr", "ma", "bl"}

Complete = Callable[[str, str], str]


def source_of(document_id: str) -> str:
    for prefix, name in SOURCES:
        if document_id.startswith(prefix):
            return name
    return "other"


def cap_of(document_id: str) -> tuple[str, int] | None:
    for name, limit, prefixes in CAPS:
        if document_id.startswith(prefixes):
            return name, limit
    return None


def _match_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def australianise(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    def swap(pattern: str, repl: str | Callable[[re.Match], str]) -> None:
        nonlocal text

        def sub(m: re.Match) -> str:
            new = m.expand(repl) if isinstance(repl, str) else repl(m)
            new = _match_case(m.group(0), new)
            if new != m.group(0):
                changes.append(f"{m.group(0)} -> {new}")
            return new

        text = re.sub(pattern, sub, text, flags=re.IGNORECASE)

    for us, au in _WORD_SWAPS:
        swap(rf"\b{re.escape(us)}\b", au)
    for pattern, repl in _PATTERN_SWAPS:
        swap(pattern, repl)

    def ize(m: re.Match) -> str:
        if m.group(1).lower() in _IZE_KEEP:
            return m.group(0)
        return f"{m.group(1)}is{m.group(2)}"

    swap(_IZE.pattern, ize)
    return text, changes


_OPENER = re.compile(r"^(according to|under|based on|in accordance with)[^,]*,\s*", re.IGNORECASE)
_STOP = set("a an the of in on to for and or with what which is are be by as at from that this how when why "
            "does do should must according actas guideline skill medicine cmg csm med".split())


def _tokens(question: str) -> set[str]:
    return {w for w in normalise(_OPENER.sub("", question)).split() if w not in _STOP and len(w) > 1}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def duplicate_pairs(questions: list[dict], threshold: float = DUPLICATE_SIMILARITY) -> list[tuple[str, str, float]]:
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        by_doc[q["document_id"]].append(q)
    pairs = []
    for group in by_doc.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                s = similarity(a["question_text"], b["question_text"])
                if s >= threshold:
                    pairs.append((a["id"], b["id"], round(s, 2)))
    return pairs


def prompt_version(model: str) -> str:
    return hashlib.sha256((SYSTEM + model).encode("utf-8")).hexdigest()[:12]


def user_prompt(question: dict) -> str:
    kind = "ACTAS clinical guideline" if source_of(question["document_id"]) in {"cmg", "csm", "med"} else \
        "general reference (pathophysiology or ECG)"
    return (f"Source document: {question.get('document', '')} ({kind})\n\n"
            f"Question: {question['question_text']}\n\nSource text:\n{question['source_text']}")


def parse_scores(reply: str) -> dict | None:
    parsed = parse_json_object(reply)
    if parsed is None:
        return None
    try:
        relevance = int(parsed["relevance"])
        asks = int(parsed["asks"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 1 <= relevance <= 5 or asks < 1:
        return None

    def flag(name: str, default: bool) -> bool:
        value = parsed.get(name, default)
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1"}
        return bool(value)

    trivia = str(parsed.get("trivia", "none")).strip().lower().replace(" ", "_")
    return {
        "relevance": relevance,
        "asks": asks,
        "scenario": flag("scenario", False),
        "scenario_needed": flag("scenario_needed", True),
        "list_recital": flag("list_recital", False),
        "stands_alone": flag("stands_alone", True),
        "answerable": flag("answerable", True),
        "trivia": trivia if trivia in TRIVIA else "none",
        "reason": str(parsed.get("reason", "")).strip()[:300],
    }


def score_one(complete: Complete, question: dict, version: str) -> dict:
    scores = parse_scores(complete(SYSTEM, user_prompt(question)))
    record = {"id": question["id"], "version": version}
    if scores is None:
        record["status"] = "unreadable"
    else:
        record.update(status="ok", **scores)
    return record


def rubric_reasons(record: dict) -> list[str]:
    reasons = []
    if record["relevance"] < MIN_RELEVANCE:
        reasons.append(f"low relevance ({record['relevance']}/5)")
    if record["asks"] > MAX_ASKS:
        reasons.append(f"{record['asks']} separate asks")
    if not record["stands_alone"]:
        reasons.append("does not stand alone")
    if not record["answerable"]:
        reasons.append("source does not state the answer")
    if record["trivia"] != "none" and record["relevance"] <= TRIVIA_RELEVANCE_LIMIT:
        reasons.append(f"trivia: {record['trivia'].replace('_', ' ')}")
    return reasons


def rank_score(record: dict | None) -> float:
    if not record or record.get("status") != "ok":
        return 0.0
    score = record["relevance"] * 2.0
    score -= max(0, record["asks"] - 1) * 0.5
    score -= 1.0 if record["trivia"] != "none" else 0.0
    score -= 1.0 if record["scenario"] and not record["scenario_needed"] else 0.0
    score -= 0.5 if record["list_recital"] else 0.0
    return score


def decide(questions: list[dict], records: dict[str, dict]) -> dict[str, dict]:
    decisions: dict[str, dict] = {}
    for q in questions:
        reasons = []
        if EXAMPLE_REF.search(q["question_text"]):
            reasons.append("refers to an unseen example")
        record = records.get(q["id"])
        if record and record.get("status") == "ok":
            reasons.extend(rubric_reasons(record))
        decisions[q["id"]] = {"retire": bool(reasons), "reasons": reasons, "score": rank_score(record)}

    for a, b, sim in duplicate_pairs(questions):
        if decisions[a]["retire"] or decisions[b]["retire"]:
            continue
        loser, winner = (b, a) if decisions[a]["score"] >= decisions[b]["score"] else (a, b)
        decisions[loser]["retire"] = True
        decisions[loser]["reasons"].append(f"near duplicate of {winner} ({sim:.0%} overlap)")

    groups: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        cap = cap_of(q["document_id"])
        if cap and not decisions[q["id"]]["retire"]:
            groups[cap[0]].append(q)
    limits = {name: limit for name, limit, _ in CAPS}
    for name, members in groups.items():
        members.sort(key=lambda q: (-decisions[q["id"]]["score"], q["id"]))
        for q in members[limits[name]:]:
            decisions[q["id"]]["retire"] = True
            decisions[q["id"]]["reasons"].append(f"over the cap of {limits[name]} for {name}")
    return decisions


def plan_fixes(questions: list[dict], decisions: dict[str, dict]) -> dict[str, dict]:
    taken = {q.get("content_hash") for q in questions}
    fixes = {}
    for q in questions:
        if decisions[q["id"]]["retire"]:
            continue
        new, changes = australianise(q["question_text"])
        if not changes:
            continue
        h = content_hash(new)
        if h != q.get("content_hash") and h in taken:
            continue
        taken.add(h)
        fixes[q["id"]] = {"text": new, "hash": h, "changes": changes}
    return fixes


def source_shares(questions: list[dict], decisions: dict[str, dict]) -> dict[str, dict]:
    totals: Counter = Counter()
    retired: Counter = Counter()
    for q in questions:
        s = source_of(q["document_id"])
        totals[s] += 1
        retired[s] += decisions[q["id"]]["retire"]
    return {s: {"active": totals[s], "retire": retired[s], "share": round(retired[s] / totals[s], 3)} for s in totals}


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def to_sql(questions: list[dict], decisions: dict[str, dict], fixes: dict[str, dict], now_ms: int) -> str:
    lines = []
    for q in questions:
        if decisions[q["id"]]["retire"]:
            lines.append(f"UPDATE question_bank SET status = 'retired', status_reason = 'quality_review', "
                         f"updated_at = {now_ms} WHERE id = {_sql(q['id'])} AND status = 'active';")
    for q in questions:
        fix = fixes.get(q["id"])
        if fix:
            lines.append(f"UPDATE question_bank SET question_text = {_sql(fix['text'])}, content_hash = "
                         f"{_sql(fix['hash'])}, updated_at = {now_ms} WHERE id = {_sql(q['id'])} AND question_text = "
                         f"{_sql(q['question_text'])};")
    return "\n".join(lines) + ("\n" if lines else "")


REVIEW_HEADER = ["id", "action", "source", "document", "type", "difficulty", "reasons", "model_reason", "relevance",
                 "trivia", "question", "fixed_question", "rescue", "notes"]


def write_review(path: Path, questions: list[dict], decisions: dict[str, dict], fixes: dict[str, dict],
                 records: dict[str, dict], sample: int = KEEP_SAMPLE, seed: int = 20261117) -> None:
    keeps = [q for q in questions if not decisions[q["id"]]["retire"] and q["id"] not in fixes]
    sampled = {q["id"] for q in random.Random(seed).sample(keeps, min(sample, len(keeps)))}
    rows = []
    for q in questions:
        d = decisions[q["id"]]
        if d["retire"]:
            action = "retire"
        elif q["id"] in fixes:
            action = "fix wording"
        elif q["id"] in sampled:
            action = "keep (sample)"
        else:
            continue
        r = records.get(q["id"]) or {}
        rows.append([q["id"], action, source_of(q["document_id"]), q.get("document", ""), q.get("question_type", ""),
                     q.get("difficulty", ""), "; ".join(d["reasons"] or fixes.get(q["id"], {}).get("changes", [])),
                     r.get("reason", ""), r.get("relevance", ""), r.get("trivia", ""), q["question_text"],
                     fixes.get(q["id"], {}).get("text", ""), "", ""])
    order = {"retire": 0, "fix wording": 1, "keep (sample)": 2}
    rows.sort(key=lambda row: (order[row[1]], row[2], row[3], row[0]))
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(REVIEW_HEADER)
        writer.writerows(rows)


def read_rescues(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["id"] for row in csv.DictReader(fh) if row.get("rescue", "").strip().lower() in {"y", "yes", "x"}}


def load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in data if isinstance(data, list) else [data]:
        if isinstance(item, dict) and isinstance(item.get("results"), list):
            rows.extend(item["results"])
        elif isinstance(item, dict) and "id" in item:
            rows.append(item)
    return [r for r in rows if r.get("id") and r.get("question_text") and r.get("source_text") and r.get("document_id")]


def load_records(path: Path, version: str | None = None) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("id") and (version is None or record.get("version") == version):
                records[record["id"]] = record
    return records


def load_labels(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def splits(labels: dict[str, dict]) -> dict[str, str]:
    by_label: dict[str, list[str]] = defaultdict(list)
    for qid, row in labels.items():
        by_label[row["label"]].append(qid)
    result = {}
    for ids in by_label.values():
        ids.sort(key=lambda qid: hashlib.sha256(qid.encode()).hexdigest())
        for i, qid in enumerate(ids):
            result[qid] = "holdout" if i % 3 == 0 else "tune"
    return result


def calibration(labels: dict[str, dict], records: dict[str, dict], questions: dict[str, dict],
                split: str = "tune") -> dict:
    split_by_id = splits(labels)
    rows = []
    for qid, label in labels.items():
        if split != "all" and split_by_id[qid] != split:
            continue
        record = records.get(qid)
        if not record or record.get("status") != "ok":
            continue
        reasons = rubric_reasons(record)
        if qid in questions and EXAMPLE_REF.search(questions[qid]["question_text"]):
            reasons.insert(0, "refers to an unseen example")
        rows.append({"id": qid, "label": label["label"], "flagged": bool(reasons), "reasons": reasons,
                     "model_reason": record.get("reason", ""), "note": label.get("reason", ""),
                     "question": label.get("question", "")})
    by_label: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_label[row["label"]].append(row)

    def rate(label: str) -> float | None:
        group = by_label.get(label, [])
        return round(sum(r["flagged"] for r in group) / len(group), 3) if group else None

    return {
        "split": split,
        "scored": len(rows),
        "missing": sum(1 for qid in labels if (split == "all" or split_by_id[qid] == split) and qid not in records),
        "weak_caught": rate("weak"),
        "acceptable_flagged": rate("acceptable"),
        "strong_flagged": rate("strong"),
        "counts": {k: len(v) for k, v in by_label.items()},
        "missed_weak": [r for r in by_label.get("weak", []) if not r["flagged"]],
        "flagged_strong": [r for r in by_label.get("strong", []) if r["flagged"]],
    }


def local_complete(model: str, base_url: str = "") -> Complete:
    from llm.lmstudio_provider import LMStudioProvider

    provider = LMStudioProvider(default_model=model, base_url=base_url)
    return lambda system, user: provider.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}], response_schema=SCHEMA
    )


def run_score(questions: list[dict], out: Path, complete: Complete, version: str, limit: int | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "scores.jsonl"
    done = load_records(path, version)
    todo = [q for q in questions if q["id"] not in done or done[q["id"]]["status"] == "unreadable"]
    if limit is not None:
        todo = todo[:limit]
    counts: dict[str, int] = {}
    started = time.monotonic()
    with path.open("a", encoding="utf-8") as fh:
        for i, question in enumerate(todo, 1):
            try:
                record = score_one(complete, question, version)
            except Exception as exc:
                print(f"Stopped at {question['id']}: {exc}", file=sys.stderr)
                break
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            counts[record["status"]] = counts.get(record["status"], 0) + 1
            if i % 25 == 0 or i == len(todo):
                rate = (time.monotonic() - started) / i
                print(f"{i}/{len(todo)} done, {rate:.1f} s each, ~{rate * (len(todo) - i) / 60:.0f} min left, {counts}")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["score", "calibrate", "export"])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--questions", type=Path, default=None, help="wrangler --json export (default: OUT/questions.json)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--lmstudio-url", default="")
    parser.add_argument("--limit", type=int, default=None, help="only the next N questions (for a trial run)")
    parser.add_argument("--labels", type=Path, default=None, help="rated sample CSV (id,label,...)")
    parser.add_argument("--split", choices=["tune", "holdout", "all"], default="tune")
    parser.add_argument("--rescue", type=Path, default=None, help="reviewed review.csv; rows with rescue=Y are kept")
    parser.add_argument("--now-ms", type=int, default=None)
    args = parser.parse_args(argv)

    questions = load_questions(args.questions or args.out / "questions.json")
    version = prompt_version(args.model)
    records = load_records(args.out / "scores.jsonl", version)

    if args.command == "score":
        todo = questions
        if args.labels:
            ids = set(load_labels(args.labels))
            todo = [q for q in questions if q["id"] in ids]
        counts = run_score(todo, args.out, local_complete(args.model, args.lmstudio_url), version, args.limit)
        print(json.dumps(counts))
        return 0

    if args.command == "calibrate":
        if not args.labels:
            parser.error("calibrate needs --labels")
        result = calibration(load_labels(args.labels), records, {q["id"]: q for q in questions}, args.split)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    missing = [q["id"] for q in questions if q["id"] not in records]
    decisions = decide(questions, records)
    rescued = read_rescues(args.rescue) if args.rescue else set()
    rescued_retirements = {qid for qid in rescued if qid in decisions and decisions[qid]["retire"]}
    for qid in rescued_retirements:
        decisions[qid] = {"retire": False, "reasons": [], "score": decisions[qid]["score"]}
    fixes = {qid: fix for qid, fix in plan_fixes(questions, decisions).items()
             if qid not in rescued or qid in rescued_retirements}

    write_review(args.out / "review.csv", questions, decisions, fixes, records)
    shares = source_shares(questions, decisions)
    reasons = Counter(r.split(" (")[0].split(" of ")[0] for d in decisions.values() for r in d["reasons"])
    summary = {
        "questions": len(questions),
        "unscored": len(missing),
        "retire": sum(d["retire"] for d in decisions.values()),
        "fix_wording": len(fixes),
        "rescued": len(rescued),
        "by_source": shares,
        "by_reason": dict(reasons.most_common()),
    }
    over = {s: v for s, v in shares.items() if v["share"] > MAX_SOURCE_SHARE}
    sql_path = args.out / "quality.sql"
    if over:
        summary["blocked"] = f"over {MAX_SOURCE_SHARE:.0%} of a source would be retired: {sorted(over)}; no SQL written"
        sql_path.unlink(missing_ok=True)
    else:
        now_ms = args.now_ms if args.now_ms is not None else int(time.time() * 1000)
        sql_path.write_text(to_sql(questions, decisions, fixes, now_ms), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 2 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
