from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm.factory import load_config
from llm.models import load_model_registry, save_model_registry
from guidelines.router import invalidate_guideline_cache
from medication.router import invalidate_medication_cache
from pipeline.cmg.refresh import load_refresh_status, start_refresh_in_background
from paths import CHROMA_DB_DIR, SETTINGS_PATH as _SETTINGS_PATH
from paths import resolve_cmg_structured_dir

router = APIRouter(prefix="/settings", tags=["settings"])
_settings_cache: dict | None = None
_models_cache: dict | None = None
_cache_lock = threading.Lock()


def _invalidate_read_caches() -> None:
    invalidate_guideline_cache()
    invalidate_medication_cache()


def _run_pipeline_ingest_in_background() -> None:
    try:
        subprocess.run(
            ["python3", "-m", "pipeline.run", "ingest"],
            cwd=str(Path(__file__).resolve().parent.parent),
            check=False,
        )
    finally:
        _invalidate_read_caches()


def _clone_dict(data: dict) -> dict:
    return json.loads(json.dumps(data))


def invalidate_settings_cache() -> None:
    global _settings_cache
    with _cache_lock:
        _settings_cache = None


def invalidate_models_cache() -> None:
    global _models_cache
    with _cache_lock:
        _models_cache = None


class ProviderConfig(BaseModel):
    api_key: str = ""
    default_model: str = ""


class SaveSettingsRequest(BaseModel):
    providers: dict[str, ProviderConfig]
    active_provider: str
    quiz_model: str
    clean_model: str
    skill_level: str = "AP"


class ModelTier(BaseModel):
    low: str
    medium: str
    high: str


class SaveModelsRequest(BaseModel):
    anthropic: ModelTier
    google: ModelTier
    zai: ModelTier


@router.get("")
def get_settings() -> dict:
    global _settings_cache
    with _cache_lock:
        if _settings_cache is not None:
            return _clone_dict(_settings_cache)
    try:
        loaded = load_config()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    with _cache_lock:
        _settings_cache = _clone_dict(loaded)
    return loaded


@router.put("")
def save_settings(req: SaveSettingsRequest) -> dict:
    global _settings_cache
    config = req.model_dump()
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    with _cache_lock:
        _settings_cache = _clone_dict(config)
    return {"status": "ok"}


@router.get("/models")
def get_models() -> dict:
    global _models_cache
    with _cache_lock:
        if _models_cache is not None:
            return _clone_dict(_models_cache)
    loaded = load_model_registry()
    with _cache_lock:
        _models_cache = _clone_dict(loaded)
    return loaded


@router.put("/models")
def save_models(req: SaveModelsRequest) -> dict:
    global _models_cache
    registry = req.model_dump()
    try:
        save_model_registry(registry)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    with _cache_lock:
        _models_cache = _clone_dict(registry)
    return {"status": "ok"}


@router.post("/pipeline/rerun")
def rerun_pipeline() -> dict:
    _invalidate_read_caches()
    thread = threading.Thread(target=_run_pipeline_ingest_in_background, daemon=True)
    thread.start()
    return {"status": "started"}


@router.get("/cmg-refresh")
def get_cmg_refresh_status() -> dict:
    return load_refresh_status()


@router.post("/cmg-refresh/run")
def run_cmg_refresh() -> dict:
    try:
        _invalidate_read_caches()
        return start_refresh_in_background()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/cmg-manifest")
def get_cmg_manifest() -> dict:
    structured_dir = resolve_cmg_structured_dir()
    manifest_path = structured_dir / ".manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="No CMG manifest found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_cmg_rebuild_in_background() -> None:
    try:
        from pipeline.cmg.chunker import chunk_and_ingest
        chunk_and_ingest(structured_dir=str(resolve_cmg_structured_dir()))
    finally:
        _invalidate_read_caches()


@router.post("/cmg-rebuild")
def rebuild_cmg_index() -> dict:
    _invalidate_read_caches()
    thread = threading.Thread(target=_run_cmg_rebuild_in_background, daemon=True)
    thread.start()
    return {"status": "started"}


@router.post("/vector-store/clear")
def clear_vector_store() -> dict:
    if CHROMA_DB_DIR.exists():
        shutil.rmtree(CHROMA_DB_DIR)
    return {"status": "cleared"}
