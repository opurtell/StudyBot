"""
Stage 2: Guideline Extraction
Extracts navigation tree from main JS bundle and route-to-chunk mappings
from the common bundle. Clinical content extraction is handled by
content_extractor.py.
"""

import json
import logging
import os
import re
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

MAIN_BUNDLE_PATTERN = re.compile(r"^2_main\.[\w]+\.js$")
COMMON_BUNDLE_PATTERN = re.compile(r"^7_common\.[\w]+\.js$")

_PAGE_OBJECT_RE = re.compile(r'\{[^{}]*?"spotlightId"\s*:\s*"([^"]+)"[^{}]*?\}')
_SECTION_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]+)"[^}]*?"pages"\s*:\s*\[')
_CMG_SECTION_RE = re.compile(r"^CMG\s+(\d+[A-Za-z]?)$")
_MED_SECTION_RE = re.compile(r"^MED(\d+)$")
_CSM_SECTION_RE = re.compile(r"^CSM\.[A-Z]+\d+$")

_ROUTE_PATTERN = re.compile(
    r'path:"([^"]+)"[^}]*?loadChildren:\(\)\s*=>\s*Promise\.all\(\[([^\]]+)\]\)'
    r"\.then\(t\.bind\(t,(\d+)\)\)\.then\(r\s*=>\s*r\.(\w+)\)"
)
_CHUNK_ID_RE = re.compile(r"t\.e\((\d+)\)")


def _find_bundle(directory: str, pattern: re.Pattern) -> Optional[str]:
    for fname in os.listdir(directory):
        if pattern.match(fname):
            return os.path.join(directory, fname)
    return None


def _extract_bracket_balanced(
    content: str, start: int, open_ch: str = "[", close_ch: str = "]"
) -> str:
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(content)):
        ch = content[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return content[start : i + 1]
    return ""


def _extract_flat_pages(content: str) -> List[Dict[str, Any]]:
    pages = []
    seen = set()
    for match in _PAGE_OBJECT_RE.finditer(content):
        raw = match.group(0)
        try:
            obj = json.loads(raw)
            sid = obj.get("spotlightId", "")
            if sid and sid not in seen:
                seen.add(sid)
                pages.append(obj)
        except json.JSONDecodeError:
            continue
    return pages


def _extract_sections(content: str) -> List[Dict[str, Any]]:
    sections = []
    for match in _SECTION_TITLE_RE.finditer(content):
        title = match.group(1)
        bracket_start = content.index("[", match.start())
        pages_json = _extract_bracket_balanced(content, bracket_start)
        if not pages_json:
            continue
        try:
            pages = json.loads(pages_json)
            sections.append({"title": title, "pages": pages})
        except json.JSONDecodeError:
            continue
    return sections


def _classify_section(cmg_number: str) -> str:
    m = _CMG_SECTION_RE.match(cmg_number)
    if not m:
        return "Other"
    num = int(re.match(r"(\d+)", m.group(1)).group(1))
    category_map = {
        1: "General Care",
        2: "Pain Management",
        3: "Airway Management",
        4: "Cardiac",
        5: "Cardiac",
        6: "Cardiac",
        7: "Cardiac",
        8: "Cardiac",
        9: "Respiratory",
        10: "Medical",
        11: "Medical",
        12: "Airway Management",
        13: "Medical",
        14: "Medical",
        15: "Medical",
        16: "Cardiac",
        17: "Trauma",
        18: "Trauma",
        19: "Trauma",
        20: "Trauma",
        21: "Trauma",
        22: "Neurology",
        23: "Neurology",
        24: "Environmental",
        25: "Environmental",
        26: "Obstetric",
        27: "Medical",
        28: "Medical",
        29: "Medical",
        30: "Trauma",
        31: "Environmental",
        32: "Behavioural",
        33: "Behavioural",
        34: "HAZMAT",
        35: "Toxicology",
        37: "Behavioural",
        38: "Medical",
        39: "Trauma",
        41: "Medical",
        42: "Medical",
        43: "Medical",
        44: "Medical",
        45: "Palliative Care",
    }
    return category_map.get(num, "Other")


def extract_navigation(
    js_bundle_path: str = "",
    investigation_dir: str = "data/cmgs/investigation/",
    output_path: str = "data/cmgs/raw/cmg_navigation.json",
) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not js_bundle_path:
        js_bundle_path = _find_bundle(investigation_dir, MAIN_BUNDLE_PATTERN) or ""

    if not js_bundle_path or not os.path.exists(js_bundle_path):
        logger.error(f"Main JS bundle not found in {investigation_dir}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {"all_pages": [], "sections": [], "cmg_count": 0, "total_pages": 0},
                f,
                indent=2,
            )
        return output_path

    with open(js_bundle_path, "r", encoding="utf-8") as f:
        content = f.read()

    all_pages = _extract_flat_pages(content)
    sections = _extract_sections(content)
    cmg_pages = [p for p in all_pages if _CMG_SECTION_RE.match(p.get("section", ""))]

    result = {
        "all_pages": all_pages,
        "sections": sections,
        "cmg_count": len(cmg_pages),
        "total_pages": len(all_pages),
        "source_file": os.path.basename(js_bundle_path),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info(
        f"Extracted {len(all_pages)} pages ({len(cmg_pages)} CMGs) from {os.path.basename(js_bundle_path)}"
    )
    return output_path


def extract_route_mappings(
    js_bundle_path: str = "",
    investigation_dir: str = "data/cmgs/investigation/",
    output_path: str = "data/cmgs/raw/route_mappings.json",
) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not js_bundle_path:
        js_bundle_path = _find_bundle(investigation_dir, COMMON_BUNDLE_PATTERN) or ""

    if not js_bundle_path or not os.path.exists(js_bundle_path):
        logger.error(f"Common JS bundle not found in {investigation_dir}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        return output_path

    with open(js_bundle_path, "r", encoding="utf-8") as f:
        content = f.read()

    id_to_file: Dict[str, str] = {}
    for fname in os.listdir(investigation_dir):
        if not fname.endswith(".js"):
            continue
        m = re.match(r"^\d+_(\d+)\.[\w]+\.js$", fname)
        if m:
            id_to_file[m.group(1)] = os.path.join(investigation_dir, fname)

    routes: Dict[str, Any] = {}
    for match in _ROUTE_PATTERN.finditer(content):
        path = match.group(1)
        chunks_str = match.group(2)
        main_id = match.group(3)
        module_name = match.group(4)

        chunk_ids = _CHUNK_ID_RE.findall(chunks_str)
        chunk_files = []
        for cid in chunk_ids:
            if cid in id_to_file:
                chunk_files.append(id_to_file[cid])

        routes[path] = {
            "path": path,
            "module_name": module_name,
            "main_chunk_id": main_id,
            "chunk_ids": chunk_ids,
            "chunk_files": chunk_files,
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(routes, f, indent=2)

    logger.info(f"Extracted {len(routes)} route mappings")
    return output_path


def extract_guidelines(
    investigation_dir: str = "data/cmgs/investigation/",
    output_path: str = "data/cmgs/raw/guidelines.json",
) -> str:
    nav_path = extract_navigation(investigation_dir=investigation_dir)
    routes_path = extract_route_mappings(investigation_dir=investigation_dir)

    with open(nav_path, "r", encoding="utf-8") as f:
        nav_data = json.load(f)

    guidelines = []
    for page in nav_data["all_pages"]:
        section = page.get("section", "")
        if not _CMG_SECTION_RE.match(section):
            continue
        guidelines.append(
            {
                "cmg_number": section.replace("CMG ", ""),
                "title": page.get("title", ""),
                "section": _classify_section(section),
                "spotlightId": page.get("spotlightId", ""),
                "tags": page.get("tags", []),
                "atp": page.get("atp", []),
                "content_html": "",
            }
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(guidelines, f, indent=2)

    logger.info(f"Extracted {len(guidelines)} CMG guideline entries to {output_path}")
    return output_path
