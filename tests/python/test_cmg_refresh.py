from __future__ import annotations

import json

import pytest

from pipeline.cmg import refresh
from pipeline.cmg.version_tracker import update_version_tracking


def test_update_version_tracking_reports_state_changes(tmp_path):
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    tracking_csv = tmp_path / "version_tracking.csv"

    baseline = {
        "id": "CMG_1_General_Care",
        "title": "General Care",
        "content_markdown": "# General Care\n\nInitial content",
        "checksum": "aaa",
    }
    with open(structured_dir / "CMG_1_General_Care.json", "w", encoding="utf-8") as f:
        json.dump(baseline, f)

    first = update_version_tracking(
        structured_dir=str(structured_dir),
        tracking_csv=str(tracking_csv),
    )
    assert first["checked_item_count"] == 1
    assert first["new_count"] == 1
    assert first["updated_count"] == 0
    assert first["unchanged_count"] == 0

    updated = {**baseline, "checksum": "bbb"}
    with open(structured_dir / "CMG_1_General_Care.json", "w", encoding="utf-8") as f:
        json.dump(updated, f)

    second = update_version_tracking(
        structured_dir=str(structured_dir),
        tracking_csv=str(tracking_csv),
    )
    assert second["checked_item_count"] == 1
    assert second["new_count"] == 0
    assert second["updated_count"] == 1
    assert second["unchanged_count"] == 0

    third = update_version_tracking(
        structured_dir=str(structured_dir),
        tracking_csv=str(tracking_csv),
    )
    assert third["checked_item_count"] == 1
    assert third["new_count"] == 0
    assert third["updated_count"] == 0
    assert third["unchanged_count"] == 1


def test_load_refresh_status_defaults_when_missing(tmp_path):
    status = refresh.load_refresh_status(tmp_path / "missing.json")
    assert status["status"] == "idle"
    assert status["is_running"] is False
    assert status["recommended_cadence"] == "weekly"
    assert status["summary"] is None


def test_run_refresh_persists_success_status_and_history(monkeypatch, tmp_path):
    status_path = tmp_path / "refresh_status.json"
    history_path = tmp_path / "refresh_history.json"

    calls: list[str] = []

    def fake_run_pipeline(
        *, stages: str, dry_run: bool, investigation_dir: str
    ) -> dict:
        calls.append(f"pipeline:{stages}:{dry_run}:{investigation_dir}")
        return {
            "version_summary": {
                "checked_item_count": 3,
                "new_count": 1,
                "updated_count": 1,
                "unchanged_count": 1,
                "error_count": 0,
                "items": [],
            }
        }

    monkeypatch.setattr(refresh, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        refresh,
        "invalidate_guideline_cache",
        lambda: calls.append("invalidate-guidelines"),
    )
    monkeypatch.setattr(
        refresh,
        "invalidate_medication_cache",
        lambda: calls.append("invalidate-medications"),
    )

    result = refresh.run_refresh(
        dry_run=True,
        skip_capture=True,
        investigation_dir="tmp/investigation",
        status_path=status_path,
        history_path=history_path,
    )

    assert calls[0] == "pipeline:all:True:tmp/investigation"
    assert result["status"] == "succeeded"
    assert result["is_running"] is False
    assert result["last_successful_at"] == result["last_completed_at"]
    assert result["summary"]["checked_item_count"] == 3
    assert result["summary"]["new_count"] == 1
    assert result["summary"]["updated_count"] == 1
    assert result["summary"]["unchanged_count"] == 1
    assert result["summary"]["dry_run"] is True
    assert result["summary"]["skip_capture"] is True
    assert calls[-2:] == ["invalidate-guidelines", "invalidate-medications"]

    persisted_status = refresh.load_refresh_status(status_path)
    assert persisted_status["status"] == "succeeded"
    assert persisted_status["summary"]["checked_item_count"] == 3

    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    assert len(history) == 1
    assert history[0]["status"] == "succeeded"


def test_run_refresh_preserves_last_successful_time_on_failure(monkeypatch, tmp_path):
    status_path = tmp_path / "refresh_status.json"
    history_path = tmp_path / "refresh_history.json"

    refresh._write_json(
        status_path,
        {
            "status": "succeeded",
            "is_running": False,
            "last_started_at": "2026-04-04T00:00:00+00:00",
            "last_completed_at": "2026-04-04T00:05:00+00:00",
            "last_successful_at": "2026-04-04T00:05:00+00:00",
            "trigger": "manual",
            "recommended_cadence": "weekly",
            "summary": {"checked_item_count": 1},
            "last_error": None,
        },
    )

    def fake_run_pipeline(
        *, stages: str, dry_run: bool, investigation_dir: str
    ) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(refresh, "run_pipeline", fake_run_pipeline)

    with pytest.raises(RuntimeError, match="boom"):
        refresh.run_refresh(
            skip_capture=True,
            investigation_dir="tmp/investigation",
            status_path=status_path,
            history_path=history_path,
        )

    persisted_status = refresh.load_refresh_status(status_path)
    assert persisted_status["status"] == "failed"
    assert persisted_status["is_running"] is False
    assert persisted_status["last_successful_at"] == "2026-04-04T00:05:00+00:00"
    assert persisted_status["last_error"] == "boom"

    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    assert history[-1]["status"] == "failed"
    assert history[-1]["last_error"] == "boom"


def test_generate_manifest_creates_file(tmp_path):
    from pipeline.cmg.version_tracker import generate_manifest

    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    (structured_dir / "med").mkdir()
    (structured_dir / "csm").mkdir()

    with open(structured_dir / "CMG_1.json", "w") as f:
        json.dump({"id": "CMG_1", "title": "Test"}, f)
    with open(structured_dir / "med" / "MED_1.json", "w") as f:
        json.dump({"id": "MED_1", "title": "Med"}, f)
    with open(structured_dir / "csm" / "CSM_1.json", "w") as f:
        json.dump({"id": "CSM_1", "title": "Skill"}, f)
    with open(structured_dir / "guidelines-index.json", "w") as f:
        json.dump({"items": []}, f)

    generate_manifest(structured_dir=str(structured_dir))

    manifest_path = structured_dir / ".manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert "captured_at" in manifest
    assert manifest["guideline_count"] == 1
    assert manifest["medication_count"] == 1
    assert manifest["clinical_skill_count"] == 1
