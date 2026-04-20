"""Stage 6: Schema Normalisation for AT pipeline.

Maps raw AT extraction data to the shared GuidelineDocument schema.
"""

import hashlib
import json
import logging
import os
from datetime import date
from typing import Any, Dict, List

from src.python.services.schema import (
    ContentSection,
    Flowchart,
    GuidelineDocument,
    MedicationDose,
    Reference,
)

logger = logging.getLogger(__name__)

# Category mapping based on Guides/categories-at.md
# Maps AT category names to project broad study categories
_CATEGORY_MAPPING: Dict[str, List[str]] = {
    # A0 prefix - Adult patient guidelines
    "Assessment": ["Clinical Skills"],
    "Mental Health": ["Clinical Guidelines"],
    "Cardiac Arrest": ["Clinical Guidelines"],
    "Airway Management": ["Clinical Skills"],
    "Cardiac": ["Clinical Guidelines"],
    "Pain Relief": ["Medication Guidelines"],
    "Respiratory": ["Clinical Guidelines"],
    "Medical": ["Clinical Guidelines"],
    "Trauma": ["Clinical Guidelines"],
    "Environment": ["Clinical Guidelines"],
    # Other prefixes
    "Obstetrics": ["Clinical Guidelines"],  # M prefix
    "Medicines": ["Medication Guidelines", "Pharmacology"],  # D prefix
    "Paediatric": ["Clinical Guidelines"],  # P prefix
    "Reference Notes": ["Operational Guidelines"],  # E prefix
}


def _map_categories(cpg_code: str, at_category: str) -> List[str]:
    """Map AT CPG code and category to project broad categories.

    Args:
        cpg_code: The CPG code (e.g., "A0201-1", "D003")
        at_category: The AT category name (e.g., "Cardiac Arrest", "Medicines")

    Returns:
        List of broad study categories
    """
    # Check single-character prefixes first (D, M, P, E)
    if cpg_code and len(cpg_code) > 0:
        first_char = cpg_code[0]

        if first_char == "D":
            # Medicine monographs always map to both
            return ["Medication Guidelines", "Pharmacology"]
        elif first_char == "M":
            return ["Clinical Guidelines"]
        elif first_char == "P":
            return ["Clinical Guidelines"]
        elif first_char == "E":
            return ["Operational Guidelines"]

    # Check two-character prefix (A0 for adult patient guidelines)
    prefix = cpg_code[:2] if len(cpg_code) >= 2 else ""
    if prefix == "A0":
        # Adult patient guidelines - look up by AT category name
        return _CATEGORY_MAPPING.get(at_category, ["Clinical Guidelines"])

    # Default fallback
    return ["Clinical Guidelines"]


def _extract_qualifications(sections: List[Dict], medicines: List[Dict]) -> List[str]:
    """Extract all unique qualifications from sections and medicines.

    Args:
        sections: List of content sections with qualifications_required
        medicines: List of medications with qualifications_required

    Returns:
        Sorted list of unique qualifications
    """
    qualifications = set()

    for section in sections:
        for qual in section.get("qualifications_required", []):
            if qual:
                qualifications.add(qual)

    for med in medicines:
        for qual in med.get("qualifications_required", []):
            if qual:
                qualifications.add(qual)

    return sorted(list(qualifications))


def _compute_source_hash(raw: Dict) -> str:
    """Compute SHA-256 hash of raw extraction content.

    Args:
        raw: Raw extraction dictionary

    Returns:
        Hexadecimal SHA-256 hash
    """
    # Use existing source_hash if provided
    if "source_hash" in raw and raw["source_hash"]:
        return raw["source_hash"]

    # Otherwise compute from content
    content_str = json.dumps(raw, sort_keys=True)
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


def _parse_last_modified(last_modified: str | None) -> date | None:
    """Parse last_modified string to date.

    Args:
        last_modified: ISO date string (YYYY-MM-DD) or None

    Returns:
        date object or None
    """
    if not last_modified:
        return None

    try:
        # Handle YYYY-MM-DD format
        if "-" in last_modified:
            parts = last_modified.split("-")
            if len(parts) == 3:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                return date(year, month, day)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse last_modified: {last_modified}")

    return None


def _extract_extra_metadata(raw: Dict) -> Dict[str, Any]:
    """Extract extra metadata not in the main schema.

    Args:
        raw: Raw extraction dictionary

    Returns:
        Dictionary of extra metadata
    """
    # Fields that are already mapped to GuidelineDocument
    mapped_fields = {
        "cpg_code",
        "title",
        "category",
        "sections",
        "medicines",
        "flowcharts",
        "source_url",
        "source_hash",
        "last_modified",
    }

    extra = {}
    for key, value in raw.items():
        if key not in mapped_fields:
            extra[key] = value

    return extra


def structure_guideline(raw: Dict) -> Dict:
    """Convert raw AT extraction to GuidelineDocument-compatible dict.

    Args:
        raw: Raw extraction dictionary with keys:
            - cpg_code: CPG identifier (e.g., "A0201-1", "D003")
            - title: Guideline title
            - category: AT clinical category
            - sections: List of content sections
            - medicines: List of medication doses
            - flowcharts: List of flowcharts
            - source_url: Source URL
            - source_hash: Content hash (optional, will be computed if missing)
            - last_modified: Last modified date string (optional)

    Returns:
        Dictionary compatible with GuidelineDocument schema
    """
    cpg_code = raw.get("cpg_code", "")
    title = raw.get("title", "")
    at_category = raw.get("category", "")

    # Map categories
    categories = _map_categories(cpg_code, at_category)

    # Extract qualifications
    sections = raw.get("sections", [])
    medicines = raw.get("medicines", [])
    qualifications = _extract_qualifications(sections, medicines)

    # Build content sections
    content_sections = [
        ContentSection(
            heading=section.get("heading", ""),
            body=section.get("body", ""),
            qualifications_required=section.get("qualifications_required", []),
        )
        for section in sections
    ]

    # Build medications
    medications = [
        MedicationDose(
            medication=med.get("medication", ""),
            indication=med.get("indication", ""),
            dose=med.get("dose", ""),
            route=med.get("route"),
            qualifications_required=med.get("qualifications_required", []),
        )
        for med in medicines
    ]

    # Build flowcharts
    flowcharts = [
        Flowchart(
            title=fc.get("title", ""),
            mermaid=fc.get("mermaid", ""),
            source_format=fc.get("source_format", "data"),
            review_required=fc.get("review_required", False),
            asset_ref=fc.get("asset_ref"),
        )
        for fc in raw.get("flowcharts", [])
    ]

    # No references in AT extraction (yet)
    references: List[Reference] = []

    # Compute source hash
    source_hash = _compute_source_hash(raw)

    # Parse last modified
    last_modified = _parse_last_modified(raw.get("last_modified"))

    # Extract extra metadata
    extra = _extract_extra_metadata(raw)

    # Build GuidelineDocument dict
    return {
        "service": "at",
        "guideline_id": f"AT_CPG_{cpg_code}",
        "title": title,
        "categories": categories,
        "qualifications_required": qualifications,
        "content_sections": [cs.model_dump() for cs in content_sections],
        "medications": [med.model_dump() for med in medications],
        "flowcharts": [fc.model_dump() for fc in flowcharts],
        "references": [ref.model_dump() for ref in references],
        "source_url": raw.get("source_url"),
        "source_hash": source_hash,
        "last_modified": last_modified,
        "extra": extra,
    }


def structure_all_guidelines(raw_dir: str, output_dir: str) -> int:
    """Process all raw AT extractions and write GuidelineDocument JSON files.

    Args:
        raw_dir: Directory containing raw extraction JSON files
        output_dir: Directory to write structured JSON files

    Returns:
        Number of guidelines successfully structured
    """
    if not os.path.exists(raw_dir):
        logger.error(f"Raw directory not found: {raw_dir}")
        return 0

    os.makedirs(output_dir, exist_ok=True)

    structured_count = 0
    errors = []

    for filename in os.listdir(raw_dir):
        if not filename.endswith(".json"):
            continue

        raw_path = os.path.join(raw_dir, filename)

        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            # Structure the guideline
            doc_dict = structure_guideline(raw)

            # Validate against schema
            doc = GuidelineDocument(**doc_dict)

            # Write output file
            output_filename = f"{doc.guideline_id}.json"
            output_path = os.path.join(output_dir, output_filename)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(doc.model_dump_json(indent=2))

            structured_count += 1
            logger.debug(f"Structured {filename} -> {output_filename}")

        except Exception as e:
            error_msg = f"Failed to structure {filename}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    if errors:
        logger.warning(f"Encountered {len(errors)} errors during structuring")
        for error in errors[:5]:  # Log first 5 errors
            logger.debug(error)

    logger.info(f"Structured {structured_count} guidelines from {raw_dir}")
    return structured_count
