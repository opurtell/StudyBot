"""
Content Extractor for AT CPG Pipeline

Extracts clinical text, section tree, categories, and metadata from each
AT guideline's lazy-loaded JS chunk. The AT site renders content as HTML
within Ionic/Angular components.

This module handles:
- Parsing HTML from JS template strings
- Extracting heading/body section pairs
- Detecting medicine D-code references
- Detecting dose tables
- Building source URLs
- Batch extraction of all guidelines
"""

import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from .models import ATContentSection, ATGuidelineRef

logger = logging.getLogger(__name__)

# AT CPG site base URL
AT_BASE_URL = "https://cpg.ambulance.tas.gov.au"

# Template string pattern in JS (template: `...`)
TEMPLATE_RE = re.compile(r'template\s*:\s*`([^`]*)`', re.DOTALL)

# D-code pattern for medicine references (D001-D099)
D_CODE_RE = re.compile(r'\bD(\d{3})\b')

# Qualification level names
QUALIFICATION_LEVELS = [
    "VAO",
    "PARAMEDIC",
    "ICP",
    "PACER",
    "CP",
    "ECP",
]

# HTML tag patterns
HEADING_RE = re.compile(r'<h([1-6])>(.*?)</h\1>', re.IGNORECASE)
TABLE_RE = re.compile(r'<table', re.IGNORECASE)


def parse_html_sections(html: str) -> List[Dict[str, Any]]:
    """Extract heading/body pairs from Ionic HTML content.

    Parses HTML content and extracts sections as heading/body pairs.
    Handles Ionic components (ion-content, ion-card) and standard HTML tags.

    Args:
        html: HTML content from Ionic template

    Returns:
        List of dicts with keys: heading, body, qualifications_required
    """
    sections = []
    current_heading = None
    current_body_parts = []

    # Normalize whitespace
    html = re.sub(r'\s+', ' ', html.strip())

    # Find all heading tags
    for match in HEADING_RE.finditer(html):
        # Save previous section if exists
        if current_heading:
            body = ' '.join(current_body_parts).strip()
            if body:
                sections.append({
                    "heading": current_heading,
                    "body": body,
                    "qualifications_required": _extract_qualifications(body),
                })

        # Start new section
        current_heading = match.group(2).strip()
        current_body_parts = []

        # Extract content after this heading until next heading
        heading_end = match.end()
        next_match = HEADING_RE.search(html, heading_end)

        if next_match:
            content_range = html[heading_end:next_match.start()]
        else:
            content_range = html[heading_end:]

        # Extract text from content
        body_text = _strip_html_tags(content_range)
        if body_text:
            current_body_parts.append(body_text)

    # Don't forget the last section
    if current_heading:
        body = ' '.join(current_body_parts).strip()
        if body:
            sections.append({
                "heading": current_heading,
                "body": body,
                "qualifications_required": _extract_qualifications(body),
            })

    return sections


def _strip_html_tags(html: str) -> str:
    """Strip HTML tags but preserve text content.

    Args:
        html: HTML string

    Returns:
        Plain text with HTML tags removed
    """
    # Remove specific Ionic/Angular components
    html = re.sub(r'<ion-content[^>]*>', '', html)
    html = re.sub(r'</ion-content>', '', html)
    html = re.sub(r'<ion-card[^>]*>', '', html)
    html = re.sub(r'</ion-card>', '', html)
    html = re.sub(r'<ion-item[^>]*>', '', html)
    html = re.sub(r'</ion-item>', '', html)

    # Convert common tags to spacing
    html = re.sub(r'</p>', ' </p>', html)
    html = re.sub(r'<li>', ' • ', html)
    html = re.sub(r'</li>', ' ', html)
    html = re.sub(r'<br\s*/?>', ' ', html)

    # Remove all remaining tags
    html = re.sub(r'<[^>]+>', '', html)

    # Clean up whitespace
    html = re.sub(r'\s+', ' ', html)

    return html.strip()


def _extract_qualifications(text: str) -> List[str]:
    """Extract qualification level markers from text.

    Args:
        text: Text content

    Returns:
        List of qualification level names found
    """
    found = []
    text_upper = text.upper()
    for level in QUALIFICATION_LEVELS:
        if level in text_upper:
            found.append(level)
    return found


def _extract_medicine_references(html: str) -> List[str]:
    """Extract medicine D-code references from HTML content.

    Args:
        html: HTML content

    Returns:
        List of D-codes found (e.g., ["D003", "D010"])
    """
    matches = D_CODE_RE.findall(html)
    # Convert to D-codes
    return [f"D{code}" for code in matches]


def _detect_dose_table(html: str) -> bool:
    """Detect presence of medication dose table in HTML.

    Args:
        html: HTML content

    Returns:
        True if dose table detected
    """
    # Check for HTML table
    if TABLE_RE.search(html):
        return True

    # Check for Ionic list (may be used as table)
    if '<ion-list' in html.lower():
        return True

    return False


def _build_source_url(cpg_code: str) -> str:
    """Build source URL for a guideline.

    Args:
        cpg_code: CPG code (e.g., "A0201-1", "D003")

    Returns:
        Full URL to the guideline on the AT site
    """
    # Remove leading/trailing whitespace
    cpg_code = cpg_code.strip()

    # Build URL based on code pattern
    # Adult guidelines: A0xxx -> /adult-patient-guidelines/...
    # Medicines: D0xx -> /medicines/...
    # For now, use a generic URL pattern
    return f"{AT_BASE_URL}/cpg/{cpg_code}"


def extract_guideline_content(
    js_content: str,
    cpg_code: str,
    title: str,
    source_bundle: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse a single lazy chunk for its guideline content.

    Extracts clinical content from a JS bundle chunk containing Angular/Ionic
    template strings. Returns structured data including sections, medicine
    references, and metadata.

    Args:
        js_content: JavaScript bundle content
        cpg_code: CPG code (e.g., "A0201-1", "D003")
        title: Guideline title
        source_bundle: Optional source bundle filename

    Returns:
        Dict with keys:
            - cpg_code: CPG code
            - title: Guideline title
            - sections: List of {heading, body, qualifications_required}
            - medicines: List of referenced medicine D-codes
            - flowcharts: Empty list (stub for future implementation)
            - source_bundle: Source bundle filename
            - has_dose_table: Whether dose table detected
            - source_url: URL to guideline on AT site
    """
    # Extract template from JS
    template_match = TEMPLATE_RE.search(js_content)

    html = ""
    if template_match:
        html = template_match.group(1)
    else:
        # Try alternative patterns (e.g., template: function() { return `...` })
        alt_match = re.search(r'return\s+`([^`]*)`', js_content, re.DOTALL)
        if alt_match:
            html = alt_match.group(1)

    # Parse sections from HTML
    sections = []
    if html:
        sections = parse_html_sections(html)

    # Extract medicine references
    medicines = []
    if html:
        medicines = _extract_medicine_references(html)

    # Detect dose table
    has_dose_table = False
    if html:
        has_dose_table = _detect_dose_table(html)

    # Build source URL
    source_url = _build_source_url(cpg_code)

    return {
        "cpg_code": cpg_code,
        "title": title,
        "sections": sections,
        "medicines": medicines,
        "flowcharts": [],  # Stub for future implementation
        "source_bundle": source_bundle or "unknown",
        "has_dose_table": has_dose_table,
        "source_url": source_url,
    }


def _load_bundle_content(bundle_filename: str, bundles_dir: Optional[str] = None) -> str:
    """Load JS bundle content from file.

    Args:
        bundle_filename: Bundle filename (e.g., "123.abc456.js")
        bundles_dir: Directory containing bundles (defaults to investigation dir)

    Returns:
        JS bundle content

    Raises:
        FileNotFoundError: If bundle file not found
    """
    if bundles_dir is None:
        # Default to investigation directory
        bundles_dir = "data/at/investigation"

    bundle_path = Path(bundles_dir) / bundle_filename

    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    with open(bundle_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_all_guidelines(
    discovery_path: str,
    output_dir: str,
    bundles_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Iterate discovery results, download each lazy chunk, extract content.

    Batch processes all guidelines discovered in the discovery phase, extracts
    their content from lazy-loaded JS chunks, and saves individual JSON files.

    Args:
        discovery_path: Path to discovery results JSON file
        output_dir: Directory to save extracted content JSON files
        bundles_dir: Directory containing JS bundles (optional)

    Returns:
        List of extracted guideline content dicts
    """
    # Load discovery results
    with open(discovery_path, 'r', encoding='utf-8') as f:
        discovery = json.load(f)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    results = []
    guidelines = discovery.get("guidelines", [])

    logger.info(f"Extracting content for {len(guidelines)} guidelines")

    for guideline_ref in guidelines:
        cpg_code = guideline_ref.get("cpg_code")
        title = guideline_ref.get("title")
        source_bundle = guideline_ref.get("source_bundle")

        if not cpg_code or not title:
            logger.warning(f"Skipping guideline with missing code/title: {guideline_ref}")
            continue

        try:
            # Load bundle content
            js_content = ""
            if source_bundle:
                try:
                    js_content = _load_bundle_content(source_bundle, bundles_dir)
                except FileNotFoundError:
                    logger.warning(f"Bundle not found for {cpg_code}: {source_bundle}")

            # Extract content
            content = extract_guideline_content(
                js_content,
                cpg_code=cpg_code,
                title=title,
                source_bundle=source_bundle,
            )

            results.append(content)

            # Save individual file
            output_file = Path(output_dir) / f"{cpg_code}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2)

            logger.info(f"Extracted {cpg_code}: {title} ({len(content['sections'])} sections)")

        except Exception as e:
            logger.error(f"Failed to extract {cpg_code}: {e}")
            # Add error entry
            results.append({
                "cpg_code": cpg_code,
                "title": title,
                "error": str(e),
                "sections": [],
                "medicines": [],
                "flowcharts": [],
                "source_bundle": source_bundle or "unknown",
                "has_dose_table": False,
                "source_url": _build_source_url(cpg_code),
            })

    logger.info(f"Extracted {len(results)} guidelines total")

    # Save summary
    summary_file = Path(output_dir) / "_extraction_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_guidelines": len(results),
            "successful_extractions": sum(1 for r in results if "error" not in r),
            "failed_extractions": sum(1 for r in results if "error" in r),
            "guidelines": results,
        }, f, indent=2)

    return results
