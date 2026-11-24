"""Generate the web scenario bank offline from the ACTAS guideline corpus with local models.

A scenario is a patient case in stages. Each stage gives new findings, asks one question and carries a rubric whose
points cite numbered source lines. The writer model only picks line ids; this module copies the verbatim text, so a
rubric can never quote something the guidelines don't say. Plan: ``docs/plans/2026-11-23-actas-scenario-bank.md``.

Run from the repo root (two passes, one model server at a time):

    PYTHONPATH=src/python python3 -m web_corpus.scenarios plan [--pilot]
    PYTHONPATH=src/python python3 -m web_corpus.scenarios write --run pilot --pilot \\
        --model Inkling-2-Mini-oQ4e-mtp-nothink --base-url http://127.0.0.1:8084/v1
    PYTHONPATH=src/python python3 -m web_corpus.scenarios check --run pilot --model qwen/qwen3.8-27b
    PYTHONPATH=src/python python3 -m web_corpus.scenarios export --run pilot [--reviewed review.csv]

Model comparison: write the same blueprints into two runs (``--run bench-a --bench 10``), check both, then
``sheet --runs bench-a bench-b`` writes a blinded rating sheet.

``write`` and ``check`` append to ``runs/<run>/raw.jsonl`` and skip finished work, so they can be stopped and resumed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from paths import APP_ROOT
from web_corpus.answers import segments
from web_corpus.build import SERVICE_ID, SOURCE_TYPE, Chunk, Corpus, Document, build
from web_corpus.questions import (
    COVERED_BY,
    ICP_MENTION,
    LOCAL_PREFIX,
    PROMPTS,
    VIEW_ORDER,
    GenerationError,
    australian_spelling,
    content_hash,
    document_titles,
    local_complete,
    name_documents,
    parse_json_object,
)

OUT_DIR = APP_ROOT / "web" / "corpus-build" / "scenarios"
QUOTAS_PATH = Path(__file__).with_name("scenario_quotas.tsv")
REFERENCE_CARDS_ID = "ACTAS_Critical_Care_Reference_Cards"
DEFAULT_WRITER = "Inkling-2-Mini-oQ4e-mtp-nothink"
DEFAULT_CHECKER = "qwen/qwen3.8-27b"
DIFFICULTIES = ("easy", "medium", "hard")
PATIENT_GROUPS = ("adult", "paediatric", "neonate", "obstetric", "older_adult")
FOCUSES = ("assessment", "treatment", "pharmacology", "airway", "disposition")
LINKS_ALLOWED = {"easy": 0, "medium": 1, "hard": 2}
MIN_POINTS, MAX_POINTS = 2, 6
MAX_PRIMARY_CHARS = 9000
MAX_LINK_CHARS = 3000
NEAR_DUPLICATE = 0.6
MEDICINE_ALIASES = {"MED_13": ("GTN",), "MED_09": ("fentanyl",), "MED_18": ("ketamine",)}
LOW_VALUE_LINKS = frozenset({"MED_33_Oxygen", "MED_34_Normal_Saline"})
US_TERMS = re.compile(
    r"\b(epinephrine|acetaminophen|albuterol|nitroglycerin|meperidine|tylenol|EMTs?|emergency medical technicians?)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_LEAD = re.compile(r"\b12[\s-]?lead\b", re.IGNORECASE)
_LINE_ID = re.compile(r"^([GABR])(\d+)$")

Complete = Callable[[str, str, dict | None], tuple[str, dict]]


@dataclass(frozen=True)
class Quota:
    cmg: str
    weight: int
    groups: tuple[str, ...]
    pilot: bool
    icp: str


@dataclass(frozen=True)
class Blueprint:
    id: str
    document_id: str
    view: str
    difficulty: str
    patient_group: str
    stages: int
    links: tuple[str, ...]
    band_chunk_id: str | None = None
    pilot: bool = False

    @property
    def icp(self) -> bool:
        return self.view.startswith("icp")


@dataclass
class Line:
    id: str
    chunk_id: str
    document_id: str
    text: str
    heading: bool


@dataclass
class Pack:
    text: str
    lines: dict[str, Line] = field(default_factory=dict)
    documents: dict[str, str] = field(default_factory=dict)


def load_quotas(path: Path = QUOTAS_PATH) -> list[Quota]:
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    quotas = []
    for row in rows:
        groups = tuple(g.strip() for g in row["patient_groups"].split(",") if g.strip())
        bad = [g for g in groups if g not in PATIENT_GROUPS]
        if bad or not groups:
            raise ValueError(f"CMG {row['cmg']}: unknown patient group {bad or '(none)'}")
        quotas.append(Quota(row["cmg"], int(row["weight"]), groups, row["pilot"] == "Y", row["icp_set"]))
    return quotas


def _cmg_documents(corpus: Corpus) -> dict[str, Document]:
    return {d.number.upper(): d for d in corpus.documents if d.kind == "cmg"}


def _visible_views(doc: Document) -> list[str]:
    return [v for v in VIEW_ORDER if doc.bodies.get(v)]


def _mention_names(doc: Document) -> list[str]:
    title = doc.title
    names = [title.split("(")[0].strip()]
    names += [n.strip() for n in re.findall(r"\(([^)]+)\)", title)]
    names += [n.strip() for part in list(names) for n in part.split(" or ")]
    names += list(MEDICINE_ALIASES.get(doc.id[:6], ()))
    first = names[0].split()[0] if names[0] else ""
    if len(first) > 4 and first.lower() not in ("sodium", "calcium", "normal", "topical", "oral", "glucose"):
        names.append(first)
    return sorted({n for n in names if len(n) >= 3}, key=len, reverse=True)


def linked_medicines(corpus: Corpus, primary: Document, view: str) -> list[str]:
    body = primary.bodies.get(view, "").lower()
    counts = []
    for doc in corpus.documents:
        if doc.kind != "med" or not doc.bodies.get(view):
            continue
        n = max(len(re.findall(r"\b" + re.escape(name.lower()) + r"\b", body)) for name in _mention_names(doc))
        if n:
            icp_first = 0 if view.startswith("icp") and doc.scope == "icp" else 1
            counts.append((doc.id in LOW_VALUE_LINKS, icp_first, -n, doc.number, doc.id))
    return [item[-1] for item in sorted(counts)]


def _band_chunks(corpus: Corpus, view: str, group: str) -> list[Chunk]:
    bands = [c for c in corpus.chunks if c.document_id == REFERENCE_CARDS_ID and view in c.views]
    if group == "neonate":
        return [c for c in bands if c.heading.lower().startswith("newborn")]
    if group == "paediatric":
        return [c for c in bands if not c.heading.lower().startswith(("adult", "newborn", "≥"))]
    return []


def _stable(*parts: object) -> int:
    return int(hashlib.sha256("\0".join(map(str, parts)).encode("utf-8")).hexdigest(), 16)


def plan(corpus: Corpus, quotas: list[Quota] | None = None, pilot: bool = False) -> list[Blueprint]:
    quotas = quotas if quotas is not None else load_quotas()
    cmgs = _cmg_documents(corpus)
    blueprints: list[Blueprint] = []

    def add(doc: Document, view: str, difficulty: str, index: int, groups: tuple[str, ...], is_pilot: bool) -> None:
        group = groups[index % len(groups)]
        stages = 2 if difficulty == "easy" else 3 if difficulty == "medium" or index % 2 == 0 else 4
        allowed = LINKS_ALLOWED[difficulty]
        band = None
        bands = _band_chunks(corpus, view, group) if allowed else []
        if bands:
            band = bands[_stable(doc.id, view, difficulty, index) % len(bands)].id
            allowed -= 1
        links = tuple(linked_medicines(corpus, doc, view)[:allowed])
        bp_id = f"{doc.id}:{view}:{difficulty}:{index}"
        blueprints.append(Blueprint(bp_id, doc.id, view, difficulty, group, stages, links, band, is_pilot))

    for quota in quotas:
        doc = cmgs.get(quota.cmg.upper())
        if doc is None:
            raise ValueError(f"CMG {quota.cmg} is in the quotas but not in the corpus")
        views = _visible_views(doc)
        if not views:
            continue
        base = "ap" if "ap" in views else views[0]
        for difficulty in DIFFICULTIES:
            for index in range(quota.weight):
                add(doc, base, difficulty, index, quota.groups, quota.pilot and index == 0)
        if quota.icp in ("Y", "pilot") and base == "ap" and "icp" in views:
            add(doc, "icp", "medium", 0, quota.groups, quota.icp == "pilot")
            if quota.weight >= 3:
                add(doc, "icp", "hard", 1, quota.groups, False)
    if pilot:
        blueprints = [b for b in blueprints if b.pilot]
    return blueprints


def bench_subset(blueprints: list[Blueprint], n: int) -> list[Blueprint]:
    """A spread of pilot blueprints for comparing writers: one per guideline, rotating difficulty, one ICP case."""
    pilot = [b for b in blueprints if b.pilot]
    docs = sorted({b.document_id for b in pilot if not b.icp})
    picked = []
    for i, doc_id in enumerate(docs):
        wanted = DIFFICULTIES[i % len(DIFFICULTIES)]
        picked += [b for b in pilot if b.document_id == doc_id and not b.icp and b.difficulty == wanted][:1]
    icp = [b for b in pilot if b.icp][:1]
    return (picked[: max(n - len(icp), 0)] + icp)[:n]


def _doc_code(doc: Document) -> str:
    if doc.id == REFERENCE_CARDS_ID:
        return "Reference card"
    if doc.kind == "csm":
        return doc.number
    return f"{'MED' if doc.kind == 'med' else 'CMG'} {doc.number}"


def _chunks_for(corpus: Corpus, doc_id: str, view: str) -> list[Chunk]:
    return sorted((c for c in corpus.chunks if c.document_id == doc_id and view in c.views), key=lambda c: c.ordinal)


def _window(chunks: list[Chunk], limit: int, seed: int) -> list[Chunk]:
    if sum(len(c.text) for c in chunks) <= limit:
        return chunks
    start = seed % len(chunks)
    picked: list[Chunk] = []
    size = 0
    for c in chunks[start:] + chunks[:start]:
        if picked and size + len(c.text) > limit:
            break
        picked.append(c)
        size += len(c.text)
    return sorted(picked, key=lambda c: c.ordinal)


def build_pack(corpus: Corpus, bp: Blueprint) -> Pack:
    docs = {d.id: d for d in corpus.documents}
    chunk_by_id = {c.id: c for c in corpus.chunks}
    parts: list[tuple[str, Document, list[Chunk]]] = []
    primary = _window(_chunks_for(corpus, bp.document_id, bp.view), MAX_PRIMARY_CHARS, _stable(bp.id))
    parts.append(("G", docs[bp.document_id], primary))
    for prefix, doc_id in zip(("A", "B"), bp.links):
        parts.append((prefix, docs[doc_id], _window(_chunks_for(corpus, doc_id, bp.view), MAX_LINK_CHARS, 0)))
    if bp.band_chunk_id:
        parts.append(("R", docs[REFERENCE_CARDS_ID], [chunk_by_id[bp.band_chunk_id]]))
    pack = Pack(text="")
    out: list[str] = []
    for prefix, doc, chunks in parts:
        out.append(f"=== {prefix}: {doc.title} ({_doc_code(doc)}) ===")
        pack.documents[prefix] = doc.id
        n = 0
        for chunk in chunks:
            if prefix == "R":
                out.append(f"(Weight band: {chunk.heading})")
            for a, b in segments(chunk.text):
                n += 1
                text = chunk.text[a:b]
                line = Line(f"{prefix}{n}", chunk.id, doc.id, text, text.lstrip().startswith("#"))
                pack.lines[line.id] = line
                out.append(f"[{line.id}] {text}")
        out.append("")
    pack.text = "\n".join(out).strip()
    return pack


def _blueprint_text(bp: Blueprint, corpus: Corpus) -> str:
    docs = {d.id: d for d in corpus.documents}
    primary = docs[bp.document_id]
    lines = [
        f"Primary guideline: {primary.title} ({_doc_code(primary)})",
        f"Difficulty: {bp.difficulty}",
        f"Patient group: {bp.patient_group.replace('_', ' ')}",
        f"Stages: exactly {bp.stages}",
        f"Documents you may cite: G{''.join(', ' + p for p, _ in zip(('A', 'B'), bp.links))}"
        + (", R" if bp.band_chunk_id else ""),
        f"Scope: {'Intensive Care Paramedic (ICP)' if bp.icp else 'Ambulance Paramedic (AP)'}",
    ]
    if bp.band_chunk_id:
        chunk = next(c for c in corpus.chunks if c.id == bp.band_chunk_id)
        lines.append(f"The patient must match the weight band in R: {chunk.heading}.")
    return "\n".join(lines)


def writer_prompt(bp: Blueprint, corpus: Corpus, pack: Pack, previous: list[str]) -> tuple[str, str]:
    system = PROMPTS["scenarioSystem"]["icp" if bp.icp else "ap"]
    already = "\n".join(f"- {t}" for t in previous) or "(none)"
    user = f"Blueprint:\n{_blueprint_text(bp, corpus)}\n\nAlready written:\n{already}\n\nSource pack:\n{pack.text}"
    return system, user


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(_LEAD.sub("", text))}


def _scenario_text(s: dict) -> str:
    parts = [s.get("title", ""), s.get("dispatch", "")]
    for stage in s.get("stages", []):
        parts += [stage.get("findings", ""), stage.get("question", "")]
        parts += [p.get("point", "") for p in stage.get("rubric", [])]
    return "\n".join(parts)


def _clean(text: str, titles: dict) -> str:
    return name_documents(australian_spelling(str(text).strip()), titles)


def resolve(bp: Blueprint, corpus: Corpus, pack: Pack, raw: dict | None) -> tuple[dict | None, list[str]]:
    """Validate a writer reply and turn its line ids into verbatim citations. Returns (scenario, reasons)."""
    if not isinstance(raw, dict):
        return None, ["unreadable"]
    stages = raw.get("stages")
    if not isinstance(raw.get("title"), str) or not isinstance(raw.get("dispatch"), str) or not isinstance(stages, list):
        return None, ["schema"]
    titles = document_titles(corpus.documents)
    docs = {d.id: d for d in corpus.documents}
    reasons: list[str] = []
    if len(stages) != bp.stages:
        reasons.append(f"stage_count:{len(stages)}")
    out_stages = []
    cited_docs: set[str] = set()
    cited_chunks: dict[str, str] = {}
    for ordinal, stage in enumerate(stages, 1):
        if not isinstance(stage, dict) or not isinstance(stage.get("rubric"), list):
            return None, ["schema"]
        question = _clean(stage.get("question", ""), titles)
        findings = _clean(stage.get("findings", ""), titles)
        if not question or not findings:
            reasons.append(f"stage{ordinal}:empty")
        if re.match(r"\s*according to\b", question, re.IGNORECASE):
            reasons.append(f"stage{ordinal}:according_to")
        rubric = stage["rubric"]
        if not MIN_POINTS <= len(rubric) <= MAX_POINTS:
            reasons.append(f"stage{ordinal}:point_count:{len(rubric)}")
        points = []
        for p in rubric:
            if not isinstance(p, dict) or not isinstance(p.get("cites"), list) or not str(p.get("point", "")).strip():
                return None, ["schema"]
            cites = []
            for cid in p["cites"]:
                cid = str(cid).strip().strip("[]").upper()
                line = pack.lines.get(cid)
                if line is None or not _LINE_ID.match(cid):
                    reasons.append(f"stage{ordinal}:unknown_line:{cid}")
                    continue
                if line.heading:
                    reasons.append(f"stage{ordinal}:cites_heading:{cid}")
                    continue
                cites.append({"line": cid, "chunk_id": line.chunk_id, "document_id": line.document_id, "quote": line.text})
            if not cites:
                reasons.append(f"stage{ordinal}:uncited_point")
            point = _clean(p["point"], titles)
            cited_text = " ".join(c["quote"] for c in cites)
            missing = sorted(_numbers(point) - _numbers(cited_text))
            if cites and missing:
                reasons.append(f"stage{ordinal}:number_not_in_source:{','.join(missing)}")
            for c in cites:
                cited_docs.add(c["document_id"])
                cited_chunks[c["chunk_id"]] = c["document_id"]
            points.append({"point": point, "critical": p.get("critical") is True, "cites": cites})
        if not any(p["critical"] for p in points):
            reasons.append(f"stage{ordinal}:no_critical_point")
        focus = stage.get("focus") if stage.get("focus") in FOCUSES else "assessment"
        out_stages.append({"ordinal": ordinal, "reveal": findings, "question": question, "focus": focus, "rubric": points})
    if bp.document_id not in cited_docs:
        reasons.append("primary_not_cited")
    if len(cited_docs - {bp.document_id, REFERENCE_CARDS_ID}) > len(bp.links):
        reasons.append("too_many_documents")
    scenario = {
        "title": _clean(raw["title"], titles),
        "dispatch": _clean(raw["dispatch"], titles),
        "stages": out_stages,
    }
    text = _scenario_text(scenario)
    if US_TERMS.search(text):
        reasons.append(f"us_term:{US_TERMS.search(text).group(0).lower()}")
    vis = visibility(bp, docs, scenario, text)
    scenario["vis"] = vis
    if not vis[bp.view]:
        reasons.append("out_of_scope")
    quotes = [(c["document_id"], c["quote"]) for st in out_stages for p in st["rubric"] for c in p["cites"]]
    if bp.icp and all(q in docs[d].bodies.get("ap", "") or q in docs[d].bodies.get("ap_pacer", "") for d, q in quotes):
        reasons.append("no_icp_only_content")
    scenario["sources"] = [{"chunk_id": k, "document_id": v} for k, v in sorted(cited_chunks.items())]
    return scenario, reasons


def visibility(bp: Blueprint, docs: dict[str, Document], scenario: dict, text: str) -> dict[str, bool]:
    """A view can see the scenario when every cited line is in that view's text and nothing names ICP-only care."""
    icp_mention = bool(ICP_MENTION.search(text))
    quotes = [(c["document_id"], c["quote"]) for st in scenario["stages"] for p in st["rubric"] for c in p["cites"]]
    return {
        view: view in COVERED_BY[bp.view]
        and bool(quotes)
        and all(q in docs[d].bodies.get(view, "") for d, q in quotes)
        and not (icp_mention and view in ("ap", "ap_pacer"))
        for view in VIEW_ORDER
    }


def check_prompt(bp: Blueprint, corpus: Corpus, pack: Pack, scenario: dict) -> tuple[str, str]:
    lines = [f"Scope: {'ICP' if bp.icp else 'AP'}", f"Dispatch: {scenario['dispatch']}", ""]
    for st in scenario["stages"]:
        lines.append(f"Stage {st['ordinal']}")
        lines.append(f"Findings: {st['reveal']}")
        lines.append(f"Question: {st['question']}")
        for p in st["rubric"]:
            lines.append(f"- {'[critical] ' if p['critical'] else ''}{p['point']}")
            lines += [f"    cites [{c['line']}] {c['quote']}" for c in p["cites"]]
        lines.append("")
    return PROMPTS["scenarioCheckSystem"], "Scenario:\n" + "\n".join(lines) + f"\nSource pack:\n{pack.text}"


def parse_check(text: str, stages: int) -> dict | None:
    parsed = parse_json_object(text)
    if parsed is None or not isinstance(parsed.get("stages"), list) or len(parsed["stages"]) != stages:
        return None
    out = []
    for st in parsed["stages"]:
        if not isinstance(st, dict) or not all(isinstance(st.get(k), bool) for k in ("supported", "consistent", "complete", "in_scope")):
            return None
        out.append({k: st[k] for k in ("supported", "consistent", "complete", "in_scope")} | {"reason": str(st.get("reason", ""))})
    return {"stages": out, "pass": all(all(st[k] for k in ("supported", "consistent", "complete", "in_scope")) for st in out)}


def run_dir(out: Path, run: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run):
        raise ValueError("run names use letters, digits, dot, dash and underscore only")
    return out / "runs" / run


def load_raw(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("blueprint"):
                records[record["blueprint"]] = record
    return records


def _append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _rewrite(path: Path, records: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records.values()), encoding="utf-8")
    tmp.replace(path)


def write_one(complete: Complete, corpus: Corpus, bp: Blueprint, previous: list[str], model_id: str) -> dict:
    pack = build_pack(corpus, bp)
    system, user = writer_prompt(bp, corpus, pack, previous)
    record = {"blueprint": bp.id, "document_id": bp.document_id, "view": bp.view, "difficulty": bp.difficulty,
              "patient_group": bp.patient_group, "model_id": model_id, "prompt_version": PROMPTS["scenarioPromptVersion"],
              "corpus_version": corpus.version}
    start = time.monotonic()
    text, _ = complete(system, user, PROMPTS["scenarioSchema"])
    record["seconds"] = round(time.monotonic() - start, 1)
    raw = parse_json_object(text)
    scenario, reasons = resolve(bp, corpus, pack, raw)
    record.update(raw=raw if raw is not None else text[:4000], scenario=scenario, reasons=reasons,
                  status="ok" if scenario is not None and not reasons else "dropped" if scenario is not None else "unreadable")
    return record


def run_write(corpus: Corpus, blueprints: list[Blueprint], out: Path, complete: Complete, model_id: str,
              limit: int | None = None) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "raw.jsonl"
    done = load_raw(path)
    todo = [b for b in blueprints if b.id not in done or done[b.id]["status"] == "unreadable"]
    todo.sort(key=lambda b: (b.document_id, b.view, DIFFICULTIES.index(b.difficulty), b.id))
    if limit is not None:
        todo = todo[:limit]
    counts: dict[str, int] = {}
    started = time.monotonic()
    for i, bp in enumerate(todo, 1):
        previous = [r["scenario"]["title"] for r in done.values()
                    if r.get("document_id") == bp.document_id and r.get("status") == "ok" and r.get("scenario")]
        try:
            record = write_one(complete, corpus, bp, previous, model_id)
        except GenerationError as exc:
            print(f"Stopped at {bp.id}: {exc}", file=sys.stderr)
            if exc.fatal:
                break
            continue
        _append(path, record)
        done[bp.id] = record
        counts[record["status"]] = counts.get(record["status"], 0) + 1
        rate = (time.monotonic() - started) / i
        print(f"{i}/{len(todo)} {bp.id}: {record['status']} {record['reasons'][:3]} "
              f"({record['seconds']} s, ~{rate * (len(todo) - i) / 60:.0f} min left)", flush=True)
    return counts


def run_check(corpus: Corpus, out: Path, complete: Complete, model_id: str, limit: int | None = None) -> dict[str, int]:
    path = out / "raw.jsonl"
    records = load_raw(path)
    blueprints = {b.id: b for b in plan(corpus)}
    todo = [r for r in records.values() if r["status"] == "ok" and not r.get("check")]
    if limit is not None:
        todo = todo[:limit]
    counts: dict[str, int] = {}
    for i, r in enumerate(todo, 1):
        bp = blueprints.get(r["blueprint"])
        if bp is None:
            counts["unplanned"] = counts.get("unplanned", 0) + 1
            continue
        system, user = check_prompt(bp, corpus, build_pack(corpus, bp), r["scenario"])
        start = time.monotonic()
        try:
            text, _ = complete(system, user, PROMPTS["scenarioCheckSchema"])
        except GenerationError as exc:
            print(f"Stopped at {r['blueprint']}: {exc}", file=sys.stderr)
            if exc.fatal:
                break
            continue
        check = parse_check(text, len(r["scenario"]["stages"]))
        r["check"] = check if check is not None else {"pass": False, "unreadable": True, "stages": []}
        r["check_model_id"] = model_id
        r["check_seconds"] = round(time.monotonic() - start, 1)
        _rewrite(path, records)
        verdict = "pass" if r["check"]["pass"] else "unreadable" if r["check"].get("unreadable") else "fail"
        counts[verdict] = counts.get(verdict, 0) + 1
        print(f"{i}/{len(todo)} {r['blueprint']}: {verdict} ({r['check_seconds']} s)", flush=True)
    return counts


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def read_review(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    out = {}
    for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines()):
        verdict = (row.get("approve (Y/N)") or "").strip().upper()
        if row.get("blueprint") and verdict in ("Y", "N"):
            out[row["blueprint"]] = verdict
    return out


def select(corpus: Corpus, records: list[dict], review: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    review = review or {}
    chunks = {c.id for c in corpus.chunks}
    docs = {d.id: d for d in corpus.documents}
    kept: list[dict] = []
    dropped: list[dict] = []
    hashes: set[str] = set()
    for r in sorted(records, key=lambda r: r["blueprint"]):
        reason = None
        if r["status"] != "ok":
            reason = ";".join(r.get("reasons") or [r["status"]])
        elif not r.get("check"):
            reason = "unchecked"
        elif not r["check"]["pass"]:
            reason = "check_failed: " + " | ".join(st["reason"] for st in r["check"].get("stages", []) if st.get("reason"))
        elif any(s["chunk_id"] not in chunks for s in r["scenario"]["sources"]):
            reason = "stale"
        elif review.get(r["blueprint"]) == "N":
            reason = "rejected_in_review"
        if reason is None:
            text = _scenario_text(r["scenario"])
            h = content_hash(text)
            if h in hashes:
                reason = "duplicate"
            elif any(k["document_id"] == r["document_id"] and _jaccard(text, _scenario_text(k["scenario"])) >= NEAR_DUPLICATE
                     for k in kept):
                reason = "near_duplicate"
        if reason:
            dropped.append({**r, "drop_reason": reason})
            continue
        hashes.add(h)
        doc = docs[r["document_id"]]
        kept.append({**r, "id": h[:16], "content_hash": h, "category": doc.section, "document_title": doc.title,
                     "reviewed": review.get(r["blueprint"]) == "Y"})
    return kept, dropped


def _sql(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


NOW_MS = "CAST(unixepoch('subsec') * 1000 AS INTEGER)"
COLUMNS = (
    "id", "service", "primary_document_id", "category", "patient_group", "difficulty", "title", "dispatch_text",
    "stages_json", "gen_view", "vis_ap", "vis_ap_pacer", "vis_icp", "vis_icp_pacer", "source_type", "content_hash",
    "prompt_version", "model_id", "check_model_id", "corpus_version", "reviewed_by", "reviewed_at",
)


def to_sql(scenarios: list[dict], reviewer: str = "oscar") -> str:
    lines = []
    for s in scenarios:
        sc = s["scenario"]
        values = [
            s["id"], SERVICE_ID, s["document_id"], s["category"], s["patient_group"], s["difficulty"], sc["title"],
            sc["dispatch"], json.dumps(sc["stages"], ensure_ascii=False), s["view"], *(sc["vis"][v] for v in VIEW_ORDER),
            SOURCE_TYPE, s["content_hash"], s["prompt_version"], s["model_id"], s["check_model_id"], s["corpus_version"],
            reviewer if s["reviewed"] else None,
        ]
        select_list = ", ".join(f"{_sql(v)} AS {n}" for v, n in zip(values, COLUMNS))
        reviewed_at = NOW_MS if s["reviewed"] else "NULL"
        ids = ", ".join(_sql(x["chunk_id"]) for x in sc["sources"])
        lines.append(
            f"INSERT OR IGNORE INTO scenario_bank ({', '.join(COLUMNS)}, created_at, updated_at) "
            f"SELECT v.*, {reviewed_at}, {NOW_MS}, {NOW_MS} FROM (SELECT {select_list}) v "
            f"WHERE (SELECT COUNT(*) FROM corpus_chunks c WHERE c.id IN ({ids}) AND c.retired_at IS NULL) = {len(sc['sources'])};"
        )
        for x in sc["sources"]:
            lines.append(
                "INSERT OR IGNORE INTO scenario_sources (scenario_id, chunk_id, document_id) "
                f"SELECT id, {_sql(x['chunk_id'])}, {_sql(x['document_id'])} FROM scenario_bank WHERE id = {_sql(s['id'])};"
            )
    return "\n".join(lines) + ("\n" if lines else "")


def _scope_label(vis: dict[str, bool]) -> str:
    if vis["ap"]:
        return "AP"
    if vis["ap_pacer"]:
        return "AP + PACER"
    if vis["icp"]:
        return "ICP only"
    return "ICP + PACER only"


def render_text(sc: dict) -> str:
    lines = [sc["title"], f"Dispatch: {sc['dispatch']}", ""]
    for st in sc["stages"]:
        lines += [f"Stage {st['ordinal']}: {st['reveal']}", f"Q: {st['question']}"]
        for p in st["rubric"]:
            lines.append(f"  - {'[critical] ' if p['critical'] else ''}{p['point']}")
            lines += [f"      > {c['quote']}" for c in p["cites"]]
        lines.append("")
    return "\n".join(lines).strip()


def review_sample(scenarios: list[dict], n: int, seed: int = 20261124) -> list[dict]:
    rng = random.Random(seed)
    strata: dict[tuple, list[dict]] = {}
    for s in scenarios:
        strata.setdefault((s["difficulty"], s["view"].startswith("icp")), []).append(s)
    for group in strata.values():
        rng.shuffle(group)
    picked: list[dict] = []
    while len(picked) < min(n, len(scenarios)):
        for key in sorted(strata):
            if strata[key] and len(picked) < n:
                picked.append(strata[key].pop())
    return sorted(picked, key=lambda s: s["blueprint"])


def write_review(out: Path, sample: list[dict]) -> None:
    with (out / "review.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["blueprint", "guideline", "difficulty", "scope", "patient_group", "scenario", "approve (Y/N)", "notes"])
        for s in sample:
            w.writerow([s["blueprint"], s["document_title"], s["difficulty"], _scope_label(s["scenario"]["vis"]),
                        s["patient_group"], render_text(s["scenario"]), "", ""])
    parts = ["<!doctype html><meta charset=utf-8><title>Scenario review</title><style>",
             "body{font-family:system-ui;max-width:860px;margin:2rem auto;padding:0 1rem;line-height:1.5}",
             "section{margin:2.5rem 0}blockquote{margin:.2rem 0 .2rem 1.5rem;color:#2d5a54;background:#f3f1e8;padding:.2rem .5rem}",
             ".crit{font-weight:600}.meta{color:#666;font-size:.9em}</style><h1>Scenario review</h1>"]
    for s in sample:
        sc = s["scenario"]
        parts.append(f"<section><h2>{html.escape(sc['title'])}</h2><p class=meta>{html.escape(s['blueprint'])} · "
                     f"{html.escape(s['document_title'])} · {s['difficulty']} · {_scope_label(sc['vis'])} · "
                     f"{s['patient_group']}</p><p><b>Dispatch:</b> {html.escape(sc['dispatch'])}</p>")
        for st in sc["stages"]:
            parts.append(f"<h3>Stage {st['ordinal']}</h3><p>{html.escape(st['reveal'])}</p>"
                         f"<p><b>Q:</b> {html.escape(st['question'])}</p><ul>")
            for p in st["rubric"]:
                quotes = "".join(f"<blockquote>{html.escape(c['quote'])}</blockquote>" for c in p["cites"])
                parts.append(f"<li class={'crit' if p['critical'] else 'pt'}>{'Critical: ' if p['critical'] else ''}"
                             f"{html.escape(p['point'])}{quotes}</li>")
            parts.append("</ul>")
        parts.append("</section>")
    (out / "review.html").write_text("\n".join(parts), encoding="utf-8")


def write_dropped(out: Path, dropped: list[dict]) -> None:
    with (out / "dropped.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["blueprint", "status", "reason", "title"])
        for r in dropped:
            w.writerow([r["blueprint"], r["status"], r["drop_reason"], ((r.get("scenario") or {}).get("title") or "")])


def report(records: list[dict], kept: list[dict], dropped: list[dict]) -> dict:
    def count(items, key):
        out: dict[str, int] = {}
        for i in items:
            k = key(i)
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))
    seconds = sorted(r["seconds"] for r in records if r.get("seconds") is not None)
    return {
        "records": len(records),
        "kept": len(kept),
        "by_category": count(kept, lambda s: s["category"]),
        "by_difficulty": count(kept, lambda s: s["difficulty"]),
        "by_scope": count(kept, lambda s: _scope_label(s["scenario"]["vis"])),
        "dropped_by_reason": count(dropped, lambda r: r["drop_reason"].split(":")[0]),
        "median_write_seconds": seconds[len(seconds) // 2] if seconds else None,
    }


def write_sheet(out: Path, runs: dict[str, list[dict]], seed: int = 20261124) -> int:
    """Blinded rating sheet: the same blueprints from each run, labelled by code only."""
    by_bp: dict[str, dict[str, dict]] = {}
    for run, records in runs.items():
        for r in records:
            if r.get("scenario"):
                by_bp.setdefault(r["blueprint"], {})[run] = r
    rng = random.Random(seed)
    key: dict[str, str] = {}
    rows = []
    for n, bp in enumerate(sorted(b for b, rs in by_bp.items() if len(rs) == len(runs)), 1):
        names = list(runs)
        rng.shuffle(names)
        for letter, run in zip("ABCDEFGH", names):
            r = by_bp[bp][run]
            code = f"S{n:02d}-{letter}"
            key[code] = run
            check = r.get("check") or {}
            rows.append([code, bp, r["difficulty"], r["status"], "pass" if check.get("pass") else "fail" if check else "",
                         ";".join(r.get("reasons", [])), render_text(r["scenario"]), "", "", "", "", ""])
    out.mkdir(parents=True, exist_ok=True)
    with (out / "rating-sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "blueprint", "difficulty", "auto_checks", "model_check", "auto_reasons", "scenario",
                    "accurate (Y/N)", "in_scope (Y/N)", "realistic (1-5)", "useful (1-5)", "notes"])
        w.writerows(rows)
    (out / "rating-key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    return len(rows)


def main(argv: list[str] | None = None, complete_factory: Callable[[str, str], Complete] = local_complete) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["plan", "write", "check", "export", "sheet"])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--run", default="pilot")
    parser.add_argument("--runs", nargs="+", default=[])
    parser.add_argument("--pilot", action="store_true", help="only the pilot blueprints")
    parser.add_argument("--bench", type=int, default=None, metavar="N", help="a spread of N pilot blueprints")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default="", help="OpenAI-compatible server (LM Studio by default; oMLX for Inkling)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample", type=int, default=12)
    parser.add_argument("--reviewed", type=Path, default=None, help="review.csv with approve (Y/N) filled in")
    args = parser.parse_args(argv)

    corpus = build()
    if args.command == "plan":
        bps = plan(corpus, pilot=args.pilot)
        summary: dict[str, int] = {}
        for b in bps:
            k = f"{b.difficulty}/{'icp' if b.icp else 'ap'}"
            summary[k] = summary.get(k, 0) + 1
        print(json.dumps({"blueprints": len(bps), **dict(sorted(summary.items()))}))
        return 0

    out = run_dir(args.out, args.run)
    if args.command == "write":
        model = args.model or DEFAULT_WRITER
        bps = plan(corpus, pilot=args.pilot or args.bench is not None)
        if args.bench is not None:
            bps = bench_subset(bps, args.bench)
        counts = run_write(corpus, bps, out, complete_factory(model, args.base_url), LOCAL_PREFIX + model, args.limit)
        print(json.dumps(counts))
        return 0
    if args.command == "check":
        model = args.model or DEFAULT_CHECKER
        counts = run_check(corpus, out, complete_factory(model, args.base_url), LOCAL_PREFIX + model, args.limit)
        print(json.dumps(counts))
        return 0
    if args.command == "sheet":
        if len(args.runs) < 2:
            parser.error("sheet needs --runs with at least two runs")
        runs = {r: list(load_raw(run_dir(args.out, r) / "raw.jsonl").values()) for r in args.runs}
        n = write_sheet(args.out / "bench", runs)
        print(f"{n} rows in {args.out / 'bench' / 'rating-sheet.csv'}")
        return 0

    records = list(load_raw(out / "raw.jsonl").values())
    kept, dropped = select(corpus, records, read_review(args.reviewed))
    (out / "scenarios.sql").write_text(to_sql(kept), encoding="utf-8")
    if args.reviewed is None:
        write_review(out, review_sample(kept, args.sample))
    write_dropped(out, dropped)
    rep = report(records, kept, dropped)
    (out / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
