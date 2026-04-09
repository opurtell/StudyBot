import logging
import shutil
import threading
from pathlib import Path

import chromadb

from paths import (
    BUNDLED_CHROMA_DB_DIR,
    CHROMA_DB_DIR,
    CLEANED_NOTES_DIR,
    CMG_STRUCTURED_DIR,
    CONFIG_DIR,
    EXAMPLE_SETTINGS_PATH,
    LOGS_DIR,
    PERSONAL_STRUCTURED_DIR,
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
    _start_paramedic_notes_seed_if_needed()


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
        shutil.copytree(str(BUNDLED_CHROMA_DB_DIR), str(CHROMA_DB_DIR), dirs_exist_ok=True)
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


def _start_paramedic_notes_seed_if_needed() -> None:
    if _paramedic_notes_collection_has_data():
        return

    # Try copying paramedic_notes from bundled DB if available
    if _copy_bundled_collection("paramedic_notes"):
        return

    _run_notability_notes_ingest(CHROMA_DB_DIR)
    _run_personal_docs_ingest(CHROMA_DB_DIR)


def _paramedic_notes_collection_has_data() -> bool:
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_or_create_collection("paramedic_notes")
        return collection.count() > 0
    except Exception:
        return False


def _copy_bundled_collection(collection_name: str) -> bool:
    """Copy a single collection from the bundled ChromaDB to the user ChromaDB."""
    if not BUNDLED_CHROMA_DB_DIR.exists():
        return False
    try:
        bundled_client = chromadb.PersistentClient(path=str(BUNDLED_CHROMA_DB_DIR))
        src = bundled_client.get_or_create_collection(collection_name)
        if src.count() == 0:
            return False

        dst_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        dst = dst_client.get_or_create_collection(collection_name)

        batch_size = 500
        total = src.count()
        offset = 0
        while offset < total:
            batch = src.get(
                include=["documents", "metadatas", "embeddings"],
                limit=batch_size,
                offset=offset,
            )
            if not batch["ids"]:
                break
            dst.add(
                ids=batch["ids"],
                documents=batch["documents"],
                metadatas=batch["metadatas"],
                embeddings=batch["embeddings"],
            )
            offset += len(batch["ids"])

        logger.info(
            f"Copied {src.count()} chunks from bundled '{collection_name}' to user ChromaDB"
        )
        return True
    except Exception:
        logger.warning(f"Could not copy '{collection_name}' from bundled ChromaDB", exc_info=True)
        return False


def _run_notability_notes_ingest(db_path: Path) -> None:
    if not CLEANED_NOTES_DIR.exists():
        return
    md_files = list(CLEANED_NOTES_DIR.rglob("*.md"))
    if not md_files:
        return
    logger.info(f"Auto-seeding notability notes from {CLEANED_NOTES_DIR} ({len(md_files)} files)")
    try:
        from pipeline.chunker import chunk_and_ingest

        for md_path in md_files:
            try:
                chunk_and_ingest(md_path, db_path)
            except Exception:
                logger.warning(f"Failed to ingest {md_path.name}")
    except Exception:
        logger.exception("Notability notes auto-seed failed")


def _run_personal_docs_ingest(db_path: Path) -> None:
    if not PERSONAL_STRUCTURED_DIR.exists():
        return
    try:
        from pipeline.personal_docs.chunker import chunk_and_ingest_directory

        result = chunk_and_ingest_directory(PERSONAL_STRUCTURED_DIR, db_path)
        logger.info(
            f"Personal docs auto-seed: {result['processed']} files, {result['total_chunks']} chunks"
        )
    except Exception:
        logger.exception("Personal docs auto-seed failed")
