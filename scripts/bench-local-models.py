#!/usr/bin/env python3
"""Benchmark LM Studio models against StudyBot's real quiz workloads.

Leaderboards do not predict which local model works here — the app needs strict JSON,
conservative marking, and verbatim source quotes, and small models fail those in ways
general benchmarks do not measure. This script scores the things that actually matter:

  latency    median seconds per answer evaluation (the user-facing wait)
  json       responses the app's own _parse_json() can read
  grounded   source_quote values that appear verbatim in the source material
  accuracy   graded answers matching their known grade, across all three grades
  fabricated answers credited with correct_elements the student never wrote

The graded set deliberately contains correct and partial answers as well as wrong ones.
Measuring only "does it mark wrong answers wrong" rewards a model that says "incorrect"
to everything — medgemma-1.5-4b-it fails that way in one direction (it once marked every
answer "partial", including two perfect ones) and a over-tuned prompt fails in the other.

Usage:
    PYTHONPATH=src/python .venv/bin/python3 scripts/bench-local-models.py [model ...]

With no arguments every chat-capable model on the running LM Studio server is tested.
Run it alone: a concurrent job makes latency figures meaningless.
"""
from __future__ import annotations

import glob
import json
import re
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "python"))

from llm.base import LLMError  # noqa: E402
from llm.lmstudio_provider import LMStudioProvider, list_server_models  # noqa: E402
from quiz.agent import EVALUATION_SYSTEM_PROMPT, _parse_json  # noqa: E402

CMG_DIR = REPO_ROOT / "data" / "cmgs" / "structured"
SOURCE_CHARS = 3500

# Answers with a known grade. Wrong answers alone are not enough — see the module docstring.
# (cmg prefix, question, answer, expected grade)
GRADED_ANSWERS = [
    # Flatly wrong: nothing the student wrote is supported by the source.
    ("CMG_29_Allergic", "Describe the management of anaphylaxis.",
     "Antihistamines and steroids are the mainstay. Once the rash settles let the patient "
     "walk to the ambulance.", "incorrect"),
    ("CMG_10_Diabetic", "How is a BGL under 4 mmol/L managed?",
     "Give glucose 10% IV in every case. Oral glucose is never appropriate.", "incorrect"),
    ("CMG_11B_Hypothermia", "Define hypothermia and describe mild hypothermia.",
     "Hypothermia is a core temperature below 30 degrees. In mild hypothermia the patient "
     "never shivers and you must not give oral fluids.", "incorrect"),
    ("CMG_12_Upper_Airway", "How is complete airway obstruction managed in a conscious patient?",
     "Give up to five abdominal thrusts only. Back blows are contraindicated. Position the "
     "patient head up.", "incorrect"),
    ("CMG_14_Shock", "Summarise the management of haemorrhagic shock.",
     "Stay on scene until bleeding is fully controlled and withhold oxygen to avoid "
     "reperfusion injury.", "incorrect"),
    # Partial: right as far as it goes, but materially incomplete.
    ("CMG_29_Allergic", "Describe the management of anaphylaxis.",
     "Give IM adrenaline and oxygen therapy.", "partial"),
    ("CMG_10_Diabetic", "How is a BGL under 4 mmol/L managed?",
     "If the patient is conscious, give oral glucose.", "partial"),
    ("CMG_11B_Hypothermia", "Define hypothermia and describe mild hypothermia.",
     "Hypothermia is a core temperature below 35 degrees Celsius. Mild hypothermia is "
     "approximately 32 to 35 degrees.", "partial"),
    # Correct: covers the source's material points.
    ("CMG_10_Diabetic", "How is a BGL under 4 mmol/L managed?",
     "If symptomatic but conscious with intact laryngeal reflexes, give oral glucose via gel "
     "or food. If there is a decreased level of consciousness, give glucose 10% IV and repeat "
     "once if required. If no IV access is available, give glucagon IM. Consider the cause of "
     "the hypoglycaemia and ensure oral carbohydrate intake if the patient is not transported.",
     "correct"),
    ("CMG_12_Upper_Airway", "How is complete airway obstruction managed in a conscious patient?",
     "Give up to five back blows. If that fails, up to five chest thrusts, positioning the "
     "patient head down to use gravity if possible. Repeat the sequence as required. If it "
     "still fails, urgent transport with 100% oxygen.", "correct"),
]

# A generic partial answer, used only to see whether source_quote is copied or invented.
QUOTE_QUESTION = "Summarise the key management points in this guideline."
QUOTE_ANSWER = "Assess the patient, treat the presenting problem, and transport."


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", text.lower())).strip()


def quote_is_grounded(quote: str, source: str) -> bool:
    """True if the quote is really lifted from the source, not paraphrased."""
    q, s = _normalise(quote), _normalise(source)
    if len(q) < 20:  # too short to be a useful citation
        return False
    return q in s or q[:40] in s


def load_source(prefix: str) -> str:
    hits = sorted(glob.glob(str(CMG_DIR / f"{prefix}*.json")))
    if not hits:
        return ""
    return (json.loads(Path(hits[0]).read_text()).get("content_markdown") or "")[:SOURCE_CHARS]


def evaluate(provider: LMStudioProvider, question: str, source: str, answer: str):
    started = time.time()
    raw = provider.complete([
        {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Question: {question}\n\nSource material:\n{source}\n\nStudent answer: {answer}"
        )},
    ])
    return _parse_json(raw), time.time() - started


def bench(model_id: str) -> dict:
    provider = LMStudioProvider(default_model=model_id)
    result: dict = {"model": model_id, "errors": []}

    try:  # Load the model first so its load time is not charged to the first case.
        provider.complete([{"role": "user", "content": "Reply: ready"}])
    except LLMError as exc:
        return {"model": model_id, "fatal": str(exc)[:160]}

    times: list[float] = []
    json_ok = correct_grade = fabricated = grounded = graded = quoted = 0
    by_grade: dict[str, list[int]] = {"incorrect": [0, 0], "partial": [0, 0], "correct": [0, 0]}

    for prefix, question, answer, expected in GRADED_ANSWERS:
        source = load_source(prefix)
        if not source:
            result["errors"].append(f"no source for {prefix}")
            continue
        graded += 1
        by_grade[expected][1] += 1
        try:
            parsed, elapsed = evaluate(provider, question, source, answer)
            times.append(elapsed)
            if parsed:
                json_ok += 1
                if (parsed.get("score") or "").lower() == expected:
                    correct_grade += 1
                    by_grade[expected][0] += 1
                # Credit for an answer with nothing right is invented.
                if expected == "incorrect" and parsed.get("correct_elements"):
                    fabricated += 1
        except LLMError as exc:
            result["errors"].append(f"{prefix}: {str(exc)[:100]}")

    for path in sorted(CMG_DIR.glob("CMG_*.json"))[:10]:
        source = (json.loads(path.read_text()).get("content_markdown") or "")[:SOURCE_CHARS]
        if len(source) < 400:
            continue
        quoted += 1
        try:
            parsed, elapsed = evaluate(provider, QUOTE_QUESTION, source, QUOTE_ANSWER)
            times.append(elapsed)
            if parsed:
                json_ok += 1
                if quote_is_grounded(parsed.get("source_quote") or "", source):
                    grounded += 1
        except LLMError as exc:
            result["errors"].append(f"{path.stem}: {str(exc)[:100]}")

    result.update({
        "n": graded + quoted,
        "json": f"{json_ok}/{graded + quoted}",
        "accuracy": f"{correct_grade}/{graded}",
        "by_grade": {k: f"{v[0]}/{v[1]}" for k, v in by_grade.items()},
        "fabricated": fabricated,
        "grounded": f"{grounded}/{quoted}",
        "median_s": round(statistics.median(times), 1) if times else None,
        # The slowest call exposes first-request stalls under memory pressure.
        "max_s": round(max(times), 1) if times else None,
    })
    return result


def main() -> int:
    models = sys.argv[1:]
    if not models:
        try:
            models = [m["id"] for m in list_server_models()]
        except LLMError as exc:
            print(f"Cannot reach LM Studio: {exc}")
            return 1

    rows = []
    for model_id in models:
        print(f"benchmarking {model_id} ...", flush=True)
        rows.append(bench(model_id))

    print()
    header = (f"{'model':26s} {'json':>7s} {'accuracy':>9s} {'inc':>5s} {'part':>5s} "
              f"{'corr':>5s} {'fab':>4s} {'grounded':>9s} {'median':>7s}")
    print(header)
    print("-" * len(header))
    for r in rows:
        if r.get("fatal"):
            print(f"{r['model']:26s} UNUSABLE: {r['fatal'][:60]}")
            continue
        g = r["by_grade"]
        print(
            f"{r['model']:26s} {r['json']:>7s} {r['accuracy']:>9s} {g['incorrect']:>5s} "
            f"{g['partial']:>5s} {g['correct']:>5s} {r['fabricated']:>4d} "
            f"{r['grounded']:>9s} {str(r['median_s']) + 's':>7s}"
        )
        for err in r.get("errors", [])[:3]:
            print(f"    ! {err}")

    out = REPO_ROOT / "tmp" / "local-model-bench.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
