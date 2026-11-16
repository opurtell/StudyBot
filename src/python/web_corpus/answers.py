"""Find where each web question's answer sits in its source text, with a local LM Studio model.

The reveal view highlights these lines, so a student checking their own answer sees where to look without AI
marking. The model never writes a quote: the source is split into numbered lines and the model picks line
numbers, so every highlight is verbatim source text.

Run from the repo root, with the LM Studio server running:

    cd web && CLOUDFLARE_ENV=production npx wrangler d1 execute DB --remote --json \\
      --command "SELECT id, question_text, source_text FROM question_bank WHERE answer_quotes IS NULL" \\
      > corpus-build/answers/questions.json
    PYTHONPATH=src/python python3 -m web_corpus.answers locate [--model openai/gpt-oss-20b] [--limit N]
    PYTHONPATH=src/python python3 -m web_corpus.answers export

``locate`` appends to ``answers.jsonl`` and skips questions already done, so it can be stopped and resumed.
``export`` writes ``answers.sql`` (load with ``npm run answers:load:<env>`` in ``web/``) and ``review-sample.csv``.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Callable

from paths import APP_ROOT
from web_corpus.questions import parse_json_object

OUT_DIR = APP_ROOT / "web" / "corpus-build" / "answers"
DEFAULT_MODEL = "openai/gpt-oss-20b"
LONG_LINE = 220
MAX_LINES = 6
MAX_SHARE = 0.6

SYSTEM = """You find where the answer to a paramedic quiz question is stated in its source text.
The source is split into numbered lines. Return the numbers of the lines that state the answer: the lines a marker
would read to check a student's answer. Usually that is 1 to 3 lines, never more than 6. Do not include headings or
lines that only mention the topic. If no line states the answer, return an empty list.

Respond with valid JSON only:
{"lines": [3, 4]}"""

SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "integer"}}},
    "required": ["lines"],
}

_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'‘“-])")

Complete = Callable[[str, str], str]


def segments(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and re.search(r"[A-Za-z0-9]", stripped):
            start = pos + line.index(stripped)
            if len(stripped) <= LONG_LINE:
                spans.append((start, start + len(stripped)))
            else:
                offset = 0
                for part in _SENTENCE_END.split(stripped):
                    at = stripped.index(part, offset)
                    spans.append((start + at, start + at + len(part)))
                    offset = at + len(part)
        pos += len(line)
    return spans


def numbered(text: str, spans: list[tuple[int, int]]) -> str:
    return "\n".join(f"[{i}] {text[a:b]}" for i, (a, b) in enumerate(spans, 1))


def user_prompt(question: str, text: str, spans: list[tuple[int, int]]) -> str:
    return f"Question: {question}\n\nSource:\n{numbered(text, spans)}"


def parse_lines(reply: str, count: int) -> list[int] | None:
    parsed = parse_json_object(reply)
    if parsed is None or not isinstance(parsed.get("lines"), list):
        return None
    lines = sorted({n for n in parsed["lines"] if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= count})
    return lines


def quotes_for(text: str, spans: list[tuple[int, int]], lines: list[int]) -> list[str]:
    if not lines or len(lines) > MAX_LINES or (len(spans) > 2 and len(lines) > MAX_SHARE * len(spans)):
        return []
    merged: list[list[int]] = []
    for n in lines:
        a, b = spans[n - 1]
        if merged and merged[-1][2] == n - 1:
            merged[-1][1] = b
            merged[-1][2] = n
        else:
            merged.append([a, b, n])
    return [text[a:b] for a, b, _ in merged]


def locate_one(complete: Complete, question: dict) -> dict:
    text = question["source_text"]
    spans = segments(text)
    record = {"id": question["id"], "lines": [], "quotes": [], "status": "no_answer"}
    if not spans:
        return record
    lines = parse_lines(complete(SYSTEM, user_prompt(question["question_text"], text, spans)), len(spans))
    if lines is None:
        record["status"] = "unreadable"
        return record
    record["lines"] = lines
    record["quotes"] = quotes_for(text, spans, lines)
    if record["quotes"]:
        record["status"] = "ok"
    elif lines:
        record["status"] = "too_broad"
    return record


def load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in data if isinstance(data, list) else [data]:
        if isinstance(item, dict) and isinstance(item.get("results"), list):
            rows.extend(item["results"])
        elif isinstance(item, dict) and "id" in item:
            rows.append(item)
    return [r for r in rows if r.get("id") and r.get("question_text") and r.get("source_text")]


def load_records(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("id"):
                records[record["id"]] = record
    return records


def local_complete(model: str, base_url: str = "") -> Complete:
    from llm.lmstudio_provider import LMStudioProvider

    provider = LMStudioProvider(default_model=model, base_url=base_url)
    return lambda system, user: provider.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}], response_schema=SCHEMA
    )


def run_locate(questions: list[dict], out: Path, complete: Complete, limit: int | None = None,
               retry_unreadable: bool = True) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "answers.jsonl"
    done = load_records(path)
    todo = [q for q in questions if q["id"] not in done or (retry_unreadable and done[q["id"]]["status"] == "unreadable")]
    if limit is not None:
        todo = todo[:limit]
    counts: dict[str, int] = {}
    started = time.monotonic()
    with path.open("a", encoding="utf-8") as fh:
        for i, question in enumerate(todo, 1):
            try:
                record = locate_one(complete, question)
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


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def to_sql(records: list[dict]) -> str:
    lines = []
    for r in records:
        if r.get("status") != "ok" or not r.get("quotes"):
            continue
        quotes = json.dumps(r["quotes"], ensure_ascii=False)
        guard = " AND ".join(f"instr(source_text, {_sql(q)}) > 0" for q in r["quotes"])
        lines.append(f"UPDATE question_bank SET answer_quotes = {_sql(quotes)} WHERE id = {_sql(r['id'])} AND {guard};")
    return "\n".join(lines) + ("\n" if lines else "")


def write_review(path: Path, records: list[dict], questions: dict[str, dict], n: int, seed: int = 20261116) -> None:
    ok = [r for r in records if r.get("status") == "ok" and r["id"] in questions]
    sample = random.Random(seed).sample(ok, min(n, len(ok)))
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "question", "highlighted", "source", "highlight right (Y/N)", "notes"])
        for r in sample:
            q = questions[r["id"]]
            writer.writerow([r["id"], q["question_text"], "\n…\n".join(r["quotes"]), q["source_text"], "", ""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["locate", "export"])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--questions", type=Path, default=None, help="wrangler --json export (default: OUT/questions.json)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--lmstudio-url", default="")
    parser.add_argument("--limit", type=int, default=None, help="only the next N questions (for a trial run)")
    parser.add_argument("--sample", type=int, default=60)
    args = parser.parse_args(argv)

    questions = load_questions(args.questions or args.out / "questions.json")
    if args.command == "locate":
        counts = run_locate(questions, args.out, local_complete(args.model, args.lmstudio_url), args.limit)
        print(json.dumps(counts))
        return 0

    by_id = {q["id"]: q for q in questions}
    records = list(load_records(args.out / "answers.jsonl").values())
    (args.out / "answers.sql").write_text(to_sql(records), encoding="utf-8")
    write_review(args.out / "review-sample.csv", records, by_id, args.sample)
    totals: dict[str, int] = {}
    for r in records:
        totals[r["status"]] = totals.get(r["status"], 0) + 1
    print(json.dumps({"questions": len(questions), "records": len(records), **totals}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
