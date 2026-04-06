from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter

from guidelines.markdown import normalise_markdown_payload, normalise_markdown_syntax
from paths import CMG_STRUCTURED_DIR

from .models import MedicationDose

router = APIRouter(prefix="/medication", tags=["medication"])

MED_DIR = CMG_STRUCTURED_DIR / "med"
MEDICATION_INDEX_PATH = CMG_STRUCTURED_DIR / "medications-index.json"
_medication_cache: list[dict] | None = None


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"####\s*{re.escape(heading)}\s*\n(.+?)(?=\n####|\n#####\s*(?!Pregnancy|Breastfeeding)|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    text = match.group(1).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "; ".join(lines)


def _extract_dose_section(content: str) -> str:
    match = re.search(r"####\s*Doses?", content, re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    remaining = content[start:]
    lines = []
    for line in remaining.splitlines():
        stripped = line.strip()
        if re.match(
            r"####\s*(?:Special Notes|Further Information|Pregnancy|Breastfeeding|Additional)",
            stripped,
            re.IGNORECASE,
        ):
            break
        lines.append(stripped)
    text = "\n".join([l for l in lines if l])
    return text


def load_medications() -> list[MedicationDose]:
    if not MED_DIR.exists():
        return []

    results: list[MedicationDose] = []
    for fpath in sorted(MED_DIR.glob("*.json")):
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        title = data.get("title", "")
        content = normalise_markdown_syntax(data.get("content_markdown", ""))
        indication = ""
        ind_match = re.search(
            r"(?:####\s*(?:Indications?|Uses?))[^\n]*\n(.+?)(?:\n####|\n#####|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if ind_match:
            lines = [
                line.strip() for line in ind_match.group(1).splitlines() if line.strip()
            ]
            indication = "; ".join(lines)
        if not indication:
            type_match = re.search(
                r"#####\s*Type\s*\n(.+?)(?:\n#####|\n#|\Z)", content, re.DOTALL
            )
            if type_match:
                indication = type_match.group(1).strip()

        contraindications = _extract_section(content, "Contraindications")
        adverse_effects = _extract_section(content, "Adverse Effects")
        precautions = _extract_section(content, "Precautions")
        dose_text = _extract_dose_section(content)

        cmg_number = data.get("cmg_number", "")
        cmg_reference = f"CMG {cmg_number}" if cmg_number else ""

        results.append(
            MedicationDose(
                name=title,
                indication=indication or "See clinical management guideline",
                contraindications=contraindications
                or "See clinical management guideline",
                adverse_effects=adverse_effects or "See clinical management guideline",
                precautions=precautions or "See clinical management guideline",
                dose=dose_text or "See CMG for dose details",
                cmg_reference=cmg_reference,
                is_icp_only=data.get("is_icp_only", False),
            )
        )

    return results


def invalidate_medication_cache() -> None:
    global _medication_cache
    _medication_cache = None


def _load_medication_payload() -> list[dict]:
    global _medication_cache
    if _medication_cache is not None:
        return _medication_cache

    if MEDICATION_INDEX_PATH.exists():
        try:
            with open(MEDICATION_INDEX_PATH, encoding="utf-8") as f:
                payload = json.load(f)
            items = payload.get("items", payload)
            if isinstance(items, list):
                _medication_cache = [
                    MedicationDose(**normalise_markdown_payload(item)).model_dump()
                    for item in items
                ]
                return _medication_cache
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    _medication_cache = [item.model_dump() for item in load_medications()]
    return _medication_cache


@router.get("/doses")
def get_doses() -> list[dict]:
    return _load_medication_payload()
