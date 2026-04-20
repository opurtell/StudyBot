"""
Content Extractor for CMG Pipeline
Extracts clinical text from Angular compiled templates across JS bundles,
maps content to CMG navigation entries via route-to-path matching.
"""

import json
import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple

from .template_parser import (
    parse_template_instructions,
    html_to_markdown,
    extract_text_from_file,
)

logger = logging.getLogger(__name__)

MAIN_BUNDLE_RE = re.compile(r"^2_main\.[\w]+\.js$")
COMMON_BUNDLE_RE = re.compile(r"^7_common\.[\w]+\.js$")
CHUNK_FILE_RE = re.compile(r"^\d+_(\d+)\.[\w]+\.js$")

_CMG_SECTION_RE = re.compile(r"^CMG\s+(\d+[A-Za-z]?)$")
_MED_SECTION_RE = re.compile(r"^MED(\d+)$")
_CSM_SECTION_RE = re.compile(r"^CSM\.[A-Z]+\d+$")
_ROUTE_PATTERN = re.compile(
    r'path:"([^"]+)"[^}]*?loadChildren:\(\)\s*=>\s*Promise\.all\(\[([^\]]+)\]\)'
    r"\.then\(t\.bind\(t,(\d+)\)\)\.then\(r\s*=>\s*r\.(\w+)\)"
)
_CHUNK_ID_RE = re.compile(r"t\.e\((\d+)\)")
_PAGE_OBJECT_RE = re.compile(r'\{[^{}]*?"spotlightId"\s*:\s*"([^"]+)"[^{}]*?\}')


def _find_bundle(directory: str, pattern: re.Pattern) -> Optional[str]:
    for fname in os.listdir(directory):
        if pattern.match(fname):
            return os.path.join(directory, fname)
    return None


def _build_chunk_id_map(investigation_dir: str) -> Dict[str, str]:
    id_to_file = {}
    for fname in os.listdir(investigation_dir):
        if not fname.endswith(".js"):
            continue
        m = CHUNK_FILE_RE.match(fname)
        if m:
            id_to_file[m.group(1)] = os.path.join(investigation_dir, fname)
    return id_to_file


def _title_to_path(title: str) -> str:
    path = title.lower()
    path = re.sub(r"[^a-z0-9\s-]", "", path)
    path = re.sub(r"\s+", "-", path).strip("-")
    return path


_NUM_WORDS = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "11": "eleven",
    "12": "twelve",
    "13": "thirteen",
    "14": "fourteen",
    "15": "fifteen",
    "16": "sixteen",
    "17": "seventeen",
    "18": "eighteen",
    "19": "nineteen",
    "20": "twenty",
}
_WORD_NUMS = {v: k for k, v in _NUM_WORDS.items()}


def _normalize_for_matching(slug: str) -> str:
    slug = slug.replace("-", " ")
    for num, word in _NUM_WORDS.items():
        slug = re.sub(r"\b" + num + r"\b", word, slug)
    return slug


def _word_overlap_score(slug_a: str, slug_b: str) -> int:
    words_a = set(_normalize_for_matching(slug_a).split())
    words_b = set(_normalize_for_matching(slug_b).split())
    return len(words_a & words_b)


def _distinctive_overlap_score(slug_a: str, slug_b: str) -> int:
    words_a = set(_normalize_for_matching(slug_a).split())
    words_b = set(_normalize_for_matching(slug_b).split())
    overlap = words_a & words_b
    if len(overlap) >= 2:
        return len(overlap)
    if len(overlap) == 1:
        word = next(iter(overlap))
        if len(word) >= 5:
            return 1
    return 0


def _find_route_for_title(title: str, route_map: Dict[str, Any]) -> Optional[str]:
    direct = _title_to_path(title)
    if direct in route_map:
        return direct

    direct_norm = _normalize_for_matching(direct)
    for route_path in route_map:
        route_norm = _normalize_for_matching(route_path.split("/:")[0])
        if direct_norm == route_norm:
            return route_path

    for route_path in route_map:
        route_base = route_path.split("/:")[0]
        if direct.startswith(route_base):
            return route_path
        if route_base.startswith(direct[: max(5, len(direct) // 2)]):
            return route_path

    best_match = None
    best_score = 0
    for route_path in route_map:
        route_base = route_path.split("/:")[0]
        score = _word_overlap_score(direct, route_base)
        if score > best_score:
            best_score = score
            best_match = route_path

    if best_match and best_score >= 2:
        return best_match
    return None


def _extract_navigation_titles(investigation_dir: str) -> List[Dict[str, str]]:
    main_path = _find_bundle(investigation_dir, MAIN_BUNDLE_RE)
    if not main_path:
        return []

    with open(main_path, "r", encoding="utf-8") as f:
        content = f.read()

    titles = []
    seen = set()
    for match in _PAGE_OBJECT_RE.finditer(content):
        try:
            obj = json.loads(match.group(0))
            section = obj.get("section", "")
            title = obj.get("title", "")
            sid = obj.get("spotlightId", "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            if _CMG_SECTION_RE.match(section):
                entry_type = "cmg"
            elif _MED_SECTION_RE.match(section):
                entry_type = "med"
            elif _CSM_SECTION_RE.match(section):
                entry_type = "csm"
            else:
                entry_type = "other"
            titles.append(
                {
                    "title": title,
                    "section": section,
                    "spotlightId": sid,
                    "route_path": _title_to_path(title),
                    "entry_type": entry_type,
                }
            )
        except json.JSONDecodeError:
            continue
    return titles


def _extract_route_map(investigation_dir: str) -> Dict[str, Dict[str, Any]]:
    common_path = _find_bundle(investigation_dir, COMMON_BUNDLE_RE)
    if not common_path:
        return {}

    with open(common_path, "r", encoding="utf-8") as f:
        content = f.read()

    id_to_file = _build_chunk_id_map(investigation_dir)
    routes = {}

    for match in _ROUTE_PATTERN.finditer(content):
        path = match.group(1)
        chunks_str = match.group(2)
        main_id = match.group(3)
        module_name = match.group(4)

        chunk_ids = _CHUNK_ID_RE.findall(chunks_str)
        chunk_files = [id_to_file[cid] for cid in chunk_ids if cid in id_to_file]

        routes[path] = {
            "path": path,
            "module_name": module_name,
            "main_chunk_id": main_id,
            "chunk_files": chunk_files,
            "common_bundle": common_path,
        }
    return routes


def _extract_content_from_file(file_path: str) -> List[Dict[str, Any]]:
    results = extract_text_from_file(file_path)
    for r in results:
        r["source_file"] = os.path.basename(file_path)
    return results


def _find_content_for_route(
    route_path: str,
    route_info: Dict[str, Any],
    all_content: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    matched = []
    boilerplate_files = {
        "22_30839.555b62faa3e247c2.js",
        "25_77083.404555ff246dc8c7.js",
        "25_77083.555b62faa3e247c2.js",
    }

    for chunk_file in route_info.get("chunk_files", []):
        fname = os.path.basename(chunk_file)
        if fname in boilerplate_files:
            continue
        if fname in all_content:
            matched.extend(all_content[fname])

    return matched


def extract_content(
    investigation_dir: str = "data/cmgs/investigation/",
    output_path: str = "data/cmgs/raw/cmg_content.json",
) -> str:
    from .selector_extractor import extract_selector_templates
    from .template_parser import strip_boilerplate, strip_boilerplate_md

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    nav_titles = _extract_navigation_titles(investigation_dir)
    route_map = _extract_route_map(investigation_dir)

    all_files: Dict[str, List[Dict[str, Any]]] = {}
    for fname in os.listdir(investigation_dir):
        if not fname.endswith(".js"):
            continue
        fpath = os.path.join(investigation_dir, fname)
        blocks = _extract_content_from_file(fpath)
        if blocks:
            all_files[fname] = blocks

    selector_templates = extract_selector_templates(investigation_dir=investigation_dir)
    selector_map: Dict[str, Dict[str, Any]] = {}
    for st in selector_templates:
        selector_map[st["route_path"]] = st

    content_map: Dict[str, Dict[str, Any]] = {}
    for entry in nav_titles:
        path = _find_route_for_title(entry["title"], route_map)
        route_blocks: List[Dict[str, Any]] = []

        if path and path in route_map:
            route_info = route_map[path]
            route_blocks = _find_content_for_route(path, route_info, all_files)

        if route_blocks:
            combined_html = "\n".join(b["html"] for b in route_blocks)
        else:
            route_slug = _title_to_path(entry["title"])
            sel_entry = selector_map.get(route_slug)
            if not sel_entry:
                best_sel_score = 0
                for sel_route, sel_data in selector_map.items():
                    score = _distinctive_overlap_score(route_slug, sel_route)
                    if score > best_sel_score:
                        best_sel_score = score
                        sel_entry = sel_data
                if best_sel_score < 1:
                    sel_entry = None
            if sel_entry:
                combined_html = sel_entry["html"]
            else:
                combined_html = ""

        if not combined_html:
            content_map[entry["spotlightId"]] = {
                "title": entry["title"],
                "section": entry["section"],
                "route_path": entry["route_path"],
                "entry_type": entry["entry_type"],
                "html": "",
                "markdown": "",
                "template_blocks": 0,
                "source": "none",
            }
            continue

        cleaned_html = strip_boilerplate(combined_html)
        combined_md = html_to_markdown(cleaned_html)
        combined_md = strip_boilerplate_md(combined_md)

        source = "selector" if not route_blocks else "route_chunks"
        content_map[entry["spotlightId"]] = {
            "title": entry["title"],
            "section": entry["section"],
            "route_path": entry["route_path"],
            "entry_type": entry["entry_type"],
            "html": cleaned_html,
            "markdown": combined_md,
            "template_blocks": len(route_blocks) if route_blocks else 1,
            "source": source,
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(content_map, f, indent=2)

    cmg_count = sum(1 for v in content_map.values() if v.get("entry_type") == "cmg")
    with_content = sum(
        1
        for v in content_map.values()
        if v.get("entry_type") == "cmg" and len(v["markdown"]) > 50
    )
    logger.info(
        f"Extracted content for {len(content_map)} pages "
        f"({cmg_count} CMGs, {with_content} with clinical content)"
    )
    return output_path


def merge_navigation_and_content(
    nav_path: str = "data/cmgs/raw/cmg_navigation.json",
    content_path: str = "data/cmgs/raw/cmg_content.json",
    output_path: str = "data/cmgs/raw/guidelines.json",
) -> str:
    from .extractor import _classify_section

    with open(nav_path, "r", encoding="utf-8") as f:
        nav_data = json.load(f)
    with open(content_path, "r", encoding="utf-8") as f:
        content_data = json.load(f)

    guidelines = []
    for page in nav_data.get("all_pages", []):
        section = page.get("section", "")
        if not (
            _CMG_SECTION_RE.match(section)
            or _MED_SECTION_RE.match(section)
            or _CSM_SECTION_RE.match(section)
        ):
            continue
        sid = page.get("spotlightId", "")
        content_entry = content_data.get(sid, {})
        if _CMG_SECTION_RE.match(section):
            entry_type = "cmg"
            cmg_number = section.replace("CMG ", "")
        elif _MED_SECTION_RE.match(section):
            entry_type = "med"
            cmg_number = section.replace("MED", "")
        else:
            entry_type = "csm"
            cmg_number = section
        guidelines.append(
            {
                "cmg_number": cmg_number,
                "title": page.get("title", ""),
                "section": _classify_section(section)
                if _CMG_SECTION_RE.match(section)
                else ("Medicine" if entry_type == "med" else "Clinical Skill"),
                "spotlightId": sid,
                "tags": page.get("tags", []),
                "atp": page.get("atp", []),
                "content_html": content_entry.get("html", ""),
                "content_markdown": content_entry.get("markdown", ""),
                "entry_type": entry_type,
            }
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(guidelines, f, indent=2)

    with_content = sum(1 for g in guidelines if g["content_html"])
    logger.info(f"Merged {len(guidelines)} guidelines ({with_content} with content)")
    return output_path
