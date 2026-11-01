"""Per-model workarounds for local models served by LM Studio.

Small local models need help that the hosted models do not, and the help is not universal:
constrained decoding rescues `medgemma-1.5-4b-it` but measurably *degrades*
`openai/gpt-oss-20b`. So the adjustments live here, keyed by model, rather than in the
shared prompts where they would reach every provider.

Measured with `scripts/bench-local-models.py`; see CLAUDE.md for the full comparison.
"""

from __future__ import annotations

# Appended to the evaluation system prompt for models that cannot follow the three-grade
# rubric unaided. Untuned, medgemma marks almost every answer "partial" — including
# perfect ones — which is useless for study. Spelling out the rule and showing one worked
# example per grade takes it from 3/10 to 9/10 on the labelled set (6/8 held out).
GRADING_CALIBRATION = """

Additional calibration for this model — apply the scoring rule literally:

- "incorrect" -> nothing the student wrote is supported by the source, OR they contradict
  the source on a clinically critical point (dose, route, position, indication).
- "partial"   -> at least one thing they wrote is supported AND something material is
  wrong or missing. An answer that is right but incomplete is "partial", NOT "incorrect".
- "correct"   -> they cover the source's material points with nothing contradicted.

correct_elements may contain ONLY things the student actually wrote. If they wrote nothing
the source supports it MUST be [] and the score MUST be "incorrect". Never credit them with
something the source says but they did not write.

Worked examples (a different guideline, for calibration only):
Source: "Give oxygen to maintain SpO2 94-98%. Position the patient upright. Transport all patients."
  Answer "Lay the patient flat and withhold oxygen."
    -> {"score": "incorrect", "correct_elements": []}
  Answer "Give oxygen to maintain SpO2 94-98%."
    -> {"score": "partial", "correct_elements": ["Oxygen to maintain SpO2 94-98%"]}
  Answer "Give oxygen for SpO2 94-98%, sit the patient upright, and transport all patients."
    -> {"score": "correct", "correct_elements": ["Oxygen 94-98%", "Upright position", "Transport"]}"""

# Matched as substrings against the model id, which LM Studio namespaces
# (e.g. "medgemma-1.5-4b-it", "openai/gpt-oss-20b").
_NEEDS_CALIBRATION: tuple[str, ...] = ("medgemma",)

# Models that only produce reliable JSON under constrained decoding. Do NOT add a model
# here without measuring: the schema costs gpt-oss-20b four grading points.
_NEEDS_STRUCTURED_OUTPUT: tuple[str, ...] = ("medgemma",)


def _matches(model_id: str, needles: tuple[str, ...]) -> bool:
    lowered = (model_id or "").lower()
    return any(needle in lowered for needle in needles)


def needs_grading_calibration(model_id: str) -> bool:
    """True if this model needs the rubric spelled out to grade across all three grades."""
    return _matches(model_id, _NEEDS_CALIBRATION)


def needs_structured_output(model_id: str) -> bool:
    """True if this model needs a JSON schema to reliably return parseable output."""
    return _matches(model_id, _NEEDS_STRUCTURED_OUTPUT)


def grading_calibration_for(model_id: str) -> str:
    """The evaluation-prompt supplement for this model, or "" if it needs none.

    Hosted models (Anthropic, Google, Z.ai, OpenAI) always get "" — their prompt is
    deliberately left untouched.
    """
    return GRADING_CALIBRATION if needs_grading_calibration(model_id) else ""
