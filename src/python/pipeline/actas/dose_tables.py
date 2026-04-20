"""
Stage 3: Dose Table Extraction
Extracts medicine dose information from Angular compiled templates.
Dose data is embedded as inline clinical text (.EFF instructions), not as
separate structured arrays. This module extracts and structures that text.
"""

import json
import logging
import os
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

COMMON_BUNDLE_RE = re.compile(r"^7_common\.[\w]+\.js$")
CHUNK_FILE_RE = re.compile(r"^\d+_[\w]+\.[\w]+\.js$")

_DOSE_UNIT_RE = re.compile(
    r"\b(\d+\.?\d*)\s*(mg|mcg|ml|IU|mmol|g|mg/kg|mcg/kg|ml/kg)\b", re.IGNORECASE
)
_DOSE_PATTERN_RE = re.compile(
    r'(?:Dose|Volume|Preparation|Formula|Concentration|Rate|Max)\s*:\s*([^\n"]+)',
    re.IGNORECASE,
)
_MEDICINE_KEYWORDS = [
    "adrenaline",
    "heparin",
    "lignocaine",
    "salbutamol",
    "ondansetron",
    "fentanyl",
    "morphine",
    "ibuprofen",
    "paracetamol",
    "ketamine",
    "midazolam",
    "atropine",
    "amiodarone",
    "glucose",
    "naloxone",
    "gtn",
    "aspirin",
    "acetylsalicylic",
    "metoclopramide",
    "magnesium",
    "suxamethonium",
    "hydrocortisone",
    "ipratropium",
    "ceftriaxone",
    "methoxyflurane",
    "glyceryl trinitrate",
    "normal saline",
    "adenosine",
    "calcium chloride",
    "droperidol",
    "glucagon",
    "levetiracetam",
    "olanzapine",
    "oxygen",
    "prochlorperazine",
    "sodium bicarbonate",
    "topical anaesthetic",
]


def _find_bundle(directory: str, pattern: re.Pattern) -> Optional[str]:
    for fname in os.listdir(directory):
        if pattern.match(fname):
            return os.path.join(directory, fname)
    return None


def _extract_eff_texts(file_path: str) -> List[str]:
    eff_re = re.compile(r'\.EFF\(\d+\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return []

    texts = []
    for match in eff_re.finditer(content):
        text = match.group(1)
        text = text.replace("\\u2019", "\u2019").replace("\\u2018", "\u2018")
        text = text.replace("\\u201c", "\u201c").replace("\\u201d", "\u201d")
        text = text.replace("\\u2013", "\u2013").replace("\\u2014", "\u2014")
        text = text.replace("\\u2010", "\u2010").replace("\\u00b0", "\u00b0")
        text = text.replace("\\u2265", "\u2265").replace("\\u2264", "\u2264")
        text = text.replace("\\n", "\n")
        texts.append(text)
    return texts


def _is_dose_related(text: str) -> bool:
    has_unit = bool(_DOSE_UNIT_RE.search(text))
    has_label = bool(_DOSE_PATTERN_RE.search(text))
    has_med = any(kw in text.lower() for kw in _MEDICINE_KEYWORDS)
    return has_unit or has_label or (has_med and any(c.isdigit() for c in text))


def _get_medicines_in_text(text: str) -> set:
    text_lower = text.lower()
    return {kw for kw in _MEDICINE_KEYWORDS if kw in text_lower}


def _is_medicine_header(text: str) -> bool:
    if len(text.split()) > 5:
        return False
    has_med = any(kw in text.lower() for kw in _MEDICINE_KEYWORDS)
    has_unit = bool(_DOSE_UNIT_RE.search(text))
    has_label = bool(_DOSE_PATTERN_RE.search(text))
    return has_med and not has_unit and not has_label


def _group_dose_texts(texts: List[str]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    current_medicines: set = set()
    pending_medicines: set = set()

    for text in texts:
        is_dose = _is_dose_related(text)
        text_meds = _get_medicines_in_text(text)

        if is_dose:
            new_med = text_meds - current_medicines if current_medicines else text_meds
            is_header_break = (
                _is_medicine_header(text) and new_med and current is not None
            )

            if is_header_break:
                groups.append(current)
                current = {"lines": [text], "inherited_medicines": text_meds}
                current_medicines = text_meds
            elif current is None:
                current = {"lines": [text]}
                inherited = pending_medicines if not text_meds else set()
                current["inherited_medicines"] = inherited
                current_medicines = text_meds if text_meds else set(pending_medicines)
            else:
                current["lines"].append(text)
                current_medicines.update(text_meds)

            pending_medicines = set()
        else:
            if current is not None:
                groups.append(current)
                current = None
                current_medicines = set()

            if text_meds:
                pending_medicines = text_meds

    if current is not None:
        groups.append(current)

    for group in groups:
        combined = " ".join(group["lines"])
        medicines_found = []
        combined_lower = combined.lower()
        for med in _MEDICINE_KEYWORDS:
            if med in combined_lower:
                medicines_found.append(med.title())
        for med in group.get("inherited_medicines", set()):
            if med.title() not in medicines_found:
                medicines_found.append(med.title())
        group["medicines"] = list(set(medicines_found))
        group["combined_text"] = combined

        doses = _DOSE_UNIT_RE.findall(combined)
        group["dose_values"] = [{"amount": amt, "unit": unit} for amt, unit in doses]
        group.pop("inherited_medicines", None)

    return groups


def _extract_medicine_from_selectors(
    investigation_dir: str,
) -> List[Dict[str, Any]]:
    common_path = _find_bundle(investigation_dir, COMMON_BUNDLE_RE)
    if not common_path:
        return []

    from .selector_extractor import extract_selector_templates

    templates = extract_selector_templates(investigation_dir=investigation_dir)

    results: List[Dict[str, Any]] = []
    for tmpl in templates:
        route = tmpl["route_path"]
        route_words = route.replace("-", " ").lower()
        matched_med = None
        for kw in _MEDICINE_KEYWORDS:
            if kw in route_words:
                matched_med = kw
                break

        if not matched_med:
            continue

        html = tmpl.get("html", "")
        from .template_parser import (
            strip_boilerplate,
            html_to_markdown,
            strip_boilerplate_md,
        )

        cleaned = strip_boilerplate(html)
        md = html_to_markdown(cleaned)
        md = strip_boilerplate_md(md)

        if not _is_dose_related(md):
            continue

        dose_values = _DOSE_UNIT_RE.findall(md)
        results.append(
            {
                "medicine": matched_med,
                "source": tmpl["selector"],
                "combined_text": md,
                "dose_values": [
                    {"amount": amt, "unit": unit} for amt, unit in dose_values
                ],
            }
        )

    return results


def extract_dose_tables(
    investigation_dir: str = "data/cmgs/investigation/",
    output_path: str = "data/cmgs/raw/dose_tables.json",
) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_groups: List[Dict[str, Any]] = []
    source_files: List[str] = []

    for fname in sorted(os.listdir(investigation_dir)):
        if not fname.endswith(".js"):
            continue
        fpath = os.path.join(investigation_dir, fname)
        texts = _extract_eff_texts(fpath)
        if not texts:
            continue
        has_dose = any(_is_dose_related(t) for t in texts)
        if not has_dose:
            continue

        file_groups = _group_dose_texts(texts)
        all_groups.extend(file_groups)
        source_files.append(fname)

    medicine_index: Dict[str, List[Dict[str, Any]]] = {}
    for group in all_groups:
        for med in group.get("medicines", []):
            if med not in medicine_index:
                medicine_index[med] = []
            medicine_index[med].append(
                {
                    "text": group["combined_text"],
                    "dose_values": group.get("dose_values", []),
                }
            )

    selector_doses = _extract_medicine_from_selectors(investigation_dir)
    for entry in selector_doses:
        med_title = entry["medicine"].title()
        if med_title not in medicine_index:
            medicine_index[med_title] = []
        medicine_index[med_title].append(
            {
                "text": entry["combined_text"],
                "dose_values": entry.get("dose_values", []),
                "source": entry["source"],
            }
        )

    result = {
        "total_dose_groups": len(all_groups),
        "unique_medicines": sorted(medicine_index.keys()),
        "medicine_count": len(medicine_index),
        "source_files": source_files,
        "medicine_index": medicine_index,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Extracted {len(all_groups)} dose groups covering {len(medicine_index)} medicines"
    )
    return output_path


def extract_dose_tables_segmented(
    investigation_dir: str = "data/cmgs/investigation/",
    output_path: str = "data/cmgs/raw/dose_tables_segmented.json",
) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    per_file: List[Dict[str, Any]] = []
    all_medicines: set = set()

    for fname in sorted(os.listdir(investigation_dir)):
        if not fname.endswith(".js"):
            continue
        fpath = os.path.join(investigation_dir, fname)
        texts = _extract_eff_texts(fpath)
        if not texts:
            continue
        has_dose = any(_is_dose_related(t) for t in texts)
        if not has_dose:
            continue

        groups = _group_dose_texts(texts)
        for group in groups:
            combined = " ".join(group["lines"])
            combined_lower = combined.lower()
            medicines_found = []
            for med in _MEDICINE_KEYWORDS:
                if med in combined_lower:
                    medicines_found.append(med.title())
            group["medicines"] = list(set(medicines_found))
            group["combined_text"] = combined
            doses = _DOSE_UNIT_RE.findall(combined)
            group["dose_values"] = [
                {"amount": amt, "unit": unit} for amt, unit in doses
            ]
            all_medicines.update(group["medicines"])

        per_file.append(
            {
                "source_file": fname,
                "dose_group_count": len(groups),
                "dose_groups": groups,
            }
        )

    result = {
        "total_dose_groups": sum(f["dose_group_count"] for f in per_file),
        "unique_medicines": sorted(all_medicines),
        "medicine_count": len(all_medicines),
        "source_file_count": len(per_file),
        "per_file": per_file,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Segmented dose tables: {len(per_file)} files, "
        f"{result['total_dose_groups']} groups, "
        f"{len(all_medicines)} medicines"
    )
    return output_path
