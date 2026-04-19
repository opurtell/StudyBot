from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from paths import (
    CLEANED_NOTES_DIR,
    CPDDOCS_DIR,
    NOTABILITY_NOTE_DOCS_DIR,
    PERSONAL_STRUCTURED_DIR,
    RAW_NOTES_DIR,
    REFDOCS_DIR,
    resolve_service_structured_dir,
)
from services.active import active_service
from pipeline.actas.refresh import load_refresh_status

router = APIRouter(prefix="/sources", tags=["sources"])


class LibrarySource(BaseModel):
    id: str
    name: str
    type: str
    filter_type: str
    progress: int
    status_text: str
    detail: str


class CleaningFeedItem(BaseModel):
    status: str
    label: str
    preview: str
    detail: str | None = None


class LibraryStatusResponse(BaseModel):
    sources: list[LibrarySource]
    cleaning_feed: list[CleaningFeedItem]


def _count_files(directory: Path, pattern: str) -> int:
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.glob(pattern))


def _count_files_recursive(directory: Path, pattern: str) -> int:
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.rglob(pattern))


def _pluralise(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    word = plural or f"{singular}s"
    return f"{count} {word}"


def _personal_status(source_count: int, structured_count: int) -> tuple[int, str]:
    # Source dirs missing but structured output exists — data was ingested previously
    if source_count == 0 and structured_count > 0:
        return 100, "INGESTED"
    if source_count == 0:
        return 0, "NO DOCUMENTS"
    if structured_count >= source_count:
        return 100, "INGESTED"
    if structured_count > 0:
        progress = round(structured_count / source_count * 100)
        return progress, "INGESTION IN PROGRESS"
    return 0, "STRUCTURING PENDING"


def _notability_status(
    note_count: int, raw_count: int, cleaned_count: int
) -> tuple[int, str, str]:
    if note_count == 0:
        return 0, "NO FILES", "0 files"
    if raw_count == 0:
        if cleaned_count > 0:
            return 100, "CLEANED", _pluralise(cleaned_count, "cleaned file")
        return 0, "EXTRACTION PENDING", _pluralise(note_count, "file")
    if cleaned_count >= raw_count:
        return 100, "CLEANED", f"{cleaned_count} of {raw_count} cleaned"
    progress = round(cleaned_count / raw_count * 100)
    return progress, "CLEANING IN PROGRESS", f"{cleaned_count} of {raw_count} cleaned"


def _build_sources() -> list[LibrarySource]:
    svc_structured_dir = resolve_service_structured_dir(active_service().id)
    cmg_count = _count_files(svc_structured_dir, "*.json")
    ref_count = _count_files(REFDOCS_DIR, "*.md")
    ref_structured_count = _count_files(PERSONAL_STRUCTURED_DIR / "REFdocs", "*.md")
    cpd_count = _count_files(CPDDOCS_DIR, "*.md")
    cpd_structured_count = _count_files(PERSONAL_STRUCTURED_DIR / "CPDdocs", "*.md")
    note_count = _count_files_recursive(NOTABILITY_NOTE_DOCS_DIR, "*.note")
    raw_count = _count_files_recursive(RAW_NOTES_DIR, "*.md")
    cleaned_count = _count_files_recursive(CLEANED_NOTES_DIR, "*.md")

    ref_progress, ref_status = _personal_status(ref_count, ref_structured_count)
    cpd_progress, cpd_status = _personal_status(cpd_count, cpd_structured_count)
    field_progress, field_status, field_detail = _notability_status(
        note_count, raw_count, cleaned_count
    )

    return [
        LibrarySource(
            id="SRC-0001",
            name="ACTAS CMGs",
            type="PRIMARY SOURCE / REGULATORY",
            filter_type="primary",
            progress=100 if cmg_count > 0 else 0,
            status_text="INGESTED" if cmg_count > 0 else "NOT INGESTED",
            detail=_pluralise(cmg_count, "Guideline"),
        ),
        LibrarySource(
            id="SRC-0002",
            name="Clinical Reference Documents",
            type="REFERENCE / POLICIES",
            filter_type="reference",
            progress=ref_progress,
            status_text=ref_status,
            detail=_pluralise(ref_structured_count if ref_count == 0 else ref_count, "Document"),
        ),
        LibrarySource(
            id="SRC-0003",
            name="CPD Study Notes",
            type="STUDY / CLINICAL NOTES",
            filter_type="study",
            progress=cpd_progress,
            status_text=cpd_status,
            detail=_pluralise(cpd_structured_count if cpd_count == 0 else cpd_count, "Document"),
        ),
        LibrarySource(
            id="SRC-0004",
            name="Notability Field Notes",
            type="FIELD NOTES / OCR",
            filter_type="field",
            progress=field_progress,
            status_text=field_status,
            detail=field_detail,
        ),
    ]


def _build_cleaning_feed() -> list[CleaningFeedItem]:
    svc_structured_dir = resolve_service_structured_dir(active_service().id)
    cmg_count = _count_files(svc_structured_dir, "*.json")
    ref_count = _count_files(REFDOCS_DIR, "*.md")
    cpd_count = _count_files(CPDDOCS_DIR, "*.md")
    personal_structured_count = _count_files(
        PERSONAL_STRUCTURED_DIR / "REFdocs", "*.md"
    ) + _count_files(PERSONAL_STRUCTURED_DIR / "CPDdocs", "*.md")
    note_count = _count_files_recursive(NOTABILITY_NOTE_DOCS_DIR, "*.note")
    raw_count = _count_files_recursive(RAW_NOTES_DIR, "*.md")
    cleaned_count = _count_files_recursive(CLEANED_NOTES_DIR, "*.md")
    refresh_status = load_refresh_status()

    cmg_state = "complete" if cmg_count > 0 else "waiting"
    if refresh_status.get("is_running"):
        cmg_state = "active"
    cmg_preview = f"{cmg_count} structured guideline files available."
    if refresh_status.get("is_running"):
        cmg_preview = "CMG refresh currently running."

    personal_total = ref_count + cpd_count
    if personal_total == 0 and personal_structured_count > 0:
        # Source dirs missing but structured output exists — ingested previously
        personal_state = "complete"
    elif personal_total == 0:
        personal_state = "waiting"
    elif personal_structured_count >= personal_total:
        personal_state = "complete"
    else:
        personal_state = "active"

    if note_count == 0 and cleaned_count == 0:
        note_state = "waiting"
        note_preview = "No Notability note files detected."
        note_detail = None
    elif raw_count == 0 and cleaned_count > 0:
        note_state = "complete"
        note_preview = "All cleaned markdown files are available."
        note_detail = _pluralise(cleaned_count, "cleaned file")
    elif raw_count == 0:
        note_state = "waiting"
        note_preview = "Source notes detected but markdown extraction has not been run."
        note_detail = _pluralise(note_count, "note file")
    elif cleaned_count >= raw_count:
        note_state = "complete"
        note_preview = "All extracted markdown files have been clinically cleaned."
        note_detail = f"{cleaned_count} of {raw_count} cleaned"
    else:
        note_state = "active"
        note_preview = (
            "Clinical cleaning is part-complete for extracted Notability markdown."
        )
        note_detail = f"{cleaned_count} of {raw_count} cleaned"

    return [
        CleaningFeedItem(
            status=cmg_state,
            label="ACTAS CMG Extraction",
            preview=cmg_preview,
            detail=refresh_status.get("last_run_at"),
        ),
        CleaningFeedItem(
            status=personal_state,
            label="Reference Documents Ingestion",
            preview=(
                f"{personal_structured_count} REF/CPD documents structured."
                if personal_total == 0
                else f"{personal_structured_count} of {personal_total} REF/CPD documents structured."
            ),
            detail=None,
        ),
        CleaningFeedItem(
            status=note_state,
            label="Notability OCR Cleaning",
            preview=note_preview,
            detail=note_detail,
        ),
    ]


@router.get("")
def get_sources() -> dict:
    payload = LibraryStatusResponse(
        sources=_build_sources(),
        cleaning_feed=_build_cleaning_feed(),
    )
    return payload.model_dump()
