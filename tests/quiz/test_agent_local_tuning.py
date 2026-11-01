"""The evaluation prompt must stay untouched for every model except the ones that need help."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from llm.local_tuning import GRADING_CALIBRATION
from quiz.agent import EVALUATION_SCHEMA, EVALUATION_SYSTEM_PROMPT, evaluate_answer
from quiz.models import Question, RetrievedChunk

_REPLY = json.dumps(
    {
        "score": "partial",
        "correct_elements": ["a"],
        "missing_or_wrong": ["b"],
        "source_quote": "quote",
        "feedback_summary": "summary",
    }
)


def _question() -> Question:
    return Question(
        id="q1",
        question_text="What is the dose?",
        question_type="drug_dose",
        source_chunks=[
            RetrievedChunk(
                content="Adrenaline 0.5 mg IM.",
                source_type="cmg",
                source_file="cmg_29.json",
                source_rank=0,
                category="Allergy",
                relevance_score=0.9,
            )
        ],
        source_citation="ACTAS CMG 29",
        difficulty="medium",
        category="Cardiac",
        primary_chunk_index=0,
    )


def _evaluate(model_id: str | None):
    llm = MagicMock()
    llm.complete.return_value = _REPLY
    if model_id is None:
        del llm.get_model  # a hosted client exposes no model hint
    else:
        llm.get_model.return_value = model_id
    evaluate_answer(
        question=_question(), user_answer="0.5 mg", llm=llm, elapsed_seconds=1.0
    )
    return llm.complete.call_args


def test_medgemma_receives_the_calibration_supplement():
    args, kwargs = _evaluate("medgemma-1.5-4b-it")
    system = args[0][0]["content"]
    assert system.startswith(EVALUATION_SYSTEM_PROMPT)
    assert GRADING_CALIBRATION in system


@pytest.mark.parametrize("model_id", ["openai/gpt-oss-20b", "qwen/qwen3.6-35b-a3b"])
def test_other_local_models_get_the_prompt_unchanged(model_id):
    args, _ = _evaluate(model_id)
    assert args[0][0]["content"] == EVALUATION_SYSTEM_PROMPT


def test_hosted_client_without_model_hint_gets_the_prompt_unchanged():
    args, _ = _evaluate(None)
    assert args[0][0]["content"] == EVALUATION_SYSTEM_PROMPT


def test_schema_is_always_offered_and_the_provider_decides():
    _, kwargs = _evaluate("openai/gpt-oss-20b")
    assert kwargs["response_schema"] == EVALUATION_SCHEMA


def test_schema_enumerates_the_three_grades():
    assert EVALUATION_SCHEMA["properties"]["score"]["enum"] == [
        "correct",
        "partial",
        "incorrect",
    ]
