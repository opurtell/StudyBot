import logging
import shutil
import threading
from pathlib import Path

import chromadb

from paths import (
    BUNDLED_CHROMA_DB_DIR,
    bundled_service_chroma_dir,
    CHROMA_DB_DIR,
    CLEANED_NOTES_DIR,
    CONFIG_DIR,
    EXAMPLE_SETTINGS_PATH,
    LOGS_DIR,
    PERSONAL_STRUCTURED_DIR,
    SETTINGS_PATH,
)
from paths import resolve_service_structured_dir

logger = logging.getLogger(__name__)

_seeding_complete = threading.Event()
_seed_status: str = "idle"  # "idle" | "seeding" | "complete" | "failed"


def is_seeding_complete() -> bool:
    return _seeding_complete.is_set()


def get_seed_status() -> dict:
    return {"is_seeding": _seed_status == "seeding", "status": _seed_status}


def seed_user_data() -> None:
    """Run all seed steps: settings, dirs, per-service guidelines, personal data."""
    global _seed_status
    _seed_status = "seeding"
    try:
        _ensure_settings()
        _ensure_dirs()
        for svc in _iter_registry():
            _seed_service_if_needed(svc)
        _seed_personal_data()
        _seed_status = "complete"
    except Exception:
        _seed_status = "failed"
        logger.exception("Seed failed")
        raise
    finally:
        _seeding_complete.set()


# ---------------------------------------------------------------------------
# Service registry helper (lazy import to avoid import errors in tests)
# ---------------------------------------------------------------------------


def _iter_registry():
    """Yield Service objects from the registry.  Returns empty tuple on import failure."""
    try:
        from services.registry import REGISTRY
        return REGISTRY
    except Exception:
        logger.warning("Could not import service registry — falling back to ACTAS-only seed.")
        return ()


def _service_id_from_registry():
    """Fallback: if registry is unavailable, return just ('actas',)."""
    try:
        from services.registry import REGISTRY
        return tuple(s.id for s in REGISTRY)
    except Exception:
        return ("actas",)


# ---------------------------------------------------------------------------
# Settings and directory bootstrap
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Per-service guidelines seeding
# ---------------------------------------------------------------------------


def _guidelines_collection_name(service_id: str) -> str:
    return f"guidelines_{service_id}"


def _personal_collection_name(service_id: str) -> str:
    return f"personal_{service_id}"


_LEGACY_COLLECTION_MAP: dict[str, str] = {
    "guidelines_actas": "cmg_guidelines",
}


def _seed_service_if_needed(service) -> None:
    """Seed the guidelines collection for a single service.

    Checks if ``guidelines_{service.id}`` already has data.  If not:
    1. Try copying from bundled ChromaDB.
    2. Fall back to running the service adapter's chunker.
    """
    global _seed_status
    service_id = service.id
    collection_name = _guidelines_collection_name(service_id)

    if _collection_has_data(CHROMA_DB_DIR, collection_name):
        logger.info("Collection '%s' already has data — skipping seed.", collection_name)
        return

    # Migrate from legacy collection name if present (e.g. cmg_guidelines → guidelines_actas).
    legacy_name = _LEGACY_COLLECTION_MAP.get(collection_name)
    if legacy_name and _collection_has_data(CHROMA_DB_DIR, legacy_name):
        logger.info("Migrating legacy collection '%s' → '%s'.", legacy_name, collection_name)
        if _copy_between_collections(CHROMA_DB_DIR, legacy_name, CHROMA_DB_DIR, collection_name):
            return

    # Try copying from bundled DB (legacy location), checking both new and legacy names.
    for src_name in [collection_name, legacy_name]:
        if src_name and _copy_bundled_collection(src_name, dst_collection_name=collection_name):
            logger.info("Copied '%s' from bundled ChromaDB.", src_name)
            return

    # Try copying from service-scoped bundled ChromaDB, checking both names.
    svc_bundled = bundled_service_chroma_dir(service_id)
    if svc_bundled.exists():
        for src_name in [collection_name, legacy_name]:
            if src_name and _copy_bundled_collection(
                src_name,
                dst_collection_name=collection_name,
                src_db_path=svc_bundled,
            ):
                logger.info("Copied '%s' from service-scoped bundled ChromaDB.", src_name)
                return

    # Fall back to adapter-based ingestion.
    _run_adapter_seed(service)


def _collection_has_data(db_path: Path, collection_name: str) -> bool:
    try:
        client = chromadb.PersistentClient(path=str(db_path))
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            return False
        return collection.count() > 0
    except Exception:
        return False


def _copy_bundled_collection(
    src_collection_name: str,
    dst_collection_name: str | None = None,
    src_db_path: Path | None = None,
) -> bool:
    """Copy a single collection from the bundled ChromaDB to the user ChromaDB."""
    if dst_collection_name is None:
        dst_collection_name = src_collection_name

    db_path = src_db_path or BUNDLED_CHROMA_DB_DIR
    if not db_path.exists():
        return False
    try:
        bundled_client = chromadb.PersistentClient(path=str(db_path))
        src = bundled_client.get_or_create_collection(src_collection_name)
        if src.count() == 0:
            return False

        dst_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        dst = dst_client.get_or_create_collection(dst_collection_name)

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
            "Copied %d chunks from bundled '%s' to user '%s'.",
            src.count(),
            src_collection_name,
            dst_collection_name,
        )
        return True
    except Exception:
        logger.warning(
            "Could not copy '%s' from bundled ChromaDB",
            src_collection_name,
            exc_info=True,
        )
        return False


def _copy_between_collections(
    src_db_path: Path, src_collection_name: str,
    dst_db_path: Path, dst_collection_name: str,
) -> bool:
    """Copy all records from one collection to another (same or different DB)."""
    try:
        src_client = chromadb.PersistentClient(path=str(src_db_path))
        src = src_client.get_collection(src_collection_name)
        if src.count() == 0:
            return False

        dst_client = chromadb.PersistentClient(path=str(dst_db_path))
        dst = dst_client.get_or_create_collection(dst_collection_name)

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
            dst.upsert(
                ids=batch["ids"],
                documents=batch["documents"],
                metadatas=batch["metadatas"],
                embeddings=batch["embeddings"],
            )
            offset += len(batch["ids"])

        logger.info(
            "Migrated %d chunks from '%s' to '%s'.",
            total, src_collection_name, dst_collection_name,
        )
        return True
    except Exception:
        logger.warning("Could not copy '%s' → '%s'", src_collection_name, dst_collection_name, exc_info=True)
        return False


def _run_adapter_seed(service) -> None:
    """Run the service's chunker to seed guidelines data.

    Only ACTAS has an adapter pipeline at this stage.  Other services
    are skipped with a log message (AT will be added in Plan B).
    """
    service_id = service.id
    adapter = service.adapter

    if "actas" in adapter:
        try:
            from pipeline.actas.chunker import chunk_and_ingest as actas_chunk_and_ingest

            structured_dir = str(resolve_service_structured_dir(service_id))
            logger.info("Auto-seeding guidelines_%s from %s via adapter.", service_id, structured_dir)
            actas_chunk_and_ingest(structured_dir=structured_dir)
            logger.info("guidelines_%s auto-seed complete.", service_id)
        except Exception:
            logger.exception("Failed to seed guidelines_%s via ACTAS adapter.", service_id)
    else:
        logger.info(
            "No adapter pipeline for service '%s' — skipping guideline seed. "
            "Adapter will be available after Plan B implementation.",
            service_id,
        )


# ---------------------------------------------------------------------------
# Personal data seeding (notability notes + REF/CPD docs)
# ---------------------------------------------------------------------------


def _seed_personal_data() -> None:
    """Seed personal collections for each registered service.

    For each service, check if ``personal_{service.id}`` exists and has data.
    If not, run notability notes ingestion and personal docs ingestion.
    """
    for service_id in _service_id_from_registry():
        collection_name = _personal_collection_name(service_id)

        if _collection_has_data(CHROMA_DB_DIR, collection_name):
            logger.info("Collection '%s' already has data — skipping.", collection_name)
            continue

        # Try copying from bundled DB first.
        if _copy_bundled_collection("paramedic_notes", dst_collection_name=collection_name):
            logger.info("Copied personal data to '%s' from bundled ChromaDB.", collection_name)
            continue

        _run_notability_notes_ingest(service_id)
        _run_personal_docs_ingest(service_id)


def _run_notability_notes_ingest(service_id: str) -> None:
    if not CLEANED_NOTES_DIR.exists():
        return
    md_files = list(CLEANED_NOTES_DIR.rglob("*.md"))
    if not md_files:
        return
    collection_name = _personal_collection_name(service_id)
    logger.info(
        "Auto-seeding notability notes from %s (%d files) into '%s'.",
        CLEANED_NOTES_DIR,
        len(md_files),
        collection_name,
    )
    try:
        from pipeline.chunker import chunk_and_ingest

        for md_path in md_files:
            try:
                chunk_and_ingest(md_path, CHROMA_DB_DIR, collection_name=collection_name)
            except Exception:
                logger.warning("Failed to ingest %s", md_path.name)
    except Exception:
        logger.exception("Notability notes auto-seed failed")


def _run_personal_docs_ingest(service_id: str) -> None:
    if not PERSONAL_STRUCTURED_DIR.exists():
        return
    collection_name = _personal_collection_name(service_id)
    try:
        from pipeline.personal_docs.chunker import chunk_and_ingest as pd_chunk_and_ingest

        # Monkey-patch the collection name by passing it through the ingestion path.
        # chunk_and_ingest reads service from front-matter and derives collection name.
        # We pass the target collection via a wrapper.
        _ingest_personal_docs_with_collection(
            pd_chunk_and_ingest, PERSONAL_STRUCTURED_DIR, CHROMA_DB_DIR, collection_name,
        )
    except Exception:
        logger.exception("Personal docs auto-seed failed")


def _ingest_personal_docs_with_collection(
    chunk_fn,
    structured_dir: Path,
    db_path: Path,
    collection_name: str,
) -> None:
    """Ingest personal docs into a specific collection.

    The personal_docs chunker derives collection name from front-matter.
    This wrapper overrides the collection name when front-matter is missing
    the service key (legacy files).
    """
    for subdir in ["REFdocs", "CPDdocs"]:
        dir_path = structured_dir / subdir
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            try:
                chunk_fn(md_file, db_path, collection_name=collection_name)
            except Exception as e:
                logger.warning("Failed to ingest %s: %s", md_file.name, e)


# ---------------------------------------------------------------------------
# Legacy compatibility: background seeding thread for FastAPI lifespan
# ---------------------------------------------------------------------------


def _start_cmg_seed_if_needed() -> None:
    """DEPRECATED: Use seed_user_data() instead.  Kept for backward compat."""
    global _seed_status

    # Check both legacy and new collection names.
    has_data = (
        _collection_has_data(CHROMA_DB_DIR, "cmg_guidelines")
        or _collection_has_data(CHROMA_DB_DIR, "guidelines_actas")
    )
    if has_data:
        _seed_status = "complete"
        _seeding_complete.set()
        return

    # Try copying pre-built bundled ChromaDB (from packaged app).
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
    try:
        bundled_client = chromadb.PersistentClient(path=str(BUNDLED_CHROMA_DB_DIR))
        has_data = False
        for name in ("guidelines_actas", "cmg_guidelines"):
            try:
                if bundled_client.get_collection(name).count() > 0:
                    has_data = True
                    break
            except Exception:
                continue
        if not has_data:
            return False
    except Exception:
        logger.warning("Bundled chroma_db exists but could not be read")
        return False

    logger.info("Copying bundled ChromaDB from %s to %s", BUNDLED_CHROMA_DB_DIR, CHROMA_DB_DIR)
    try:
        CHROMA_DB_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(BUNDLED_CHROMA_DB_DIR), str(CHROMA_DB_DIR), dirs_exist_ok=True)
        # Migrate legacy collection name if present.
        _migrate_legacy_collection(CHROMA_DB_DIR, "cmg_guidelines", "guidelines_actas")
        return True
    except Exception:
        logger.exception("Failed to copy bundled ChromaDB")
        return False


def _migrate_legacy_collection(db_path: Path, old_name: str, new_name: str) -> None:
    """If old_name collection exists with data and new_name doesn't, copy data over."""
    try:
        client = chromadb.PersistentClient(path=str(db_path))
        try:
            old_col = client.get_collection(old_name)
        except Exception:
            return
        if old_col.count() == 0:
            return
        try:
            client.get_collection(new_name)
            return  # new name already exists
        except Exception:
            pass
        _copy_between_collections(db_path, old_name, db_path, new_name)
    except Exception:
        logger.warning("Legacy collection migration '%s' → '%s' failed", old_name, new_name, exc_info=True)


def _seed_cmg_index() -> None:
    from pipeline.actas.chunker import chunk_and_ingest

    structured_dir = str(resolve_service_structured_dir("actas"))
    logger.info("Auto-seeding CMG index from %s", structured_dir)
    chunk_and_ingest(structured_dir=structured_dir)
    logger.info("CMG auto-seed complete")
