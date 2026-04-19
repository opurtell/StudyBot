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
    import types
    from services import registry

    calls: list[str] = []
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: calls.append("guidelines"))
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: calls.append("medications"))

    fake_adapter = types.ModuleType("src.python.pipeline.actas")
    fake_adapter.run_pipeline = lambda **kwargs: calls.append("pipeline")  # type: ignore[attr-defined]

    actas_service = registry.get_service("actas")
    monkeypatch.setattr(settings_router, "active_service", lambda: actas_service)
    monkeypatch.setattr(settings_router.importlib, "import_module", lambda name: fake_adapter)

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


def test_rerun_pipeline_calls_adapter_run_pipeline(monkeypatch):
    """POST /settings/pipeline/rerun should call the active service adapter's run_pipeline in a background thread."""
    import types
    import time
    from services import registry

    calls: list[str] = []

    fake_adapter = types.ModuleType("src.python.pipeline.actas")
    fake_adapter.run_pipeline = lambda **kwargs: calls.append("run_pipeline")  # type: ignore[attr-defined]

    actas_service = registry.get_service("actas")
    monkeypatch.setattr(settings_router, "active_service", lambda: actas_service)
    monkeypatch.setattr(settings_router.importlib, "import_module", lambda name: fake_adapter)
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: None)
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: None)

    response = client.post("/settings/pipeline/rerun")
    assert response.status_code == 200
    assert response.json()["status"] == "started"

    # Allow background thread to finish
    time.sleep(0.2)

    assert "run_pipeline" in calls, f"adapter run_pipeline was not called; calls={calls}"


# ---------------------------------------------------------------------------
# Task 8b: active_service() + importlib routing for /settings/pipeline/rerun
# ---------------------------------------------------------------------------

def test_rerun_pipeline_actas(monkeypatch):
    """POST /settings/pipeline/rerun with ACTAS active service should call the ACTAS adapter's run_pipeline."""
    import types
    from services import registry

    calls: list[str] = []

    # Build a minimal fake actas adapter module with run_pipeline
    fake_actas = types.ModuleType("src.python.pipeline.actas")
    fake_actas.run_pipeline = lambda **kwargs: calls.append("actas_run_pipeline")  # type: ignore[attr-defined]

    actas_service = registry.get_service("actas")

    monkeypatch.setattr(settings_router, "active_service", lambda: actas_service)
    monkeypatch.setattr(settings_router.importlib, "import_module", lambda name: fake_actas)
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: None)
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: None)

    response = client.post("/settings/pipeline/rerun")

    assert response.status_code == 200
    assert response.json() == {"status": "started"}

    # Allow background thread to finish
    import time
    time.sleep(0.2)

    assert "actas_run_pipeline" in calls, "ACTAS adapter run_pipeline was not called"


def test_rerun_pipeline_unimplemented_service(monkeypatch):
    """POST /settings/pipeline/rerun with a service whose adapter lacks run_pipeline returns 409."""
    import types
    from services import registry

    # Build a fake AT adapter module with NO run_pipeline attribute
    fake_at = types.ModuleType("src.python.pipeline.at")

    at_service = registry.get_service("at")

    monkeypatch.setattr(settings_router, "active_service", lambda: at_service)
    monkeypatch.setattr(settings_router.importlib, "import_module", lambda name: fake_at)
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: None)
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: None)

    response = client.post("/settings/pipeline/rerun")

    assert response.status_code == 409
    assert response.json() == {"error": "adapter not ready"}
