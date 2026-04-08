from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app
from paths import CHROMA_DB_DIR
from settings import router as settings_router

client = TestClient(app)


def test_get_cmg_refresh_status(monkeypatch):
    monkeypatch.setattr(
        settings_router,
        "load_refresh_status",
        lambda: {
            "status": "idle",
            "is_running": False,
            "recommended_cadence": "weekly",
        },
    )

    response = client.get("/settings/cmg-refresh")
    assert response.status_code == 200
    assert response.json()["status"] == "idle"
    assert response.json()["recommended_cadence"] == "weekly"


def test_start_cmg_refresh(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: calls.append("guidelines"))
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: calls.append("medications"))
    monkeypatch.setattr(
        settings_router,
        "start_refresh_in_background",
        lambda: {
            "status": "started",
            "message": "CMG refresh started",
            "started_at": "2026-04-04T12:00:00+00:00",
        },
    )

    response = client.post("/settings/cmg-refresh/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert "started_at" in data
    assert calls == ["guidelines", "medications"]


def test_start_cmg_refresh_returns_conflict(monkeypatch):
    def fail() -> dict:
        raise RuntimeError("CMG refresh already running")

    monkeypatch.setattr(settings_router, "start_refresh_in_background", fail)

    response = client.post("/settings/cmg-refresh/run")
    assert response.status_code == 409
    assert response.json()["detail"] == "CMG refresh already running"


def test_save_settings_persists_api_keys_and_model_selection(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_router, "_SETTINGS_PATH", settings_path)

    payload = {
        "providers": {
            "anthropic": {
                "api_key": "anthropic-key",
                "default_model": "claude-haiku-4-5-20251001",
            },
            "google": {
                "api_key": "google-key",
                "default_model": "gemini-3-flash-preview",
            },
            "zai": {
                "api_key": "zai-key",
                "default_model": "glm-4.7-flash",
            },
        },
        "active_provider": "google",
        "quiz_model": "gemini-2.5-pro",
        "clean_model": "claude-opus-4.6",
        "skill_level": "ICP",
    }

    response = client.put("/settings", json=payload)

    assert response.status_code == 200
    assert json.loads(settings_path.read_text()) == payload


def test_get_settings_uses_cache(monkeypatch):
    calls = {"count": 0}
    settings_router.invalidate_settings_cache()

    def load_once():
        calls["count"] += 1
        return {
            "providers": {
                "anthropic": {"api_key": "", "default_model": "a"},
                "google": {"api_key": "", "default_model": "g"},
                "zai": {"api_key": "", "default_model": "z"},
            },
            "active_provider": "anthropic",
            "quiz_model": "a",
            "clean_model": "a",
            "skill_level": "AP",
        }

    monkeypatch.setattr(settings_router, "load_config", load_once)

    first = client.get("/settings")
    second = client.get("/settings")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1


def test_get_models_uses_cache(monkeypatch):
    calls = {"count": 0}
    settings_router.invalidate_models_cache()

    def load_once():
        calls["count"] += 1
        return {
            "anthropic": {"low": "a1", "medium": "a2", "high": "a3"},
            "google": {"low": "g1", "medium": "g2", "high": "g3"},
            "zai": {"low": "z1", "medium": "z2", "high": "z3"},
        }

    monkeypatch.setattr(settings_router, "load_model_registry", load_once)

    first = client.get("/settings/models")
    second = client.get("/settings/models")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1


def test_clear_vector_store_removes_canonical_chroma_dir(tmp_path, monkeypatch):
    chroma_dir = tmp_path / "chroma_db"
    chroma_dir.mkdir()
    (chroma_dir / "index.bin").write_text("test")
    monkeypatch.setattr(settings_router, "CHROMA_DB_DIR", chroma_dir)

    response = client.post("/settings/vector-store/clear")

    assert response.status_code == 200
    assert response.json() == {"status": "cleared"}
    assert not chroma_dir.exists()


def test_rerun_pipeline_invalidates_read_caches(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: calls.append("guidelines"))
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: calls.append("medications"))
    monkeypatch.setattr(
        settings_router,
        "_run_pipeline_ingest_in_background",
        lambda: calls.append("pipeline"),
    )

    response = client.post("/settings/pipeline/rerun")

    assert response.status_code == 200
    assert response.json() == {"status": "started"}
    assert calls[:2] == ["guidelines", "medications"]


def test_get_cmg_manifest(monkeypatch, tmp_path):
    manifest = {
        "captured_at": "2026-04-07T10:00:00+00:00",
        "source": "cmg.ambulance.act.gov.au",
        "guideline_count": 55,
        "medication_count": 35,
        "clinical_skill_count": 99,
        "pipeline_version": "1",
    }
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    (structured_dir / ".manifest.json").write_text(json.dumps(manifest))

    monkeypatch.setattr(settings_router, "resolve_cmg_structured_dir", lambda: structured_dir)

    response = client.get("/settings/cmg-manifest")
    assert response.status_code == 200
    assert response.json()["captured_at"] == "2026-04-07T10:00:00+00:00"
    assert response.json()["guideline_count"] == 55


def test_get_cmg_manifest_returns_404_when_missing(monkeypatch, tmp_path):
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    monkeypatch.setattr(settings_router, "resolve_cmg_structured_dir", lambda: structured_dir)

    response = client.get("/settings/cmg-manifest")
    assert response.status_code == 404


def test_cmg_rebuild_starts_background_job(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: calls.append("guidelines"))
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: calls.append("medications"))

    def fake_rebuild():
        calls.append("rebuild")

    monkeypatch.setattr(settings_router, "_run_cmg_rebuild_in_background", fake_rebuild)

    response = client.post("/settings/cmg-rebuild")
    assert response.status_code == 200
    assert response.json()["status"] == "started"


def test_rerun_pipeline_starts_both_pipelines(monkeypatch):
    """Re-run Pipeline should trigger both notability notes and personal docs ingestion."""
    commands_run: list[list[str]] = []

    def mock_run(cmd, **kwargs):
        commands_run.append(cmd)

    monkeypatch.setattr(settings_router.subprocess, "run", mock_run)
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: None)
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: None)

    response = client.post("/settings/pipeline/rerun")
    assert response.status_code == 200
    assert response.json()["status"] == "started"

    # Wait for background thread to finish
    import time
    time.sleep(1)

    # Should have run both pipelines
    assert len(commands_run) >= 2
    cmd_strs = [" ".join(c) for c in commands_run]
    assert any("pipeline.run" in c for c in cmd_strs), f"Notability pipeline not found in {cmd_strs}"
    assert any("pipeline.personal_docs.run" in c for c in cmd_strs), f"Personal docs pipeline not found in {cmd_strs}"
