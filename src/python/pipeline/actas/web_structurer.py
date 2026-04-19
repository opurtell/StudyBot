"""Parse crawled HTML pages into structured CMGGuideline models."""

import json
import logging
import os
import re
from typing import Any

from .models import CMGGuideline, ExtractionMetadata

logger = logging.getLogger(__name__)

_SECTION_MAP: dict[str, str] = {
    "cardiac": "Cardiac",
    "respiratory": "Respiratory",
    "airway": "Airway Management",
    "neurology": "Neurology",
    "trauma": "Trauma",
    "medicine": "Medicine",
    "medical": "Medical",
    "pain": "Pain Management",
    "toxicology": "Toxicology",
    "environmental": "Environmental",
    "obstetric": "Obstetric",
    "behavioural": "Behavioural",
    "hazmat": "HAZMAT",
    "palliative": "Palliative Care",
    "general": "General Care",
    "clinical skill": "Clinical Skill",
    "paediatric": "Paediatric",
}


def _infer_section(category: str) -> str:
    cat_lower = category.lower()
    for key, value in _SECTION_MAP.items():
        if key in cat_lower:
            return value
    return "Other"


def _html_to_markdown(html: str) -> str:
    text = html
    text = re.sub(r"<h1[^>]*>", "# ", text)
    text = re.sub(r"<h2[^>]*>", "## ", text)
    text = re.sub(r"<h3[^>]*>", "### ", text)
    text = re.sub(r"</h[123]>", "\n", text)
    text = re.sub(r"<p[^>]*>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<li[^>]*>", "- ", text)
    text = re.sub(r"<strong[^>]*>", "**", text)
    text = re.sub(r"</strong>", "**", text)
    text = re.sub(r"<em[^>]*>", "*", text)
    text = re.sub(r"</em>", "*", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_dose_table(html: str) -> dict[str, list[dict[str, str]]] | None:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    if not rows:
        return None
    cells = [re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL) for row in rows]
    cells = [[re.sub(r"<[^>]+>", "", c).strip() for c in row] for row in cells if row]
    if not cells or len(cells) < 2:
        return None
    headers = cells[0]
    dose_lookup: dict[str, list[dict[str, str]]] = {}
    for row in cells[1:]:
        entry = {}
        for i, val in enumerate(row):
            key = headers[i].strip() if i < len(headers) else f"col_{i}"
            entry[key] = val
        drug_name = row[0] if row else "unknown"
        dose_lookup.setdefault(drug_name, []).append(entry)
    return dose_lookup if dose_lookup else None


def structure_crawled_guideline(
    crawled_path: str,
    output_dir: str = "data/cmgs/structured",
) -> dict[str, Any] | None:
    if not os.path.exists(crawled_path):
        logger.warning(f"Crawled file not found: {crawled_path}")
        return None

    with open(crawled_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("cmg_title", "").replace("\n", " ").strip()
    category = data.get("category", "Other")
    html = data.get("html", "")
    extracted_at = data.get("extracted_at", "")

    if not title or not html:
        logger.warning(f"Skipping crawled file with missing title/html: {crawled_path}")
        return None

    cmg_id = title.replace("/", "_").replace(" ", "_").replace("\n", "_")[:50]
    section = _infer_section(category)
    content_markdown = _html_to_markdown(html)
    dose_lookup = _parse_dose_table(html)

    cmg = CMGGuideline(
        id=cmg_id,
        cmg_number="",
        title=title,
        section=section,
        content_markdown=content_markdown,
        is_icp_only=False,
        dose_lookup=dose_lookup,
        checksum=str(hash(content_markdown)),
        extraction_metadata=ExtractionMetadata(
            timestamp=extracted_at,
            source_type="cmg",
        ),
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{cmg_id}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cmg.model_dump(), f, indent=2)

    logger.info(f"Structured crawled guideline: {cmg_id}")
    return cmg.model_dump()


def structure_crawled_guidelines(
    changed_ids: list[str],
    crawled_dir: str = "data/cmgs/raw",
    output_dir: str = "",
) -> list[str]:
    from paths import USER_CMG_STRUCTURED_DIR

    out = output_dir or str(USER_CMG_STRUCTURED_DIR)
    structured: list[str] = []

    for gid in changed_ids:
        crawled_path = os.path.join(crawled_dir, f"{gid}.json")
        result = structure_crawled_guideline(
            crawled_path=crawled_path,
            output_dir=out,
        )
        if result:
            structured.append(gid)

    return structured
