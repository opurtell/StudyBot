"""
Qualification Tagger for AT CPG Pipeline

Tags guideline sections with qualification level requirements based on
content analysis. Maps AT's five qualification levels (VAO, PARAMEDIC,
ICP, PACER, CP_ECP) to guideline content sections.

AT Qualification Structure:
- VAO (Volunteer Ambulance Officer) - baseline, universally available
- PARAMEDIC - base qualification
- ICP (Intensive Care Paramedic) - endorsement requiring PARAMEDIC
- PACER - endorsement requiring PARAMEDIC
- CP_ECP (Community Paramedic / Extended Care Paramedic) - endorsement requiring PARAMEDIC

Tagging Strategy:
- Default (no specific markers): qualifications_required = [] (universally available)
- ICP-tagged sections: Look for ICP markers in headings or body
- PACER-tagged sections: Look for PACER-specific markers
- CP/ECP-tagged sections: Look for community paramedic markers
- VAO-only content: Generally not restricted; VAO content is baseline

The tagging is heuristic-based and conservative — if uncertain, default to
empty (universally available).
"""

import logging
import re
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)


# Qualification level markers for heuristic detection
# Patterns are checked case-insensitively
_ICP_MARKERS = [
    r"\bICP\b",
    r"intensive care",
    r"cold intubation",
    r"rapid sequence intubation",
    r"RSI",
    r"intensive care paramedic",
]

_PACER_MARKERS = [
    r"\bPACER\b",
    r"pacer",
]

_CP_ECP_MARKERS = [
    r"\bCP/ECP\b",
    r"community paramedic",
    r"extended care",
    r"extended care paramedic",
]

# ICP-exclusive medications (simplified list - may need expansion)
_ICP_MEDICATIONS = [
    "amiodarone",
    "rostafuroxin",
    "ketamine",
    "rocuroinium",
    "succinylcholine",
]

# Known qualification-restricted medicines for AT CPG
# These sets will be populated when definitive mapping is obtained from AT site
# For now, using conservative defaults based on common ambulance service patterns
_KNOWN_ICP_MEDICINES = {
    "amiodarone",  # Antiarrhythmic for cardiac arrest
    # Additional ICP medicines will be added when AT site is probed
}

_KNOWN_PACER_MEDICINES = set()  # Empty until AT site probing

_KNOWN_CP_ECP_MEDICINES = set()  # Empty until AT site probing

# Compile regex patterns for efficiency
_ICP_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in _ICP_MARKERS]
_PACER_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in _PACER_MARKERS]
_CP_ECP_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in _CP_ECP_MARKERS]
_ICP_MED_PATTERNS = [re.compile(rf"\b{med}\b", re.IGNORECASE) for med in _ICP_MEDICATIONS]


def _check_patterns(text: str, patterns: List[re.Pattern]) -> bool:
    """Check if any pattern matches the text.

    Args:
        text: Text to search
        patterns: List of compiled regex patterns

    Returns:
        True if any pattern matches
    """
    for pattern in patterns:
        if pattern.search(text):
            return True
    return False


def _detect_qualifications(heading: str, body: str) -> List[str]:
    """Detect qualification requirements from section heading and body.

    Args:
        heading: Section heading
        body: Section body text

    Returns:
        List of qualification IDs required for this section
    """
    qualifications: Set[str] = set()

    # Combine heading and body for analysis
    combined = f"{heading} {body}".lower()

    # Check for ICP markers
    if _check_patterns(combined, _ICP_PATTERNS):
        qualifications.add("ICP")

    # Check for ICP-exclusive medications
    if _check_patterns(combined, _ICP_MED_PATTERNS):
        qualifications.add("ICP")

    # Check for PACER markers
    if _check_patterns(combined, _PACER_PATTERNS):
        qualifications.add("PACER")

    # Check for CP/ECP markers
    if _check_patterns(combined, _CP_ECP_PATTERNS):
        qualifications.add("CP_ECP")

    # Return sorted list for consistent ordering
    return sorted(list(qualifications))


def tag_section_qualifications(section: Dict[str, Any]) -> Dict[str, Any]:
    """Tag a single section with qualification requirements.

    Analyses the section heading and body text to determine which
    qualification levels are required to apply the clinical guidance.

    Args:
        section: Dict with keys: heading, body

    Returns:
        New dict with original keys plus qualifications_required (list of qualification IDs)

    Examples:
        >>> tag_section_qualifications({"heading": "ICP Management", "body": "Cold intubation."})
        {"heading": "ICP Management", "body": "Cold intubation.", "qualifications_required": ["ICP"]}

        >>> tag_section_qualifications({"heading": "Indications", "body": "Chest pain."})
        {"heading": "Indications", "body": "Chest pain.", "qualifications_required": []}
    """
    heading = section.get("heading", "")
    body = section.get("body", "")

    # Detect qualifications from content
    qualifications_required = _detect_qualifications(heading, body)

    # Return new dict with qualifications tagged
    return {
        "heading": heading,
        "body": body,
        "qualifications_required": qualifications_required,
    }


def tag_guideline_qualifications(guideline: Dict[str, Any]) -> Dict[str, Any]:
    """Tag all sections in a guideline with qualification requirements.

    Processes each section in the guideline to determine qualification
    requirements at section level. Returns a new guideline dict with
    tagged sections (does not modify input).

    Args:
        guideline: Dict with keys: cpg_code, title, sections (list of section dicts)

    Returns:
        New guideline dict with sections tagged with qualifications_required

    Examples:
        >>> guideline = {
        ...     "cpg_code": "A0201-1",
        ...     "title": "Medical Cardiac Arrest",
        ...     "sections": [
        ...         {"heading": "Initial Assessment", "body": "DRABC."},
        ...         {"heading": "ICP Interventions", "body": "Cold intubation."},
        ...     ]
        ... }
        >>> result = tag_guideline_qualifications(guideline)
        >>> result["sections"][0]["qualifications_required"]
        []
        >>> result["sections"][1]["qualifications_required"]
        ["ICP"]
    """
    # Create a copy to avoid modifying input
    result = dict(guideline)

    # Tag each section
    tagged_sections = []
    for section in guideline.get("sections", []):
        tagged_section = tag_section_qualifications(section)
        tagged_sections.append(tagged_section)

    result["sections"] = tagged_sections

    return result


def tag_medicine_qualifications(med: Dict[str, Any]) -> Dict[str, Any]:
    """Tag a medicine with qualification requirements.

    Determines which qualification levels are required to administer
    a specific medicine based on known qualification restrictions.

    Args:
        med: Dict with at least: name (str)

    Returns:
        New dict with original keys plus qualifications_required (list of qualification IDs)

    Examples:
        >>> tag_medicine_qualifications({"name": "Adrenaline", "cpg_code": "D003"})
        {"name": "Adrenaline", "cpg_code": "D003", "qualifications_required": []}

        >>> tag_medicine_qualifications({"name": "Amiodarone", "cpg_code": "D004"})
        {"name": "Amiodarone", "cpg_code": "D004", "qualifications_required": ["ICP"]}
    """
    # Create a copy to avoid modifying input
    result = dict(med)

    # Get medicine name for lookup
    medicine_name = med.get("name", "").strip().lower()

    # Determine qualification requirements
    qualifications_required: Set[str] = set()

    # Check if medicine is ICP-restricted
    if medicine_name in _KNOWN_ICP_MEDICINES:
        qualifications_required.add("ICP")

    # Check if medicine is PACER-restricted
    if medicine_name in _KNOWN_PACER_MEDICINES:
        qualifications_required.add("PACER")

    # Check if medicine is CP/ECP-restricted
    if medicine_name in _KNOWN_CP_ECP_MEDICINES:
        qualifications_required.add("CP_ECP")

    # Default to empty list (universally available to PARAMEDIC level)
    result["qualifications_required"] = sorted(list(qualifications_required))

    return result
