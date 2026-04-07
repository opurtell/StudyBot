import logging
import shutil
import threading
from pathlib import Path

import chromadb

from paths import (
    BUNDLED_CHROMA_DB_DIR,
    CHROMA_DB_DIR,
    CMG_STRUCTURED_DIR,
    CONFIG_DIR,
    EXAMPLE_SETTINGS_PATH,
    LOGS_DIR,
    SETTINGS_PATH,
)
from paths import resolve_cmg_structured_dir

logger = logging.getLogger(__name__)

_seeding_complete = threading.Event()
_seed_status: str = "idle"  # "idle" | "seeding" | "complete" | "failed"


def is_seeding_complete() -> bool:
    return _seeding_complete.is_set()


def get_seed_status() -> dict:
    return {"is_seeding": _seed_status == "seeding", "status": _seed_status}


def seed_user_data() -> None:
    _ensure_settings()
    _ensure_dirs()
    _start_cmg_seed_if_needed()


def _ensure_settings() -> None:
    if SETTINGS_PATH.exists():
        return
    if not EXAMPLE_SETTINGS_PATH.exists():
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXAMPLE_SETTINGS_PATH, SETTINGS_PATH)


def _ensure_dirs() -> None:
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _start_cmg_seed_if_needed() -> None:
    global _seed_status
    if _cmg_collection_has_data():
        _seed_status = "complete"
        _seeding_complete.set()
        return

    # Try copying pre-built bundled ChromaDB (from packaged app)
    if _copy_bundled_chroma_db():
        _seed_status = "complete"
        _seeding_complete.set()
        return

    _seed_status = "seeding"

    def _seed() -> None:
        global _seed_status
        try:
            _seed_cmg_index()
            _seed_status = "complete"
        except Exception:
            _seed_status = "failed"
            logger.exception("CMG auto-seed failed")
        finally:
            _seeding_complete.set()

    threading.Thread(target=_seed, daemon=True, name="cmg-auto-seed").start()


def _copy_bundled_chroma_db() -> bool:
    """Copy pre-built ChromaDB from bundled app resources to user data dir."""
    if not BUNDLED_CHROMA_DB_DIR.exists():
        return False
    # Check the bundled DB actually has data
    try:
        bundled_client = chromadb.PersistentClient(path=str(BUNDLED_CHROMA_DB_DIR))
        collection = bundled_client.get_or_create_collection("cmg_guidelines")
        if collection.count() == 0:
            return False
    except Exception:
        logger.warning("Bundled chroma_db exists but could not be read")
        return False

    logger.info(f"Copying bundled ChromaDB from {BUNDLED_CHROMA_DB_DIR} to {CHROMA_DB_DIR}")
    try:
        CHROMA_DB_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(BUNDLED_CHROMA_DB_DIR), str(CHROMA_DB_DIR))
        return True
    except Exception:
        logger.exception("Failed to copy bundled ChromaDB")
        return False


def _cmg_collection_has_data() -> bool:
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_or_create_collection("cmg_guidelines")
        return collection.count() > 0
    except Exception:
        return False


def _seed_cmg_index() -> None:
    from pipeline.cmg.chunker import chunk_and_ingest

    structured_dir = str(resolve_cmg_structured_dir())
    logger.info(f"Auto-seeding CMG index from {structured_dir}")
    chunk_and_ingest(structured_dir=structured_dir)
    logger.info("CMG auto-seed complete")
