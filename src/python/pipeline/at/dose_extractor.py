"""
Dose Extractor for AT CPG Pipeline

Extracts medication dose information from AT's narrative step-by-step text.
AT provides dosing as detailed instructions (not pre-computed lookup tables like ACTAS),
so this module uses regex patterns to parse dose quantities, routes, and qualifiers.

Key functions:
- extract_dose_sections: Find dose-related sections from guideline content
- parse_dose_text: Extract dose entries from narrative text using regex
- normalise_dose_entry: Convert raw extraction to schema-valid dict
"""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Dose section heading patterns
DOSE_SECTION_PATTERNS = [
    r"^Dose Recommendations?$",
    r"^Dosing$",
    r"^Administration$",
    r"^Dose$",
]

# Dose quantity patterns
DOSE_QUANTITY_RE = re.compile(
    r'\b(\d+\.?\d*)\s*(mg|mcg|microg|ml|IU|mmol|g|mg/kg|mcg/kg|microg/kg|ml/kg)\b',
    re.IGNORECASE
)

# Route patterns (ordered by specificity - longer first)
ROUTE_PATTERNS = [
    (r'\bintranasal\b', 'intranasal'),
    (r'\btopical\b', 'topical'),
    (r'\bnebulised?\b', 'inhaled'),
    (r'\binhaled\b', 'inhaled'),
    (r'\brectal\b', 'rectal'),
    (r'\boral\b', 'oral'),
    (r'\bIV\b', 'IV'),
    (r'\bIO\b', 'IO'),
    (r'\bIM\b', 'IM'),
    (r'\bSC\b', 'SC'),
]

# Dilution ratio patterns (1:10,000, 1:100,000)
DILUTION_RE = re.compile(
    r'\b1\s*:\s*(10\s*,?\s*0{3,4}|100\s*,?\s*0{3,4})\b',
    re.IGNORECASE
)

# Max dose markers
MAX_DOSE_RE = re.compile(
    r'\b(max|maximum|hard max)\b(?:\s+(?:total|dose)?)?\s*(\d+\.?\d*)\s*(mg|mcg|microg|ml|g|mg/kg|mcg/kg|microg/kg)',
    re.IGNORECASE
)

# Dose sentence patterns - sentences that contain dose information
DOSE_SENTENCE_RE = re.compile(
    r'[^.!?]*\b(\d+\.?\d*\s*(mg|mcg|microg|ml|IU|mmol|g|mg/kg|mcg/kg|microg/kg|ml/kg))[^.!?]*[.!?]',
    re.IGNORECASE
)


def extract_dose_sections(content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find sections with dose-related headings from guideline content.

    Args:
        content: Guideline content dict with 'sections' list

    Returns:
        List of section dicts with dose-related headings
    """
    if not content or "sections" not in content:
        return []

    dose_sections = []
    dose_pattern = re.compile(
        '|'.join(f'({pattern})' for pattern in DOSE_SECTION_PATTERNS),
        re.IGNORECASE
    )

    for section in content.get("sections", []):
        heading = section.get("heading", "")
        if dose_pattern.match(heading.strip()):
            dose_sections.append(section)

    return dose_sections


def parse_dose_text(text: str, medicine: str, indication: str) -> List[Dict[str, Any]]:
    """Extract dose entries from narrative text using regex patterns.

    Parses AT's narrative dose format (step-by-step instructions) and extracts
    structured dose entries with medication, indication, dose, route, and qualifiers.

    Args:
        text: Narrative dose text from guideline section
        medicine: Medication name (e.g. "Adrenaline")
        indication: Clinical indication (e.g. "Cardiac Arrest")

    Returns:
        List of dicts with keys: medication, indication, dose, route, qualifications_required
    """
    if not text or not text.strip():
        return []

    entries = []
    sentences = _split_into_sentences(text)

    # Extract max dose and dilution info from all sentences first
    max_dose_info = None
    dilution_info = None

    for sentence in sentences:
        if not max_dose_info:
            max_dose_info = _extract_max_dose(sentence)
        if not dilution_info:
            dilution_info = _extract_dilution(sentence)

    for sentence in sentences:
        # Check if sentence contains dose quantity OR dose-related keywords
        dose_match = DOSE_QUANTITY_RE.search(sentence)
        has_dose_keyword = any(keyword in sentence.lower() for keyword in
                               ['bolus', 'infusion', 'dose', 'dilution', 'administer', 'give'])

        # Skip sentences with no dose information
        if not dose_match and not has_dose_keyword:
            continue

        # Skip sentences that are clearly not dose instructions (like references)
        if any(skip_word in sentence.lower() for skip_word in ['see pharmacology', 'no dose information', 'refer to']):
            continue

        # Extract route
        route = _extract_route(sentence)

        # Build dose description
        dose_desc = sentence.strip()

        # Add max dose info if not already in sentence
        if max_dose_info and 'max' not in dose_desc.lower():
            dose_desc += f". {max_dose_info}"

        # Add dilution info if not already in sentence
        if dilution_info and 'dilution' not in dose_desc.lower() and dilution_info not in dose_desc:
            dose_desc += f" ({dilution_info})"

        # Create raw entry
        raw_entry = {
            "medication": medicine,
            "indication": indication,
            "dose": dose_desc,
            "route": route,
        }

        # Normalise to schema-valid dict
        entry = normalise_dose_entry(raw_entry)
        entries.append(entry)

    return entries


def normalise_dose_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw dose extraction into a schema-valid dict.

    Ensures all required keys are present and defaults optional fields.

    Args:
        raw: Raw dose entry dict from parse_dose_text

    Returns:
        Normalised dict with keys: medication, indication, dose, route, qualifications_required
    """
    return {
        "medication": raw.get("medication", ""),
        "indication": raw.get("indication", ""),
        "dose": raw.get("dose", ""),
        "route": raw.get("route", ""),
        "qualifications_required": raw.get("qualifications_required", []),
    }


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, handling abbreviations.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    # Simple sentence splitting - could be enhanced with abbreviations
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _extract_route(text: str) -> str:
    """Extract administration route from text.

    Args:
        text: Dose text to search

    Returns:
        Route string (e.g. "IV", "IO", "IM", "inhaled") or empty string
    """
    for pattern, route_name in ROUTE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return route_name
    return ""


def _extract_dilution(text: str) -> Optional[str]:
    """Extract dilution ratio from text.

    Args:
        text: Dose text to search

    Returns:
        Dilution string (e.g. "1:10,000") or None
    """
    match = DILUTION_RE.search(text)
    if match:
        # Normalise spacing in ratio
        ratio = match.group(0).replace(' ', '')
        return ratio
    return None


def _extract_max_dose(text: str) -> Optional[str]:
    """Extract maximum dose information from text.

    Args:
        text: Dose text to search

    Returns:
        Max dose string or None
    """
    match = MAX_DOSE_RE.search(text)
    if match:
        return match.group(0)
    return None
