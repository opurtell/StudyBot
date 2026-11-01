#!/usr/bin/env python3
"""Benchmark cloud models on StudyBot's marking and question generation (web port Phase 1).

Marking is scored on the labelled answers from ``bench-local-models.py``:

  json        responses the app's own _parse_json() can read
  accuracy    graded answers matching their known grade, across all three grades
  fabricated  answers that are wholly wrong but get credited with correct_elements
  grounded    source_quote values that appear verbatim in the source
  latency     median and max seconds per call
  cost        estimated USD per marking call (characters / 4 as tokens; the LLM
              interface does not return usage yet, see review H-8)

``--generate`` also writes a blinded question sample for clinical rating. Every model
gets the same sources, difficulties and qualification, so the ratings compare like
with like. The model behind each row is in a separate key file.

Usage (from the repo root, with API keys in config/settings.json)::

    PYTHONPATH=src/python python3 scripts/bench-cloud-models.py [--generate 50] [provider:model ...]

With no models the four Phase 1 candidates are run. Run it alone: concurrent jobs
make the latency figures meaningless.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "python"))

from guidelines import actas_scope  # noqa: E402
from llm.base import LLMError  # noqa: E402
from llm.factory import _PROVIDERS, load_config  # noqa: E402
from quiz.agent import (  # noqa: E402
    DIFFICULTY_INSTRUCTIONS,
    EVALUATION_SYSTEM_PROMPT,
    _parse_json,
    build_generation_prompt,
)

CMG_DIR = REPO_ROOT / "data" / "services" / "actas" / "structured"
LEGACY_DIR = REPO_ROOT / "data" / "cmgs" / "structured"
OUT_DIR = REPO_ROOT / "tmp" / "cloud-model-bench"
SOURCE_CHARS = 3500
GEN_CHUNK_CHARS = 1800

DEFAULT_MODELS = [
    "google:gemini-3.8-flash",
    "google:gemini-3.5-flash-lite",
    "zai:glm-5.3-flash",
    "zai:glm-5.3-flashx",
]

# USD per million tokens (input, output), checked 2026-10-31; see review section 8.
PRICES = {
    "gemini-3.8-flash": (1.50, 7.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "glm-5.3-flash": (0.15, 0.50),
    "glm-5.3-flashx": (0.37, 1.25),
}

# Answers with a known grade (cmg prefix, question, answer, expected grade).
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


QUOTE_QUESTION = "Summarise the key management points in this guideline."
QUOTE_ANSWER = "Assess the patient, treat the presenting problem, and transport."


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", text.lower())).strip()


def quote_is_grounded(quote: str, source: str) -> bool:
    q, s = _normalise(quote), _normalise(source)
    if len(q) < 20:
        return False
    return q in s or q[:40] in s


def load_source(prefix: str) -> str:
    hits = sorted(glob.glob(str(CMG_DIR / f"{prefix}*.json")))
    if not hits:
        return ""
    return (json.loads(Path(hits[0]).read_text()).get("content_markdown") or "")[:SOURCE_CHARS]


def make_client(spec: str):
    provider, _, model = spec.partition(":")
    if provider not in _PROVIDERS or not model:
        raise SystemExit(f"Bad model spec {spec!r}; use provider:model, e.g. zai:glm-5.3-flash")
    key = load_config()["providers"].get(provider, {}).get("api_key", "")
    if not key:
        raise SystemExit(f"No API key for {provider} in config/settings.json")
    return _PROVIDERS[provider](api_key=key, default_model=model), model


def cost(model: str, chars_in: int, chars_out: int) -> float | None:
    price = PRICES.get(model)
    if not price:
        return None
    return (chars_in / 4 * price[0] + chars_out / 4 * price[1]) / 1_000_000


class Meter:
    def __init__(self) -> None:
        self.times: list[float] = []
        self.chars_in = 0
        self.chars_out = 0
        self.calls = 0

    def call(self, client, messages: list[dict]) -> str:
        for attempt in range(4):
            started = time.time()
            try:
                raw = client.complete(messages) or ""
                break
            except LLMError as exc:
                transient = any(code in str(exc) for code in ("429", "500", "503", "UNAVAILABLE"))
                if not transient or "1113" in str(exc) or attempt == 3:
                    raise
                time.sleep(5 * 2 ** attempt)
        self.times.append(time.time() - started)
        self.chars_in += sum(len(m["content"]) for m in messages)
        self.chars_out += len(raw)
        self.calls += 1
        return raw


def evaluate(client, meter: Meter, question: str, source: str, answer: str):
    raw = meter.call(client, [
        {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Question: {question}\n\nSource material:\n{source}\n\nStudent answer: {answer}"
        )},
    ])
    return _parse_json(raw)


def bench_marking(spec: str) -> dict:
    client, model = make_client(spec)
    meter = Meter()
    result: dict = {"model": spec, "errors": []}
    try:
        Meter().call(client, [{"role": "user", "content": "Reply: ready"}])
    except LLMError as exc:
        return {"model": spec, "fatal": str(exc)[:200]}

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
            parsed = evaluate(client, meter, question, source, answer)
            if parsed:
                json_ok += 1
                if (parsed.get("score") or "").lower() == expected:
                    correct_grade += 1
                    by_grade[expected][0] += 1
                if expected == "incorrect" and parsed.get("correct_elements"):
                    fabricated += 1
        except LLMError as exc:
            result["errors"].append(f"{prefix}: {str(exc)[:120]}")

    for path in sorted(CMG_DIR.glob("CMG_*.json"))[:10]:
        source = (json.loads(path.read_text()).get("content_markdown") or "")[:SOURCE_CHARS]
        if len(source) < 400:
            continue
        quoted += 1
        try:
            parsed = evaluate(client, meter, QUOTE_QUESTION, source, QUOTE_ANSWER)
            if parsed:
                json_ok += 1
                if quote_is_grounded(parsed.get("source_quote") or "", source):
                    grounded += 1
        except LLMError as exc:
            result["errors"].append(f"{path.stem}: {str(exc)[:120]}")

    per_call = cost(model, meter.chars_in, meter.chars_out)
    result.update({
        "n": graded + quoted,
        "json": f"{json_ok}/{graded + quoted}",
        "accuracy": f"{correct_grade}/{graded}",
        "by_grade": {k: f"{v[0]}/{v[1]}" for k, v in by_grade.items()},
        "fabricated": fabricated,
        "grounded": f"{grounded}/{quoted}",
        "median_s": round(statistics.median(meter.times), 1) if meter.times else None,
        "max_s": round(max(meter.times), 1) if meter.times else None,
        "usd_per_mark": round(per_call / meter.calls, 5) if per_call and meter.calls else None,
    })
    return result


def _sources() -> list[dict]:
    docs = []
    patterns = [str(CMG_DIR / "CMG_*.json"), str(LEGACY_DIR / "med" / "*.json"),
                str(LEGACY_DIR / "csm" / "*.json")]
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            doc = json.loads(Path(path).read_text())
            if len(doc.get("content_markdown") or "") >= 400:
                docs.append(doc)
    return docs


def _chunk(text: str, rng: random.Random) -> str:
    sections = [s for s in re.split(r"\n(?=#{1,4} )", text) if len(s.strip()) > 200]
    if not sections:
        return text[:GEN_CHUNK_CHARS]
    start = rng.randrange(len(sections))
    out = ""
    for section in sections[start:]:
        if out and len(out) + len(section) > GEN_CHUNK_CHARS:
            break
        out += section + "\n"
    return out[:GEN_CHUNK_CHARS]


def sample_plan(n: int, seed: int = 20261101) -> list[dict]:
    """The same sources, difficulties and qualifications for every model."""
    rng = random.Random(seed)
    docs = _sources()
    picks = rng.sample(docs, min(n, len(docs)))
    plan = []
    for i, doc in enumerate(picks):
        icp = i % 5 == 4
        quals = frozenset({"AP", "ICP"}) if icp else frozenset({"AP"})
        whole = actas_scope.document_scope(doc)
        if whole == actas_scope.ICP and not icp:
            icp, quals = True, frozenset({"AP", "ICP"})
        text = actas_scope.icp_text(doc) if icp else actas_scope.ap_text(doc)
        plan.append({
            "source": f"{doc.get('cmg_number', '')} {doc.get('title', '')}".strip(),
            "difficulty": ("easy", "medium", "hard")[i % 3],
            "qualification": "ICP" if icp else "AP",
            "quals": quals,
            "chunk": _chunk(text, rng),
        })
    return plan


def generate_sample(spec: str, plan: list[dict]) -> tuple[list[dict], dict]:
    client, model = make_client(spec)
    meter = Meter()
    rows, failures = [], 0
    for item in plan:
        user = f"Source material:\n\n[Source 1: cmg]\n{item['chunk']}\n\nDifficulty: {item['difficulty']}"
        extra = DIFFICULTY_INSTRUCTIONS.get(item["difficulty"], "")
        if extra:
            user += f"\n\n{extra}"
        try:
            raw = meter.call(client, [
                {"role": "system", "content": build_generation_prompt(item["quals"])},
                {"role": "user", "content": user},
            ])
        except LLMError as exc:
            failures += 1
            rows.append({**item, "question": f"[ERROR] {str(exc)[:120]}", "citation": ""})
            continue
        parsed = _parse_json(raw)
        if not parsed or not parsed.get("question_text"):
            failures += 1
        rows.append({
            **item,
            "question": (parsed or {}).get("question_text") or f"[UNPARSEABLE] {raw[:200]}",
            "citation": (parsed or {}).get("source_citation", ""),
        })
    hashes = [hashlib.sha1(_normalise(r["question"]).encode()).hexdigest()
              for r in rows if not r["question"].startswith(("[ERROR]", "[UNPARSEABLE]"))]
    per_call = cost(model, meter.chars_in, meter.chars_out)
    stats = {
        "model": spec,
        "generated": len(rows) - failures,
        "failures": failures,
        "exact_duplicates": len(hashes) - len(set(hashes)),
        "median_s": round(statistics.median(meter.times), 1) if meter.times else None,
        "usd_per_question": round(per_call / meter.calls, 5) if per_call and meter.calls else None,
    }
    return rows, stats


def write_sample(all_rows: dict[str, list[dict]]) -> None:
    rng = random.Random(7)
    models = list(all_rows)
    codes = {m: f"M{i + 1}" for i, m in enumerate(rng.sample(models, len(models)))}
    rows = []
    for model, items in all_rows.items():
        for item in items:
            rows.append({"model_code": codes[model], **item})
    rng.shuffle(rows)
    with open(OUT_DIR / "question-sample.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row", "model_code", "qualification", "difficulty", "source", "question",
                         "citation", "source_excerpt", "accurate (Y/N)", "in scope (Y/N)",
                         "useful (1-5)", "notes"])
        for i, r in enumerate(rows, 1):
            writer.writerow([i, r["model_code"], r["qualification"], r["difficulty"], r["source"],
                             r["question"], r["citation"], r["chunk"], "", "", "", ""])
    (OUT_DIR / "question-sample-key.json").write_text(json.dumps(codes, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--generate", type=int, default=0, help="questions per model for rating")
    parser.add_argument("--skip-marking", action="store_true")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    marking = []
    if not args.skip_marking:
        for spec in args.models:
            print(f"marking benchmark: {spec} ...", flush=True)
            marking.append(bench_marking(spec))
        header = (f"{'model':30s} {'json':>6s} {'acc':>6s} {'inc':>5s} {'part':>5s} {'corr':>5s} "
                  f"{'fab':>4s} {'grnd':>6s} {'med':>6s} {'max':>6s} {'$/mark':>8s}")
        print("\n" + header + "\n" + "-" * len(header))
        for r in marking:
            if r.get("fatal"):
                print(f"{r['model']:30s} UNUSABLE: {r['fatal'][:80]}")
                continue
            g = r["by_grade"]
            print(f"{r['model']:30s} {r['json']:>6s} {r['accuracy']:>6s} {g['incorrect']:>5s} "
                  f"{g['partial']:>5s} {g['correct']:>5s} {r['fabricated']:>4d} {r['grounded']:>6s} "
                  f"{str(r['median_s']) + 's':>6s} {str(r['max_s']) + 's':>6s} {str(r['usd_per_mark']):>8s}")
            for err in r.get("errors", [])[:3]:
                print(f"    ! {err}")

    generation = []
    if args.generate:
        plan = sample_plan(args.generate)
        all_rows = {}
        for spec in args.models:
            if any(r.get("fatal") and r["model"] == spec for r in marking):
                continue
            print(f"generating {len(plan)} questions: {spec} ...", flush=True)
            rows, stats = generate_sample(spec, plan)
            all_rows[spec] = rows
            generation.append(stats)
            print(f"  {stats}")
        if all_rows:
            write_sample(all_rows)

    (OUT_DIR / "results.json").write_text(json.dumps(
        {"marking": marking, "generation": generation}, indent=2, default=str))
    print(f"\nwrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
