#!/usr/bin/env python3
"""Compare LM Studio models with Gemini on general-reference questions: writing them and the CMG conflict check.

For general-reference chunks Gemini has already done (from raw.jsonl), each local model writes a fresh question at the
same difficulty, checks its own question against the CMGs, and re-checks Gemini's question. The re-check is scored
against Gemini's verdict, including every conflict and out-of-scope question Gemini caught: a checker that misses a
CMG conflict lets a wrong-for-ACTAS question into the bank, so that column matters most.

Writes to tmp/local-generation-bench/:
  results.json        per-model summary and every call
  rating-sheet.csv    blinded: Gemini's and each model's question for the same chunk, in random order
  rating-key.json     which code is which model (don't open until the rating is done)

Usage (LM Studio server running, nothing else heavy on the Mac):
    PYTHONPATH=src/python .venv/bin/python3 scripts/bench-local-generation.py [--n 20] MODEL [MODEL ...]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "python"))

from web_corpus import questions as qb  # noqa: E402
from web_corpus.build import build  # noqa: E402

OUT_DIR = REPO_ROOT / "tmp" / "local-generation-bench"


def verdict(check: dict | None) -> str:
    if not check:
        return "failed"
    if check["conflict"]:
        return "conflict"
    if check["out_of_scope"]:
        return "out_of_scope"
    return "clean"


def pick(records: list[dict], n: int, seed: int = 7) -> list[dict]:
    general = [r for r in records if r.get("ok") and r.get("check")
               and str(r.get("prompt_version", "")).startswith("general")]
    rng = random.Random(seed)
    conflicts = [r for r in general if verdict(r["check"]) == "conflict"]
    scope = [r for r in general if verdict(r["check"]) == "out_of_scope"]
    flagged = conflicts + rng.sample(scope, min(len(scope), max(n // 4, 2)))
    clean = [r for r in general if verdict(r["check"]) == "clean"]
    rest = max(n - len(flagged), 0)
    openrn = [r for r in clean if r["document_id"].startswith("OPENRN_")]
    litfl = [r for r in clean if not r["document_id"].startswith("OPENRN_")]
    take = rng.sample(openrn, min(len(openrn), rest // 2))
    take += rng.sample(litfl, min(len(litfl), rest - len(take)))
    return flagged + take


def run_model(model: str, picked: list[dict], chunks: dict, corpus, base_url: str) -> dict:
    complete = qb.local_complete(model, base_url)
    runner = qb.Runner(corpus, OUT_DIR, "", None, 0.0, generate=complete, model_id=qb.LOCAL_PREFIX + model)
    print(f"\n{model}: loading", flush=True)
    complete("Reply with the word ready.", "ready?", None)
    rows = []
    for i, r in enumerate(picked, 1):
        chunk = chunks[r["chunk_id"]]
        row: dict = {"chunk_id": chunk.id, "gemini_verdict": verdict(r["check"])}
        try:
            text, usage = complete(qb.system_prompt(r["gen_view"], True),
                                   qb.user_prompt(chunk.embed_text, r["difficulty"], [], (), True), None)
            row["gen_seconds"] = round(usage["seconds"], 1)
            parsed = qb.parse_generation(text)
            row["question"] = parsed
            if not parsed:
                row["raw"] = text[:400]
        except qb.GenerationError as exc:
            row["error"] = str(exc)
            if exc.fatal:
                raise SystemExit(f"{model}: {exc}")
        if row.get("question"):
            own = {"cost_usd": 0.0}
            runner.check(row["question"]["question_text"], chunk, own)
            row["own_check"] = own.get("check")
            row["own_check_seconds"] = own.get("check_seconds")
        again = {"cost_usd": 0.0}
        runner.check(r["question_text"], chunk, again)
        row["recheck"] = again.get("check")
        row["recheck_verdict"] = verdict(again.get("check"))
        row["recheck_seconds"] = again.get("check_seconds")
        rows.append(row)
        print(f"  {i}/{len(picked)} gemini={row['gemini_verdict']} local={row['recheck_verdict']} "
              f"gen={row.get('gen_seconds')}s check={row.get('recheck_seconds')}s", flush=True)

    def score(kind: str) -> str:
        cases = [x for x in rows if x["gemini_verdict"] == kind]
        return f"{sum(1 for x in cases if x['recheck_verdict'] == kind)}/{len(cases)}"

    gen_s = [x["gen_seconds"] for x in rows if x.get("gen_seconds")]
    check_s = [x[k] for x in rows for k in ("own_check_seconds", "recheck_seconds") if x.get(k)]
    clean = [x for x in rows if x["gemini_verdict"] == "clean"]
    return {
        "model": model,
        "written": f"{sum(1 for x in rows if x.get('question'))}/{len(rows)}",
        "conflicts_caught": score("conflict"),
        "out_of_scope_caught": score("out_of_scope"),
        "clean_agreed": score("clean"),
        "false_alarms": sum(1 for x in clean if x["recheck_verdict"] in ("conflict", "out_of_scope")),
        "check_failures": sum(1 for x in rows if x["recheck_verdict"] == "failed"),
        "own_questions_dropped": sum(1 for x in rows if verdict(x.get("own_check")) in ("conflict", "out_of_scope")),
        "median_gen_s": round(statistics.median(gen_s), 1) if gen_s else None,
        "median_check_s": round(statistics.median(check_s), 1) if check_s else None,
        "rows": rows,
    }


def write_sheet(picked: list[dict], chunks: dict, results: list[dict], seed: int = 20261103) -> None:
    rng = random.Random(seed)
    key: dict[str, dict[str, str]] = {}
    with (OUT_DIR / "rating-sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["item", "code", "difficulty", "question", "source_text",
                         "accurate (Y/N)", "in_scope (Y/N)", "useful (1-5)", "notes"])
        for i, r in enumerate(picked, 1):
            candidates = [("gemini", r["question_text"])]
            for res in results:
                q = res["rows"][i - 1].get("question")
                if q:
                    candidates.append((res["model"], q["question_text"]))
            rng.shuffle(candidates)
            item = f"Q{i:02d}"
            key[item] = {}
            for j, (model, question) in enumerate(candidates):
                code = chr(ord("A") + j)
                key[item][code] = model
                writer.writerow([item, code, r["difficulty"], question,
                                 chunks[r["chunk_id"]].embed_text if j == 0 else "", "", "", "", ""])
    (OUT_DIR / "rating-key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", nargs="+")
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--raw", type=Path, default=qb.OUT_DIR / "raw.jsonl")
    parser.add_argument("--lmstudio-url", default="")
    args = parser.parse_args()

    corpus = build()
    chunks = {c.id: c for c in corpus.chunks}
    picked = [r for r in pick(qb.load_raw(args.raw), args.n) if r["chunk_id"] in chunks]
    if not picked:
        print("No checked general-reference questions in raw.jsonl to compare against.", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{len(picked)} chunks: " + ", ".join(
        f"{v} {sum(1 for r in picked if verdict(r['check']) == v)}" for v in ("conflict", "out_of_scope", "clean")))
    results = []
    started = time.monotonic()
    for model in args.models:
        results.append(run_model(model, picked, chunks, corpus, args.lmstudio_url))
        (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    write_sheet(picked, chunks, results)
    print(f"\nDone in {(time.monotonic() - started) / 60:.0f} min.")
    for res in results:
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
