from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from paths import CMG_STRUCTURED_DIR

from .markdown import normalise_markdown_payload, normalise_markdown_syntax
from .models import GuidelineDetail, GuidelineSummary

router = APIRouter(prefix="/guidelines", tags=["guidelines"])

STRUCTURED_DIR = CMG_STRUCTURED_DIR
GUIDELINES_INDEX_PATH = STRUCTURED_DIR / "guidelines-index.json"

_TYPE_DIRS = {
    "cmg": STRUCTURED_DIR,
    "med": STRUCTURED_DIR / "med",
    "csm": STRUCTURED_DIR / "csm",
}

_guideline_summaries_cache: list[dict] | None = None
_guideline_detail_cache: dict[str, dict] = {}


def _load_all_raw() -> list[dict]:
    results: list[dict] = []
    for source_type, directory in _TYPE_DIRS.items():
        if not directory.exists():
            continue
        for fpath in sorted(directory.glob("*.json")):
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            data["_source_type"] = source_type
            data["_file_path"] = fpath
            results.append(data)
    return results


def invalidate_guideline_cache() -> None:
    global _guideline_summaries_cache
    _guideline_summaries_cache = None
    _guideline_detail_cache.clear()


def _summary_from_item(item: dict, source_type: str) -> dict:
    return GuidelineSummary(
        id=item["id"],
        cmg_number=item.get("cmg_number", ""),
        title=item.get("title", ""),
        section=item.get("section", "Other"),
        source_type=source_type,
        is_icp_only=item.get("is_icp_only", False),
    ).model_dump()


def _load_guideline_summaries() -> list[dict]:
    global _guideline_summaries_cache
    if _guideline_summaries_cache is not None:
        return _guideline_summaries_cache

    if GUIDELINES_INDEX_PATH.exists():
        try:
            with open(GUIDELINES_INDEX_PATH, encoding="utf-8") as f:
                payload = json.load(f)
            items = payload.get("items", payload)
            if isinstance(items, list):
                _guideline_summaries_cache = [
                    GuidelineSummary(**item).model_dump() for item in items
                ]
                return _guideline_summaries_cache
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    _guideline_summaries_cache = [
        _summary_from_item(item, item.get("_source_type", "cmg"))
        for item in _load_all_raw()
    ]
    return _guideline_summaries_cache


def _detail_path(source_type: str, guideline_id: str) -> Path:
    return _TYPE_DIRS.get(source_type, STRUCTURED_DIR) / f"{guideline_id}.json"


def _find_summary(guideline_id: str) -> dict | None:
    for item in _load_guideline_summaries():
        if item["id"] == guideline_id:
            return item
    return None


@router.get("")
def list_guidelines(
    type: str | None = None,
    section: str | None = None,
) -> list[dict]:
    summaries: list[dict] = []
    for item in _load_guideline_summaries():
        source_type = item.get("source_type", "cmg")
        if type and source_type != type:
            continue
        if section and item.get("section", "") != section:
            continue
        summaries.append(item)
    return summaries


@router.get("/{guideline_id}")
def get_guideline(guideline_id: str) -> dict:
    cached = _guideline_detail_cache.get(guideline_id)
    if cached is not None:
        return cached

    summary = _find_summary(guideline_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Guideline not found")

    source_type = summary.get("source_type", "cmg")
    fpath = _detail_path(source_type, guideline_id)
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Guideline not found")

    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=500, detail="Failed to read guideline")

    detail = GuidelineDetail(
        id=data["id"],
        cmg_number=data.get("cmg_number", ""),
        title=data.get("title", ""),
        section=data.get("section", "Other"),
        source_type=source_type,
        content_markdown=normalise_markdown_syntax(data.get("content_markdown", "")),
        is_icp_only=data.get("is_icp_only", False),
        dose_lookup=normalise_markdown_payload(data.get("dose_lookup")),
        flowchart=normalise_markdown_payload(data.get("flowchart")),
    ).model_dump()
    _guideline_detail_cache[guideline_id] = detail
    return detail
