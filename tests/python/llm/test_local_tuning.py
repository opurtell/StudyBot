from __future__ import annotations

import pytest

from llm.local_tuning import (
    GRADING_CALIBRATION,
    grading_calibration_for,
    needs_grading_calibration,
    needs_structured_output,
)
from llm.models import load_model_registry


@pytest.mark.parametrize(
    "model_id",
    ["medgemma-1.5-4b-it", "MedGemma-1.5-4B-IT", "mlx-community/medgemma-1.5-4b-it-4bit"],
)
def test_medgemma_variants_are_recognised(model_id):
    assert needs_grading_calibration(model_id)
    assert needs_structured_output(model_id)
    assert grading_calibration_for(model_id) == GRADING_CALIBRATION


@pytest.mark.parametrize(
    "model_id",
    [
        "openai/gpt-oss-20b",          # the schema costs this model grading accuracy
        "qwen/qwen3.6-35b-a3b",
        "claude-haiku-4-5-20251001",   # hosted models must never be altered
        "gemini-3-flash-preview",
        "glm-4.7-flash",
        "",
    ],
)
def test_other_models_are_left_alone(model_id):
    assert not needs_grading_calibration(model_id)
    assert not needs_structured_output(model_id)
    assert grading_calibration_for(model_id) == ""


def test_calibration_defines_all_three_grades():
    # A supplement that omits a grade is what caused the single-grade collapse.
    for grade in ("incorrect", "partial", "correct"):
        assert f'"{grade}"' in GRADING_CALIBRATION


def test_every_registry_model_resolves_without_error():
    for model_id in load_model_registry()["lmstudio"].values():
        assert isinstance(grading_calibration_for(model_id), str)
