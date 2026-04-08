"""Upload router — accept user documents, convert, structure, and ingest into ChromaDB."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from paths import UPLOADS_DIR, UPLOADS_STRUCTURED_DIR, CHROMA_DB_DIR
from upload.extractor import extract_text, SUPPORTED_EXTENSIONS
from pipeline.personal_docs.chunker import chunk_and_ingest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    filename: str
    status: str  # "processed" | "failed"
    chunks: int
    categories: list[str]
    source_type: str
    error: str | None = None


class AcceptedFormatsResponse(BaseModel):
    extensions: list[str]
    max_size_mb: int


MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return Path(fallback).stem


def _structure_and_ingest(
    text: str,
    filename: str,
    uploads_dir: Path,
    structured_dir: Path,
    db_path: Path,
) -> UploadResponse:
    """Add YAML front matter and ingest into ChromaDB.

    Uses source_type 'cpd_doc' for user uploads (tier 3, same as CPD docs).
    """
    title = _extract_title(text, filename)
    source_file = f"uploads/{filename}"
    source_type = "cpd_doc"
    categories = ["General Paramedicine"]
    last_modified = datetime.now(tz=timezone.utc).isoformat()

    # Save raw uploaded file
    raw_dir = uploads_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / filename).write_text(text, encoding="utf-8")

    # Create structured version with front matter
    structured_dir.mkdir(parents=True, exist_ok=True)
    out_path = structured_dir / filename

    front_matter = {
        "title": title,
        "source_type": source_type,
        "source_file": source_file,
        "categories": categories,
        "last_modified": last_modified,
    }
    yaml_block = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    structured = f"---\n{yaml_block}---\n{text}"
    out_path.write_text(structured, encoding="utf-8")

    # Ingest into ChromaDB
    try:
        result = chunk_and_ingest(out_path, db_path)
        return UploadResponse(
            filename=filename,
            status="processed",
            chunks=result.get("chunk_count", 0),
            categories=categories,
            source_type=source_type,
        )
    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}")
        return UploadResponse(
            filename=filename,
            status="failed",
            chunks=0,
            categories=categories,
            source_type=source_type,
            error=str(e),
        )


@router.post("", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Sanitise filename to prevent path traversal
    safe_name = Path(file.filename).name
    if safe_name != file.filename or ".." in safe_name or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")

    # Save uploaded file to temp location for extraction
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOADS_DIR / f"_temp_{safe_name}"
    temp_path.write_bytes(contents)

    try:
        text = extract_text(temp_path)
    except ValueError as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)

    if not text.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty")

    return _structure_and_ingest(
        text=text,
        filename=safe_name,
        uploads_dir=UPLOADS_DIR,
        structured_dir=UPLOADS_STRUCTURED_DIR,
        db_path=CHROMA_DB_DIR,
    )


@router.get("/formats", response_model=AcceptedFormatsResponse)
def get_accepted_formats() -> AcceptedFormatsResponse:
    return AcceptedFormatsResponse(
        extensions=sorted(SUPPORTED_EXTENSIONS),
        max_size_mb=20,
    )
