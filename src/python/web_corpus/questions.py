"""Generate the web question bank offline from the web corpus with Gemini.

Run from the repo root with a Gemini key in config/settings.json (providers.google.api_key):

    PYTHONPATH=src/python python3 -m web_corpus.questions plan
    PYTHONPATH=src/python python3 -m web_corpus.questions generate --yes [--limit N] [--max-usd 15]
    PYTHONPATH=src/python python3 -m web_corpus.questions export [--sample 60]

``plan`` makes no API calls. ``generate`` appends to ``raw.jsonl`` and skips work already done, so it can be
stopped and resumed. ``export`` writes ``questions.sql`` (load with ``npm run bank:load:<env>`` in ``web/``),
``review-sample.csv`` for clinical review and ``report.json``.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from paths import APP_ROOT
from web_corpus.build import ATTRIBUTION, LICENCE, SERVICE_ID, SOURCE_TYPE, Chunk, Corpus, build

PROMPTS_PATH = APP_ROOT / "web" / "src" / "worker" / "quiz" / "prompts.json"
OUT_DIR = APP_ROOT / "web" / "corpus-build" / "questions"
MODEL_ID = "gemini-3.8-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PRICE_PER_MILLION = (1.50, 7.50)
VIEW_ORDER = ("ap", "ap_pacer", "icp", "icp_pacer")
COVERED_BY = {
    "ap": ("ap", "ap_pacer", "icp", "icp_pacer"),
    "ap_pacer": ("ap_pacer", "icp_pacer"),
    "icp": ("icp", "icp_pacer"),
    "icp_pacer": ("icp_pacer",),
}
MIN_CHARS = 150
FULL_SET_CHARS = 400
NEAR_DUPLICATE = 0.8
TWIN_SIMILARITY = 0.85
MIN_FOCUS_CHARS = 30
EST_INPUT_TOKENS = 750
EST_OUTPUT_TOKENS = 450

PROMPTS = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
ICP_MENTION = re.compile(PROMPTS["icpMentionPattern"], re.IGNORECASE)
GUIDELINE_CODE = re.compile(r"\b(?:ACTAS\s+)?(?:(CMG|MED)\s?(\d+[A-Z]?)|CSM\.\s?([A-Z]{1,2}\d+))\b(?![.\d])")


class GenerationError(Exception):
    pass


@dataclass(frozen=True)
class Task:
    chunk: Chunk
    gen_view: str
    difficulties: tuple[str, ...]
    focus: tuple[str, ...] = ()


def gen_view_for(chunk: Chunk) -> str:
    return next(view for view in VIEW_ORDER if view in chunk.views)


def difficulties_for(chunk: Chunk) -> tuple[str, ...]:
    if len(chunk.text) < MIN_CHARS:
        return ()
    if len(chunk.text) < FULL_SET_CHARS:
        return ("easy",)
    return ("easy", "medium", "hard")


def _ap_visible(chunk: Chunk) -> bool:
    return "ap" in chunk.views or "ap_pacer" in chunk.views


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _is_twin(chunk: Chunk, sibling: Chunk) -> bool:
    """The ICP chunk nearly repeats the AP one, or holds every AP line plus ICP-only additions."""
    if difflib.SequenceMatcher(None, chunk.text, sibling.text).ratio() >= TWIN_SIMILARITY:
        return True
    own = set(_lines(chunk.text))
    theirs = _lines(sibling.text)
    return bool(theirs) and all(line in own for line in theirs)


def icp_focus(chunk: Chunk, siblings: list[Chunk]) -> tuple[str, ...] | None:
    """For an ICP-only chunk that repeats an AP chunk of the same section, the lines only ICPs see.

    Returns None when the chunk has no AP twin, so it is planned normally.
    """
    twins = [s for s in siblings if _is_twin(chunk, s)]
    if not twins:
        return None
    shared = {line.strip() for twin in twins for line in twin.text.splitlines()}
    return tuple(line.strip() for line in chunk.text.splitlines() if line.strip() and line.strip() not in shared)


def plan(corpus: Corpus) -> list[Task]:
    ap_sections: dict[tuple[str, str], list[Chunk]] = {}
    for chunk in corpus.chunks:
        if _ap_visible(chunk):
            ap_sections.setdefault((chunk.document_id, chunk.heading), []).append(chunk)
    tasks = []
    for chunk in corpus.chunks:
        diffs = difficulties_for(chunk)
        if not diffs:
            continue
        if not _ap_visible(chunk):
            focus = icp_focus(chunk, ap_sections.get((chunk.document_id, chunk.heading), []))
            if focus is not None:
                if sum(len(line) for line in focus) >= MIN_FOCUS_CHARS:
                    tasks.append(Task(chunk, gen_view_for(chunk), ("medium",), focus))
                continue
        tasks.append(Task(chunk, gen_view_for(chunk), diffs))
    return tasks


def focus_chunk_ids(tasks: list[Task]) -> set[str]:
    return {t.chunk.id for t in tasks if t.focus}


def system_prompt(gen_view: str) -> str:
    return PROMPTS["generationSystem"]["icp" if gen_view.startswith("icp") else "ap"]


def user_prompt(source: str, difficulty: str, previous: list[str], focus: tuple[str, ...] = ()) -> str:
    user = f"Source material:\n\n[Source 1: {SOURCE_TYPE}]\n{source}\n\nDifficulty: {difficulty}"
    extra = PROMPTS["difficultyInstructions"].get(difficulty, "")
    if extra:
        user += f"\n\n{extra}"
    if focus:
        user += "\n\n" + PROMPTS["icpFocusInstruction"] + "\n" + "\n".join(f"- {line}" for line in focus)
    if previous:
        user += "\n\nPreviously asked questions (do NOT repeat these):\n" + "\n".join(f"- {q}" for q in previous)
    return user


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def parse_json_object(text: str) -> dict | None:
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s+(.*?)\s+```", text, re.DOTALL)
    body = (fenced.group(1) if fenced else text).strip()
    for candidate in (body, (re.search(r"(\{.*\})", body, re.DOTALL) or [None, None])[1]):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return parsed if isinstance(parsed, dict) else None
    return None


def parse_generation(text: str) -> dict | None:
    parsed = parse_json_object(text)
    if not parsed:
        return None
    question = parsed.get("question_text")
    if not isinstance(question, str) or len(question.strip()) < 10:
        return None
    qtype = parsed.get("question_type")
    return {
        "question_text": question.strip(),
        "question_type": qtype if qtype in ("recall", "definition", "scenario", "drug_dose") else "recall",
        "source_citation": str(parsed.get("source_citation") or "").strip(),
        "category": str(parsed.get("category") or "").strip(),
    }


def visibility(gen_view: str, chunk_views: set[str], question: str) -> dict[str, bool]:
    icp_only = bool(ICP_MENTION.search(question))
    return {
        view: view in COVERED_BY[gen_view] and view in chunk_views and not (icp_only and view in ("ap", "ap_pacer"))
        for view in VIEW_ORDER
    }


Transport = Callable[[str, dict, str], dict]


def http_transport(url: str, body: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read().decode("utf-8"))


def call_gemini(transport: Transport, api_key: str, system: str, user: str, retries: int = 4) -> tuple[str, dict]:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseJsonSchema": PROMPTS["generationSchema"],
        },
    }
    delay = 2.0
    for attempt in range(retries):
        try:
            data = transport(API_URL.format(model=MODEL_ID), body, api_key)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise GenerationError(f"Gemini returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                raise GenerationError(f"Gemini request failed: {exc}") from exc
        time.sleep(delay)
        delay *= 2
    candidate = (data.get("candidates") or [{}])[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    meta = data.get("usageMetadata") or {}
    usage = {
        "input": meta.get("promptTokenCount", 0),
        "output": meta.get("candidatesTokenCount", 0),
        "thinking": meta.get("thoughtsTokenCount", 0),
    }
    return text, usage


def usage_cost(usage: dict) -> float:
    return (usage["input"] * PRICE_PER_MILLION[0] + (usage["output"] + usage["thinking"]) * PRICE_PER_MILLION[1]) / 1_000_000


def estimate_cost(tasks: list[Task]) -> float:
    calls = sum(len(t.difficulties) for t in tasks)
    return calls * (EST_INPUT_TOKENS * PRICE_PER_MILLION[0] + EST_OUTPUT_TOKENS * PRICE_PER_MILLION[1]) / 1_000_000


def load_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Runner:
    def __init__(self, corpus: Corpus, out_dir: Path, api_key: str, transport: Transport, max_usd: float):
        self.corpus = corpus
        self.raw_path = out_dir / "raw.jsonl"
        self.api_key = api_key
        self.transport = transport
        self.max_usd = max_usd
        self.lock = threading.Lock()
        existing = load_raw(self.raw_path)
        self.done = {(r["chunk_id"], r["difficulty"], bool(r.get("focus"))) for r in existing if r.get("ok")}
        self.previous: dict[str, list[str]] = {}
        for r in existing:
            if r.get("ok"):
                self.previous.setdefault(r["chunk_id"], []).append(r["question_text"])
        self.spent = sum(r.get("cost_usd", 0.0) for r in existing)
        self.made = 0
        self.failed = 0

    def _write(self, record: dict) -> None:
        with self.lock:
            with self.raw_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.spent += record.get("cost_usd", 0.0)
            if record.get("ok"):
                self.made += 1
            else:
                self.failed += 1

    def run_task(self, task: Task) -> None:
        chunk = task.chunk
        for difficulty in task.difficulties:
            if (chunk.id, difficulty, bool(task.focus)) in self.done:
                continue
            if self.spent >= self.max_usd:
                return
            previous = self.previous.setdefault(chunk.id, [])
            record = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "difficulty": difficulty,
                "gen_view": task.gen_view,
                "model_id": MODEL_ID,
                "prompt_version": PROMPTS["promptVersion"],
                "corpus_version": self.corpus.version,
                "source_text": chunk.embed_text,
                "focus": bool(task.focus),
                "ok": False,
                "cost_usd": 0.0,
            }
            parsed = None
            for _ in range(2):
                try:
                    text, usage = call_gemini(
                        self.transport, self.api_key, system_prompt(task.gen_view),
                        user_prompt(chunk.embed_text, difficulty, previous, task.focus),
                    )
                except GenerationError as exc:
                    record["error"] = str(exc)
                    break
                record["cost_usd"] += usage_cost(usage)
                parsed = parse_generation(text)
                if parsed:
                    break
                record["error"] = f"unparseable: {text[:200]}"
            if parsed:
                record.update(parsed, ok=True)
                record.pop("error", None)
                previous.append(parsed["question_text"])
            self._write(record)

    def run(self, tasks: list[Task], workers: int, progress: Callable[[str], None] = print) -> None:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self.run_task, t) for t in tasks]
            for i, future in enumerate(futures, 1):
                future.result()
                if i % 25 == 0 or i == len(futures):
                    progress(f"{i}/{len(futures)} chunks, {self.made} questions, {self.failed} failures, US${self.spent:.2f}")


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(normalise(a).split()), set(normalise(b).split())
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def _doc_label(doc) -> str:
    if doc.kind == "csm":
        return f"ACTAS {doc.number}"
    return f"ACTAS {'MED' if doc.kind == 'med' else 'CMG'} {doc.number}"


def _code_key(kind: str, number: str) -> tuple[str, str]:
    return kind, number.upper().lstrip("0") or "0"


def guideline_titles(corpus: Corpus) -> dict[tuple[str, str], str]:
    titles = {}
    for doc in corpus.documents:
        if doc.kind == "csm" and doc.number.startswith("CSM."):
            titles[_code_key("CSM", doc.number[4:])] = doc.title
        elif doc.kind in ("cmg", "med"):
            titles[_code_key(doc.kind.upper(), doc.number)] = doc.title
    return titles


def name_guidelines(text: str, titles: dict[tuple[str, str], str]) -> str:
    """Add the title after any guideline code the question names on its own, since users know guidelines by title."""

    def named(match: re.Match) -> str:
        kind, number, csm = match.groups()
        title = titles.get(_code_key("CSM", csm) if csm else _code_key(kind, number))
        if not title:
            return match.group(0)
        core = re.sub(r"\s*\([^)]*\)", "", title).strip().lower()
        after = text[match.end():match.end() + len(title) + 4].lstrip(" (:-\u2013").lower()
        before = text[max(0, match.start() - len(core) - 30):match.start()].lower()
        if after.startswith(core) or core in before:
            return match.group(0)
        flat = re.sub(r"\s*\(([^)]*)\)", r", \1", title)
        return f"{match.group(0)} ({flat})"

    return GUIDELINE_CODE.sub(named, text)


def select_questions(corpus: Corpus, records: list[dict]) -> tuple[list[dict], dict]:
    chunks = {c.id: c for c in corpus.chunks}
    docs = {d.id: d for d in corpus.documents}
    tasks = plan(corpus)
    planned = {t.chunk.id for t in tasks}
    focused = focus_chunk_ids(tasks)
    stats = {"stale": 0, "unplanned": 0, "exact_duplicates": 0, "near_duplicates": 0, "ap_restricted": 0}
    kept: list[dict] = []
    hashes: set[str] = set()
    by_chunk: dict[str, list[str]] = {}
    titles = guideline_titles(corpus)
    for r in records:
        if not r.get("ok"):
            continue
        r = {**r, "question_text": name_guidelines(r["question_text"], titles)}
        chunk = chunks.get(r["chunk_id"])
        if chunk is None or chunk.embed_text != r["source_text"]:
            stats["stale"] += 1
            continue
        if chunk.id not in planned or (chunk.id in focused) != bool(r.get("focus")):
            stats["unplanned"] += 1
            continue
        h = content_hash(r["question_text"])
        if h in hashes:
            stats["exact_duplicates"] += 1
            continue
        if any(_jaccard(r["question_text"], other) >= NEAR_DUPLICATE for other in by_chunk.get(chunk.id, [])):
            stats["near_duplicates"] += 1
            continue
        vis = visibility(r["gen_view"], chunk.views, r["question_text"])
        if not any(vis.values()):
            continue
        if any(v in chunk.views for v in ("ap", "ap_pacer")) and not (vis["ap"] or vis["ap_pacer"]):
            stats["ap_restricted"] += 1
        doc = docs[chunk.document_id]
        hashes.add(h)
        by_chunk.setdefault(chunk.id, []).append(r["question_text"])
        kept.append({
            **r,
            "id": h[:16],
            "content_hash": h,
            "vis": vis,
            "category": r.get("category") or doc.section,
            "source_citation": r.get("source_citation") or _doc_label(doc),
            "document_title": doc.title,
            "document_label": _doc_label(doc),
        })
    return kept, stats


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
    "id, service, document_id, chunk_id, source_text, question_text, question_type, difficulty, category, "
    "source_citation, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, licence, attribution, "
    "content_hash, prompt_version, model_id, corpus_version, origin, status, created_at, updated_at"
)


def to_sql(questions: list[dict]) -> str:
    lines = []
    for q in questions:
        values = [
            q["id"], SERVICE_ID, q["document_id"], q["chunk_id"], q["source_text"], q["question_text"],
            q["question_type"], q["difficulty"], q["category"], q["source_citation"], q["gen_view"],
            *(q["vis"][v] for v in VIEW_ORDER), SOURCE_TYPE, LICENCE, ATTRIBUTION, q["content_hash"],
            q["prompt_version"], q["model_id"], q["corpus_version"], "bank", "active",
        ]
        names = [c.strip() for c in COLUMNS.split(",")][:-2]
        select = ", ".join(f"{_sql(v)} AS {n}" for v, n in zip(values, names))
        lines.append(
            f"INSERT OR IGNORE INTO question_bank ({COLUMNS}) SELECT v.*, {NOW_MS}, {NOW_MS} FROM (SELECT {select}) v "
            "WHERE EXISTS (SELECT 1 FROM corpus_chunks c WHERE c.id = v.chunk_id AND c.retired_at IS NULL "
            "AND c.embed_text = v.source_text);"
        )
    return "\n".join(lines) + "\n"


def scope_label(vis: dict[str, bool]) -> str:
    if vis["ap"]:
        return "AP"
    if vis["ap_pacer"]:
        return "AP + PACER"
    if vis["icp"]:
        return "ICP"
    return "ICP + PACER"


def review_sample(questions: list[dict], n: int, seed: int = 20261101) -> list[dict]:
    rng = random.Random(seed)
    groups: dict[tuple[str, str], list[dict]] = {}
    for q in questions:
        groups.setdefault((scope_label(q["vis"]), q["difficulty"]), []).append(q)
    keys = sorted(groups)
    picked: list[dict] = []
    while len(picked) < min(n, len(questions)):
        for key in keys:
            pool = groups[key]
            if pool and len(picked) < n:
                picked.append(pool.pop(rng.randrange(len(pool))))
    rng.shuffle(picked)
    return picked


def write_sample(path: Path, sample: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "shown_to", "difficulty", "guideline", "question", "source_text",
                         "accurate (Y/N)", "in_scope (Y/N)", "useful (1-5)", "notes"])
        for q in sample:
            writer.writerow([q["id"], scope_label(q["vis"]), q["difficulty"],
                             f"{q['document_label']} {q['document_title']}", q["question_text"], q["source_text"],
                             "", "", "", ""])


def report(questions: list[dict], records: list[dict], stats: dict) -> dict:
    by_scope: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    for q in questions:
        by_scope[scope_label(q["vis"])] = by_scope.get(scope_label(q["vis"]), 0) + 1
        by_difficulty[q["difficulty"]] = by_difficulty.get(q["difficulty"], 0) + 1
    return {
        "questions": len(questions),
        "visible_to": {view: sum(1 for q in questions if q["vis"][view]) for view in VIEW_ORDER},
        "lowest_scope": by_scope,
        "by_difficulty": by_difficulty,
        "documents": len({q["document_id"] for q in questions}),
        "failures": sum(1 for r in records if not r.get("ok")),
        "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in records), 2),
        **stats,
    }


def api_key_from_settings() -> str:
    from llm.factory import load_config

    key = (load_config().get("providers", {}).get("google", {}) or {}).get("api_key", "")
    if not key:
        raise SystemExit("No Gemini key in config/settings.json (providers.google.api_key).")
    return key


def main(argv: list[str] | None = None, transport: Transport = http_transport) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["plan", "generate", "export"])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--yes", action="store_true", help="confirm spending money on generation")
    parser.add_argument("--limit", type=int, default=None, help="only the first N chunks (for a trial run)")
    parser.add_argument("--max-usd", type=float, default=15.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sample", type=int, default=60)
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args(argv)

    corpus = build()
    tasks = plan(corpus)
    if args.limit is not None:
        tasks = random.Random(7).sample(tasks, min(args.limit, len(tasks)))
    args.out.mkdir(parents=True, exist_ok=True)

    if args.command == "plan":
        calls = sum(len(t.difficulties) for t in tasks)
        by_view: dict[str, int] = {}
        for t in tasks:
            by_view[t.gen_view] = by_view.get(t.gen_view, 0) + len(t.difficulties)
        print(json.dumps({
            "corpus_version": corpus.version,
            "chunks": len(corpus.chunks),
            "chunks_used": len(tasks),
            "calls": calls,
            "calls_by_generation_scope": by_view,
            "estimated_usd": round(estimate_cost(tasks), 2),
        }, indent=2))
        return 0

    if args.command == "generate":
        if not args.yes:
            print(f"This makes up to {sum(len(t.difficulties) for t in tasks)} Gemini calls "
                  f"(about US${estimate_cost(tasks):.2f}). Re-run with --yes to go ahead.")
            return 1
        runner = Runner(corpus, args.out, args.api_key or api_key_from_settings(), transport, args.max_usd)
        runner.run(tasks, args.workers)
        if runner.spent >= args.max_usd:
            print(f"Stopped at the US${args.max_usd:.2f} cap. Re-run with a higher --max-usd to continue.")
        return 0

    records = load_raw(args.out / "raw.jsonl")
    if not records:
        print("Nothing generated yet. Run the generate command first.", file=sys.stderr)
        return 1
    questions, stats = select_questions(corpus, records)
    (args.out / "questions.sql").write_text(to_sql(questions), encoding="utf-8")
    write_sample(args.out / "review-sample.csv", review_sample(questions, args.sample))
    info = report(questions, records, stats)
    (args.out / "report.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
