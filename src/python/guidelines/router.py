from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from paths import CMG_STRUCTURED_DIR
from paths import resolve_cmg_structured_dir

from .markdown import normalise_markdown_payload, normalise_markdown_syntax, strip_icp_content
from .models import GuidelineDetail, GuidelineSummary

router = APIRouter(prefix="/guidelines", tags=["guidelines"])


def _get_structured_dir() -> Path:
    return resolve_cmg_structured_dir()


def _get_type_dirs() -> dict[str, Path]:
    structured_dir = _get_structured_dir()
    return {
        "cmg": structured_dir,
        "med": structured_dir / "med",
        "csm": structured_dir / "csm",
    }


_guideline_summaries_cache: list[dict] | None = None
_guideline_detail_cache: dict[str, dict] = {}


def _load_all_raw() -> list[dict]:
    results: list[dict] = []
    for source_type, directory in _get_type_dirs().items():
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

    index_path = _get_structured_dir() / "guidelines-index.json"
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as f:
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
    return _get_type_dirs().get(source_type, _get_structured_dir()) / f"{guideline_id}.json"


def _find_summary(guideline_id: str) -> dict | None:
    for item in _load_guideline_summaries():
        if item["id"] == guideline_id:
            return item
    return None


@router.get("")
def list_guidelines(
    type: str | None = None,
    section: str | None = None,
    skill_level: str | None = None,
) -> list[dict]:
    summaries: list[dict] = []
    for item in _load_guideline_summaries():
        source_type = item.get("source_type", "cmg")
        if type and source_type != type:
            continue
        if section and item.get("section", "") != section:
            continue
        if skill_level == "AP" and item.get("is_icp_only", False):
            continue
        summaries.append(item)
    return summaries


@router.get("/{guideline_id}")
def get_guideline(guideline_id: str, skill_level: str | None = None) -> dict:
    cache_key = f"{guideline_id}:{skill_level or 'all'}"
    cached = _guideline_detail_cache.get(cache_key)
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

    content = normalise_markdown_syntax(data.get("content_markdown", ""))
    if skill_level == "AP":
        content = strip_icp_content(content)

    detail = GuidelineDetail(
        id=data["id"],
        cmg_number=data.get("cmg_number", ""),
        title=data.get("title", ""),
        section=data.get("section", "Other"),
        source_type=source_type,
        content_markdown=content,
        is_icp_only=data.get("is_icp_only", False),
        dose_lookup=normalise_markdown_payload(data.get("dose_lookup")),
        flowchart=normalise_markdown_payload(data.get("flowchart")),
    ).model_dump()
    _guideline_detail_cache[cache_key] = detail
    return detail
