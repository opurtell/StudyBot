"""
Stage 6: Schema Normalisation
Maps raw extraction data to the CMG Guideline Schema.
"""

import json
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

from .models import CMGGuideline, ExtractionMetadata, FlowchartEntry

logger = logging.getLogger(__name__)

_ICP_ONLY_TITLES = {
    "Adenosine",
    "Amiodarone (Cordarone)",
    "Calcium Chloride",
    "Heparin",
    "Hydrocortisone",
    "Levetiracetam",
    "Sodium Bicarbonate",
    "Suxamethonium",
    "Intubation Algorithm",
    "AirTraq (Endotracheal Intubation)",
    "Laryngoscope and Bougie (Endotracheal Intubation)",
    "Laryngoscope and Bougie Railroad Technique (Endotracheal Intubation)",
    "Extubation",
    "Front of Neck (Surgical Airway)",
    "Needle Cricothyroidotomy",
    "External Cardiac Pacing (Zoll X Series)",
    "External Jugular Cannulation",
    "Tension Pneumothorax Needle Decompression",
}


def _is_icp_only_entry(title: str, content_markdown: str) -> bool:
    content_lower = content_markdown.lower()
    if "icp only" in content_lower or "intensive care paramedic only" in content_lower:
        return True
    return title in _ICP_ONLY_TITLES


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
    text = "\n".join([line for line in lines if line])
    return text


def _build_medication_index_entry(
    raw: dict, content_markdown: str, is_icp_only: bool
) -> dict:
    indication = ""
    ind_match = re.search(
        r"(?:####\s*(?:Indications?|Uses?))[^\n]*\n(.+?)(?:\n####|\n#####|\Z)",
        content_markdown,
        re.DOTALL | re.IGNORECASE,
    )
    if ind_match:
        lines = [
            line.strip() for line in ind_match.group(1).splitlines() if line.strip()
        ]
        indication = "; ".join(lines)
    if not indication:
        type_match = re.search(
            r"#####\s*Type\s*\n(.+?)(?:\n#####|\n#|\Z)", content_markdown, re.DOTALL
        )
        if type_match:
            indication = type_match.group(1).strip()

    contraindications = _extract_section(content_markdown, "Contraindications")
    adverse_effects = _extract_section(content_markdown, "Adverse Effects")
    precautions = _extract_section(content_markdown, "Precautions")
    dose_text = _extract_dose_section(content_markdown)
    cmg_number = raw.get("cmg_number", "")

    return {
        "name": raw.get("title", ""),
        "indication": indication or "See clinical management guideline",
        "contraindications": contraindications or "See clinical management guideline",
        "adverse_effects": adverse_effects or "See clinical management guideline",
        "precautions": precautions or "See clinical management guideline",
        "dose": dose_text or "See CMG for dose details",
        "cmg_reference": f"MED {cmg_number}" if cmg_number else "",
        "is_icp_only": is_icp_only,
    }


def structure_guidelines(
    guidelines_path: str = "data/cmgs/raw/guidelines.json",
    dose_tables_path: str = "data/cmgs/raw/dose_tables.json",
    flowcharts_dir: str = "data/cmgs/flowcharts/",
    output_dir: str = "data/cmgs/structured/",
) -> None:
    if not os.path.exists(guidelines_path):
        logger.error(f"Guidelines not found at {guidelines_path}")
        return

    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(guidelines_path, "r", encoding="utf-8") as f:
            raw_guidelines = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read guidelines: {e}")
        return

    dose_lookup: Dict = {}
    if os.path.exists(dose_tables_path):
        try:
            with open(dose_tables_path, "r", encoding="utf-8") as f:
                dose_data = json.load(f)
                dose_lookup = dose_data.get("medicine_index", {})
        except Exception as e:
            logger.warning(f"Could not load dose tables: {e}")

    structured_count = 0
    guideline_index: list[dict] = []
    medication_index: list[dict] = []
    for raw in raw_guidelines:
        try:
            cmg_number = raw.get("cmg_number", "UNKNOWN")
            title = raw.get("title", f"Guideline {cmg_number}")
            section = raw.get("section", "Other")
            entry_type = raw.get("entry_type", "cmg")

            content_html = raw.get("content_html", "")
            content_markdown = raw.get("content_markdown", "")
            if not content_markdown and content_html:
                content_markdown = content_html
            if not content_markdown:
                content_markdown = f"# {title}"

            if not content_markdown.startswith("#"):
                content_markdown = f"# {title}\n\n{content_markdown}"

            clinical_chars = len(content_markdown.strip())
            content_flag = "short" if clinical_chars < 50 else None

            checksum = hashlib.sha256(content_markdown.encode("utf-8")).hexdigest()

            flowchart_entry = None
            mermaid_path = os.path.join(flowcharts_dir, f"{cmg_number}.mmd")
            if os.path.exists(mermaid_path):
                with open(mermaid_path, "r", encoding="utf-8") as f:
                    flowchart_entry = FlowchartEntry(
                        cmg_number=cmg_number,
                        mermaid_code=f.read(),
                        source_type="svg",
                    )

            cmg_dose = None
            content_lower = content_markdown.lower()
            is_icp_only = _is_icp_only_entry(title, content_markdown)

            # Dose lookup tables (weight-band field references) are only useful
            # for clinical guideline entries — medication monograph bodies already
            # contain their full dose section, and the lookup tables bleed
            # unrelated medicines into MED entries.
            if entry_type != "med":
                matched_meds = {}
                for med_name, entries in dose_lookup.items():
                    if med_name.lower() in content_lower:
                        matched_meds[med_name] = entries
                if matched_meds:
                    cmg_dose = matched_meds

            safe_title = title.replace("/", "_").replace("\\", "_").replace(" ", "_")
            safe_title = re.sub(r"[^\w]", "_", safe_title)
            if entry_type == "med":
                num_key = cmg_number.zfill(2) if cmg_number.isdigit() else cmg_number
                entry_id = f"MED_{num_key}_{safe_title}"
            else:
                entry_id = f"CMG_{cmg_number}_{safe_title}"
            cmg = CMGGuideline(
                id=entry_id,
                cmg_number=cmg_number,
                title=title,
                version_date=raw.get("version_date"),
                section=section,
                content_markdown=content_markdown,
                is_icp_only=is_icp_only,
                dose_lookup=cmg_dose,
                flowchart=flowchart_entry,
                checksum=checksum,
                extraction_metadata=ExtractionMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    source_type=entry_type,
                    agent_version="2.0",
                    content_flag=content_flag,
                ),
            )

            if entry_type == "med":
                entry_output_dir = os.path.join(output_dir, "med")
            elif entry_type == "csm":
                entry_output_dir = os.path.join(output_dir, "csm")
            else:
                entry_output_dir = output_dir
            os.makedirs(entry_output_dir, exist_ok=True)
            output_file = os.path.join(entry_output_dir, f"{cmg.id}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(cmg.model_dump_json(indent=2))
            guideline_index.append(
                {
                    "id": cmg.id,
                    "cmg_number": cmg.cmg_number,
                    "title": cmg.title,
                    "section": cmg.section,
                    "source_type": entry_type,
                    "is_icp_only": cmg.is_icp_only,
                }
            )
            if entry_type == "med":
                medication_index.append(
                    _build_medication_index_entry(raw, content_markdown, is_icp_only)
                )
            structured_count += 1

        except Exception as e:
            logger.error(f"Validation failed for CMG {raw.get('cmg_number')}: {e}")

    guideline_index_path = os.path.join(output_dir, "guidelines-index.json")
    medication_index_path = os.path.join(output_dir, "medications-index.json")
    with open(guideline_index_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "items": guideline_index,
            },
            f,
            indent=2,
        )
    with open(medication_index_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "items": medication_index,
            },
            f,
            indent=2,
        )
    logger.info(f"Structured {structured_count} of {len(raw_guidelines)} guidelines.")
