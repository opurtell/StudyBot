"""
Stage 2: JS Bundle Download and Parsing

Downloads and parses AT CPG JavaScript bundles to extract:
- CPG registry codes (A0xxx, D0xx, M0xx, P0xxx, E0xx patterns)
- Medicine registry (name + D-code pairs)
- Angular route definitions
- Qualification level markers

The AT CPG site is an Angular + Ionic SPA. Clinical content is embedded
in JavaScript bundles served from /assets/. This module extracts structured
metadata from those bundles.
"""

import logging
import os
import re
from typing import List, Dict, Optional
import requests

logger = logging.getLogger(__name__)

# AT CPG site base URL
AT_BASE_URL = "https://cpg.ambulance.tas.gov.au"

# Bundle filename patterns (lazy-loaded chunks use hash-based naming)
MAIN_BUNDLE_PATTERN = re.compile(r"^main\.[a-f0-9]{8,}\.js$", re.IGNORECASE)
COMMON_BUNDLE_PATTERN = re.compile(r"^common\.[a-f0-9]{8,}\.js$", re.IGNORECASE)
LAZY_CHUNK_PATTERN = re.compile(r"^\d+\.[a-f0-9]{8,}\.js$", re.IGNORECASE)

# CPG code patterns for AT Clinical Practice Guidelines
# A0xxx: Adult guidelines (with hyphenated variants A0xxx-N)
# D0xx: Drug monographs (D001-D047 expected range)
# M0xx: Medical guidelines
# P0xxx: Paediatric guidelines
# E0xx: Equipment guidelines
CPG_CODE_PATTERNS = [
    r'A\d{4}(?:-\d+)?',  # A0xxx, A0xxx-1, A0xxx-2, etc.
    r'D\d{3}',           # D001-D099
    r'M\d{3}',           # M001-M099
    r'P\d{4}',           # P0001-P9999
    r'E\d{3}',           # E001-E099
]

# Combined CPG code regex
CPG_CODE_RE = re.compile(r'\b(?:' + '|'.join(CPG_CODE_PATTERNS) + r')\b')

# D-code pattern for medicine registry (D001-D047)
D_CODE_RE = re.compile(r'"(D\d{3})"\s*:\s*"([^"]+)"')

# Angular route path pattern
ROUTE_PATH_RE = re.compile(r'path\s*:\s*["\']([^"\']*tabs/[^"\']*)["\']')

# Qualification level names (standard AT levels)
QUALIFICATION_LEVELS = [
    "VAO",
    "PARAMEDIC",
    "ICP",
    "PACER",
    "CP",
    "ECP",
]

# Combined qualification level regex
QUALIFICATION_RE = re.compile(r'\b(?:' + '|'.join(QUALIFICATION_LEVELS) + r')\b')

# Calculator route path pattern
CALCULATOR_ROUTE_RE = re.compile(r'path\s*:\s*["\']([^"\']*tabs/calculators/[^"\']*)["\']')

# Checklist route path pattern
CHECKLIST_ROUTE_RE = re.compile(r'path\s*:\s*["\']([^"\']*tabs/checklists/[^"\']*)["\']')


def _ensure_dir(directory: str) -> None:
    """Create directory if it doesn't exist."""
    os.makedirs(directory, exist_ok=True)


def _download_js_bundle(url: str, output_dir: str) -> str:
    """Download a single JS bundle from URL to output directory.

    Args:
        url: Full URL to the JS bundle
        output_dir: Directory to save the bundle

    Returns:
        Path to downloaded file

    Raises:
        requests.RequestException: If download fails
    """
    _ensure_dir(output_dir)

    filename = os.path.basename(url)
    output_path = os.path.join(output_dir, filename)

    logger.info(f"Downloading {url} -> {output_path}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(response.text)

    logger.info(f"Downloaded {len(response.text)} bytes")
    return output_path


def _find_bundle_in_dir(directory: str, pattern: re.Pattern) -> Optional[str]:
    """Find a JS bundle file matching pattern in directory.

    Args:
        directory: Directory to search
        pattern: Regex pattern to match filenames

    Returns:
        Full path to matching file or None
    """
    if not os.path.exists(directory):
        return None

    for filename in os.listdir(directory):
        if pattern.match(filename):
            return os.path.join(directory, filename)
    return None


def _discover_lazy_chunk_urls(base_url: str = AT_BASE_URL) -> List[str]:
    """Discover lazy chunk URLs by scanning the main bundle.

    This is a stub implementation. The full implementation would:
    1. Download the main bundle
    2. Scan for chunk references (e.g., __webpack_require__ calls)
    3. Build list of lazy chunk URLs

    Args:
        base_url: Base URL for the AT CPG site

    Returns:
        List of lazy chunk URLs
    """
    # Stub implementation - returns empty list
    # Full implementation will parse main bundle for chunk references
    logger.info("Lazy chunk discovery not yet implemented")
    return []


def download_main_bundle(
    output_dir: str,
    base_url: str = AT_BASE_URL
) -> str:
    """Download the main JS bundle from the AT CPG site.

    The main bundle contains the core application code and metadata
    including CPG registry, medicine registry, and qualification levels.

    Args:
        output_dir: Directory to save the bundle
        base_url: Base URL for the AT CPG site

    Returns:
        Path to downloaded main bundle

    Raises:
        requests.RequestException: If download fails
        FileNotFoundError: If bundle cannot be found after download
    """
    _ensure_dir(output_dir)

    # Try to find existing bundle first
    existing = _find_bundle_in_dir(output_dir, MAIN_BUNDLE_PATTERN)
    if existing:
        logger.info(f"Using existing main bundle: {existing}")
        return existing

    # Download main bundle from /assets/
    # Note: The actual hash in the filename changes with deployments
    # This implementation assumes a known URL pattern
    url = f"{base_url}/assets/main.js"

    try:
        return _download_js_bundle(url, output_dir)
    except requests.RequestException as e:
        logger.error(f"Failed to download main bundle: {e}")
        raise


def download_common_bundle(
    output_dir: str,
    base_url: str = AT_BASE_URL
) -> str:
    """Download the common JS bundle from the AT CPG site.

    The common bundle contains shared dependencies and Angular route
    definitions for guidelines and medicine pages.

    Args:
        output_dir: Directory to save the bundle
        base_url: Base URL for the AT CPG site

    Returns:
        Path to downloaded common bundle

    Raises:
        requests.RequestException: If download fails
        FileNotFoundError: If bundle cannot be found after download
    """
    _ensure_dir(output_dir)

    # Try to find existing bundle first
    existing = _find_bundle_in_dir(output_dir, COMMON_BUNDLE_PATTERN)
    if existing:
        logger.info(f"Using existing common bundle: {existing}")
        return existing

    # Download common bundle from /assets/
    url = f"{base_url}/assets/common.js"

    try:
        return _download_js_bundle(url, output_dir)
    except requests.RequestException as e:
        logger.error(f"Failed to download common bundle: {e}")
        raise


def download_lazy_chunks(
    output_dir: str,
    base_url: str = AT_BASE_URL
) -> List[str]:
    """Download lazy-loaded JS chunks from the AT CPG site.

    Lazy chunks contain per-guideline content that's loaded on demand.
    This function discovers available chunks and downloads them.

    Args:
        output_dir: Directory to save chunks
        base_url: Base URL for the AT CPG site

    Returns:
        List of paths to downloaded chunks
    """
    _ensure_dir(output_dir)

    # Discover lazy chunk URLs
    chunk_urls = _discover_lazy_chunk_urls(base_url)

    downloaded_paths = []
    for url in chunk_urls:
        try:
            path = _download_js_bundle(url, output_dir)
            downloaded_paths.append(path)
        except requests.RequestException as e:
            logger.warning(f"Failed to download chunk {url}: {e}")
            continue

    logger.info(f"Downloaded {len(downloaded_paths)} lazy chunks")
    return downloaded_paths


def parse_cpg_registry(js_content: str) -> List[str]:
    """Parse CPG registry codes from JS bundle content.

    Extracts all CPG codes matching AT patterns:
    - A0xxx: Adult guidelines (with variants A0xxx-N)
    - D0xx: Drug monographs
    - M0xx: Medical guidelines
    - P0xxx: Paediatric guidelines
    - E0xx: Equipment guidelines

    Args:
        js_content: JavaScript bundle content

    Returns:
        List of unique CPG codes found
    """
    matches = CPG_CODE_RE.findall(js_content)
    unique_codes = sorted(set(matches))

    logger.info(f"Found {len(unique_codes)} unique CPG codes")
    return unique_codes


def parse_medicine_registry(js_content: str) -> List[Dict[str, str]]:
    """Parse medicine registry from JS bundle content.

    Extracts medicine name + D-code pairs from the medicine registry.
    Only extracts codes in the D001-D047 range (AT formulary).

    Args:
        js_content: JavaScript bundle content

    Returns:
        List of dicts with "code" and "name" keys
    """
    medicines = []
    for match in D_CODE_RE.finditer(js_content):
        code = match.group(1)
        name = match.group(2)

        # Filter to expected D-code range (AT formulary)
        code_num = int(code[1:])
        if 1 <= code_num <= 47:  # D001-D047
            medicines.append({
                "code": code,
                "name": name
            })

    logger.info(f"Found {len(medicines)} medicines in D001-D047 range")
    return medicines


def parse_route_definitions(js_content: str) -> List[str]:
    """Parse Angular route definitions from JS bundle content.

    Extracts route paths for guideline and medicine pages.
    Filters to only include /tabs/ routes (main app navigation).

    Args:
        js_content: JavaScript bundle content

    Returns:
        List of route paths
    """
    routes = []
    for match in ROUTE_PATH_RE.finditer(js_content):
        path = match.group(1)
        # Only include /tabs/ routes
        if path.startswith("tabs/"):
            routes.append(path)

    logger.info(f"Found {len(routes)} /tabs/ routes")
    return routes


def parse_qualification_levels(js_content: str) -> List[str]:
    """Parse qualification level markers from JS bundle content.

    Extracts AT qualification level names from level selector logic.
    Standard levels: VAO, PARAMEDIC, ICP, PACER, CP, ECP

    Args:
        js_content: JavaScript bundle content

    Returns:
        List of qualification level names found
    """
    matches = QUALIFICATION_RE.findall(js_content)
    unique_levels = sorted(set(matches))

    logger.info(f"Found {len(unique_levels)} qualification levels")
    return unique_levels


def parse_calculator_routes(js_content: str) -> List[str]:
    """Parse calculator route definitions from JS bundle content.

    Extracts route slugs for calculator pages under tabs/calculators/.
    Common AT calculators: Medicine Calculator, NEWS2, CEWT, Palliative Care.

    Args:
        js_content: JavaScript bundle content

    Returns:
        List of calculator route slugs (e.g., "medicine-calculator", "news-two")
    """
    routes = []
    for match in CALCULATOR_ROUTE_RE.finditer(js_content):
        path = match.group(1)
        # Extract the slug (last segment after /calculators/)
        if "tabs/calculators/" in path:
            slug = path.split("tabs/calculators/")[-1]
            routes.append(slug)

    unique_routes = sorted(set(routes))
    logger.info(f"Found {len(unique_routes)} calculator routes")
    return unique_routes


def parse_checklist_routes(js_content: str) -> List[str]:
    """Parse checklist route definitions from JS bundle content.

    Extracts route slugs for checklist pages under tabs/checklists/.
    Common AT checklists: Clinical Handover, STEMI Referral, Reperfusion.

    Args:
        js_content: JavaScript bundle content

    Returns:
        List of checklist route slugs (e.g., "clinical-handover", "stemi-referral-script")
    """
    routes = []
    for match in CHECKLIST_ROUTE_RE.finditer(js_content):
        path = match.group(1)
        # Extract the slug (last segment after /checklists/)
        if "tabs/checklists/" in path:
            slug = path.split("tabs/checklists/")[-1]
            routes.append(slug)

    unique_routes = sorted(set(routes))
    logger.info(f"Found {len(unique_routes)} checklist routes")
    return unique_routes


def extract_calculator_content(js_content: str, route_slug: str) -> Dict[str, any]:
    """Extract calculator content from JS bundle for a specific route.

    Extracts structured text content for a calculator identified by route slug.
    Returns a dict with route metadata and the relevant JS content.

    Args:
        js_content: JavaScript bundle content
        route_slug: Calculator route slug (e.g., "medicine-calculator")

    Returns:
        Dict with keys: route_slug, js_content (truncated snippet)
    """
    # In a full implementation, this would extract the actual calculator
    # configuration, field definitions, and logic from the JS bundle.
    # For now, return a placeholder with the route slug.

    result = {
        "route_slug": route_slug,
        "content_type": "calculator",
        "js_content": js_content[:1000] if len(js_content) > 1000 else js_content,  # Truncate for logging
    }

    logger.info(f"Extracted calculator content for route: {route_slug}")
    return result


def extract_checklist_content(js_content: str, route_slug: str) -> Dict[str, any]:
    """Extract checklist content from JS bundle for a specific route.

    Extracts structured text content for a checklist identified by route slug.
    Returns a dict with route metadata and the relevant JS content.

    Args:
        js_content: JavaScript bundle content
        route_slug: Checklist route slug (e.g., "clinical-handover")

    Returns:
        Dict with keys: route_slug, content_type, js_content (truncated snippet)
    """
    # In a full implementation, this would extract the actual checklist
    # items, steps, and structure from the JS bundle.
    # For now, return a placeholder with the route slug.

    result = {
        "route_slug": route_slug,
        "content_type": "checklist",
        "source_type": "checklist",  # For GuidelineDocument metadata
        "js_content": js_content[:1000] if len(js_content) > 1000 else js_content,  # Truncate for logging
    }

    logger.info(f"Extracted checklist content for route: {route_slug}")
    return result


def extract_all_metadata(
    investigation_dir: str
) -> Dict[str, any]:
    """Extract all metadata from downloaded JS bundles.

    Convenience function that runs all parsers on downloaded bundles
    and returns a consolidated metadata dict.

    Args:
        investigation_dir: Directory containing downloaded JS bundles

    Returns:
        Dict with keys: cpg_codes, medicines, routes, qualification_levels
    """
    result = {
        "cpg_codes": [],
        "medicines": [],
        "routes": [],
        "qualification_levels": [],
    }

    # Find and parse main bundle
    main_bundle = _find_bundle_in_dir(investigation_dir, MAIN_BUNDLE_PATTERN)
    if main_bundle:
        with open(main_bundle, 'r', encoding='utf-8') as f:
            main_content = f.read()

        result["cpg_codes"] = parse_cpg_registry(main_content)
        result["medicines"] = parse_medicine_registry(main_content)
        result["qualification_levels"] = parse_qualification_levels(main_content)
    else:
        logger.warning(f"Main bundle not found in {investigation_dir}")

    # Find and parse common bundle
    common_bundle = _find_bundle_in_dir(investigation_dir, COMMON_BUNDLE_PATTERN)
    if common_bundle:
        with open(common_bundle, 'r', encoding='utf-8') as f:
            common_content = f.read()

        result["routes"] = parse_route_definitions(common_content)
    else:
        logger.warning(f"Common bundle not found in {investigation_dir}")

    return result
