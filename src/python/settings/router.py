from __future__ import annotations

import importlib
import json
import shutil
import threading
from pathlib import Path

import chromadb
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from llm.factory import load_config
from llm.models import load_model_registry, save_model_registry
from guidelines.router import invalidate_guideline_cache
from medication.router import invalidate_medication_cache
from pipeline.actas.refresh import load_refresh_status, start_refresh_in_background
from paths import CHROMA_DB_DIR, SETTINGS_PATH as _SETTINGS_PATH
from paths import resolve_cmg_structured_dir
from seed import get_seed_status as _get_seed_status
from services.active import active_service

router = APIRouter(prefix="/settings", tags=["settings"])
_settings_cache: dict | None = None
_models_cache: dict | None = None
_cache_lock = threading.Lock()
_rebuild_status: dict = {"is_running": False, "status": "idle", "last_completed_at": None}
_rebuild_lock = threading.Lock()


def _invalidate_read_caches() -> None:
    invalidate_guideline_cache()
    invalidate_medication_cache()


def _run_pipeline_ingest_in_background(adapter_module_path: str) -> None:
    try:
        adapter = importlib.import_module(adapter_module_path)
        adapter.run_pipeline()
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
    vision_model: str = ""
    base_qualification: str = "AP"
    endorsements: list[str] = []


class ModelTier(BaseModel):
    low: str
    medium: str
    high: str


class SaveModelsRequest(BaseModel):
    anthropic: ModelTier
    google: ModelTier
    zai: ModelTier
    openai: ModelTier


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


@router.post("/pipeline/rerun", response_model=None)
def rerun_pipeline() -> dict | JSONResponse:
    service = active_service()
    try:
        adapter = importlib.import_module(service.adapter)
    except ImportError:
        return JSONResponse(status_code=409, content={"error": "adapter not ready"})

    if not hasattr(adapter, "run_pipeline"):
        return JSONResponse(status_code=409, content={"error": "adapter not ready"})

    _invalidate_read_caches()
    thread = threading.Thread(
        target=_run_pipeline_ingest_in_background,
        args=(service.adapter,),
        daemon=True,
    )
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
    global _rebuild_status
    try:
        from pipeline.actas.chunker import chunk_and_ingest
        chunk_and_ingest(structured_dir=str(resolve_cmg_structured_dir()))
        with _rebuild_lock:
            _rebuild_status = {
                "is_running": False,
                "status": "complete",
                "last_completed_at": __import__("datetime").datetime.utcnow().isoformat(),
            }
    except Exception:
        with _rebuild_lock:
            _rebuild_status = {
                "is_running": False,
                "status": "failed",
                "last_completed_at": _rebuild_status.get("last_completed_at"),
            }
    finally:
        _invalidate_read_caches()


@router.post("/cmg-rebuild")
def rebuild_cmg_index() -> dict:
    global _rebuild_status
    with _rebuild_lock:
        if _rebuild_status["is_running"]:
            raise HTTPException(status_code=409, detail="Rebuild already in progress")
        _invalidate_read_caches()
        _rebuild_status = {"is_running": True, "status": "running", "last_completed_at": _rebuild_status.get("last_completed_at")}
    thread = threading.Thread(target=_run_cmg_rebuild_in_background, daemon=True)
    thread.start()
    return {"status": "started"}


@router.get("/cmg-rebuild-status")
def get_cmg_rebuild_status() -> dict:
    with _rebuild_lock:
        return dict(_rebuild_status)


@router.get("/seed-status")
def get_seed_status() -> dict:
    return _get_seed_status()


@router.get("/vector-store/status")
def vector_store_status() -> dict:
    """Return chunk counts per source type across all collections."""
    if not CHROMA_DB_DIR.exists():
        return {"cmg": 0, "ref_doc": 0, "cpd_doc": 0, "notability_note": 0}

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    counts: dict[str, int] = {"cmg": 0, "ref_doc": 0, "cpd_doc": 0, "notability_note": 0}

    try:
        cmg_col = client.get_or_create_collection("cmg_guidelines")
        counts["cmg"] = cmg_col.count()
    except Exception:
        pass

    try:
        notes_col = client.get_or_create_collection("paramedic_notes")
        for st in ("ref_doc", "cpd_doc", "notability_note"):
            result = notes_col.get(where={"source_type": st})
            counts[st] = len(result["ids"])
    except Exception:
        pass

    return counts


@router.post("/vector-store/clear")
def clear_vector_store(source_type: str | None = None) -> dict:
    """Clear indexed data. Optional source_type for selective clearing."""
    if source_type is None:
        # Nuclear option: delete entire ChromaDB directory
        if CHROMA_DB_DIR.exists():
            shutil.rmtree(CHROMA_DB_DIR)
        _invalidate_read_caches()
        return {"status": "cleared"}

    valid_types = ("cmg", "ref_doc", "cpd_doc", "notability_note")
    if source_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Must be one of: {', '.join(valid_types)}",
        )

    if not CHROMA_DB_DIR.exists():
        return {"status": "cleared", "source_type": source_type}

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    if source_type == "cmg":
        try:
            client.delete_collection("cmg_guidelines")
        except Exception:
            pass
    else:
        # Clear from paramedic_notes collection by source_type metadata
        try:
            notes_col = client.get_or_create_collection("paramedic_notes")
            notes_col.delete(where={"source_type": source_type})
        except Exception:
            pass

    _invalidate_read_caches()
    return {"status": "cleared", "source_type": source_type}
