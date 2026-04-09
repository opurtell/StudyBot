# CMG Core Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract all 52 ACTAS clinical management guidelines from downloaded JS bundles into structured, queryable data in ChromaDB.

**Architecture:** Three-stage offline pipeline — (1) extract navigation/TOC from main JS bundle, (2) parse Angular compiled templates in lazy-loaded chunks for clinical content, (3) merge and feed into existing structurer/chunker. All data is already in `data/cmgs/investigation/`.

**Tech Stack:** Python 3.10+, regex, json, chromadb, langchain, pydantic

**Design spec:** `docs/superpowers/specs/2026-04-02-cmg-extraction-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/python/pipeline/cmg/template_parser.py` | **Create** | Parse Angular compiled template instructions → extract text content |
| `src/python/pipeline/cmg/extractor.py` | **Rewrite** | Extract navigation tree + route mappings from main bundle |
| `src/python/pipeline/cmg/dose_tables.py` | **Update** | Extract real dose data from `7_common.*.js` |
| `src/python/pipeline/cmg/orchestrator.py` | **Update** | Wire new `extract-navigation` and `extract-content` stages |
| `tests/python/test_cmg_extraction.py` | **Create** | Tests for navigation extraction, template parsing, dose tables |
| `data/cmgs/raw/cmg_navigation.json` | **Output** | Navigation tree with all CMG entries and metadata |
| `data/cmgs/raw/cmg_content.json` | **Output** | Clinical text content keyed by spotlightId |
| `data/cmgs/raw/guidelines.json` | **Output** | Merged navigation + content (replaces empty mock) |
| `data/cmgs/raw/dose_tables.json` | **Output** | Real dose lookup tables |

---

### Task 1: Navigation Extractor — Extract CMG TOC from Main Bundle

**Files:**
- Modify: `src/python/pipeline/cmg/extractor.py` (full rewrite)
- Create: `tests/python/test_cmg_extraction.py`

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_cmg_extraction.py`:

```python
"""Tests for CMG extraction pipeline — navigation and content."""
import json
import os
import tempfile
import pytest


class TestNavigationExtraction:
    """Tests for Stage 1: Navigation/TOC extraction from main JS bundle."""

    SAMPLE_MAIN_BUNDLE = '''
    var x=1;
    {"title":"Settings","sectionId":"settings","icon":"folder","atp":["p","icp"],"pages":[{"title":"General Care","section":"CMG 1","spotlightId":"1iA3FOWukpEi","icon":"angle-double-right","color":"default","atp":["p","icp"],"tags":["patient"]},{"title":"Pain Management","section":"CMG 2","spotlightId":"Tanp4PgrNR2yWw0I","icon":"angle-double-right","color":"default","atp":["p","icp"],"tags":["pain","analgesia"]}]}
    var y=2;
    {"title":"Another Section","sectionId":"other","pages":[{"title":"Glasgow Coma Score","section":"","spotlightId":"g9W5SSHS","icon":"angle-double-right","color":"default","atp":["p","icp"]}]}
    '''

    def test_extract_navigation_finds_cmg_entries(self, tmp_path):
        """Should extract entries with CMG section numbers."""
        from pipeline.cmg.extractor import extract_navigation

        bundle_path = tmp_path / "main.js"
        bundle_path.write_text(self.SAMPLE_MAIN_BUNDLE)

        output_path = tmp_path / "nav.json"
        result = extract_navigation(str(bundle_path), str(output_path))

        with open(result) as f:
            data = json.load(f)

        cmg_entries = [e for e in data["all_pages"] if e.get("section", "").startswith("CMG")]
        assert len(cmg_entries) >= 2
        titles = {e["title"] for e in cmg_entries}
        assert "General Care" in titles
        assert "Pain Management" in titles

    def test_extract_navigation_preserves_metadata(self, tmp_path):
        """Should preserve spotlightId, tags, atp, icon metadata."""
        from pipeline.cmg.extractor import extract_navigation

        bundle_path = tmp_path / "main.js"
        bundle_path.write_text(self.SAMPLE_MAIN_BUNDLE)

        output_path = tmp_path / "nav.json"
        extract_navigation(str(bundle_path), str(output_path))

        with open(output_path) as f:
            data = json.load(f)

        cmg_1 = next(e for e in data["all_pages"] if e.get("section") == "CMG 1")
        assert cmg_1["spotlightId"] == "1iA3FOWukpEi"
        assert "patient" in cmg_1["tags"]
        assert "p" in cmg_1["atp"]

    def test_extract_navigation_handles_missing_file(self, tmp_path):
        """Should return empty result, not crash, for missing bundle."""
        from pipeline.cmg.extractor import extract_navigation

        result = extract_navigation(
            str(tmp_path / "nonexistent.js"),
            str(tmp_path / "nav.json")
        )

        with open(result) as f:
            data = json.load(f)
        assert data["all_pages"] == []
        assert data["sections"] == []

    def test_extract_navigation_extracts_sections(self, tmp_path):
        """Should extract section/grouping hierarchy."""
        from pipeline.cmg.extractor import extract_navigation

        bundle_path = tmp_path / "main.js"
        bundle_path.write_text(self.SAMPLE_MAIN_BUNDLE)

        output_path = tmp_path / "nav.json"
        extract_navigation(str(bundle_path), str(output_path))

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["sections"]) >= 1
        # At least one section should have pages
        sections_with_pages = [s for s in data["sections"] if s.get("pages")]
        assert len(sections_with_pages) >= 1


class TestRouteMapping:
    """Tests for component-to-route mapping extraction."""

    SAMPLE_ROUTES = '''
    const routes=[{path:"",redirectTo:"tabs/guidelines",pathMatch:"full"},{path:"cmg-1-general-care/:spotlightId",loadChildren:()=>import("./114_30259.bc1c95995a3fe02e.js").then(e=>e.Cmg1GeneralCareModule)},{path:"cmg-2-pain-management/:spotlightId",loadChildren:()=>import("./7_common.d79180c97e61e8b5.js").then(e=>e.Cmg2PainModule)}];
    '''

    def test_extract_route_mapping(self, tmp_path):
        """Should map route paths to chunk filenames."""
        from pipeline.cmg.extractor import extract_route_mappings

        bundle_path = tmp_path / "main.js"
        bundle_path.write_text(self.SAMPLE_ROUTES)

        output_path = tmp_path / "routes.json"
        result = extract_route_mappings(str(bundle_path), str(output_path))

        with open(result) as f:
            routes = json.load(f)

        assert "114_30259.bc1c95995a3fe02e.js" in routes
        assert routes["114_30259.bc1c95995a3fe02e.js"]["path"] == "cmg-1-general-care/:spotlightId"

    def test_extract_route_mapping_empty_bundle(self, tmp_path):
        """Should return empty dict for bundle with no routes."""
        from pipeline.cmg.extractor import extract_route_mappings

        bundle_path = tmp_path / "main.js"
        bundle_path.write_text("var x=1;")

        output_path = tmp_path / "routes.json"
        result = extract_route_mappings(str(bundle_path), str(output_path))

        with open(result) as f:
            routes = json.load(f)
        assert routes == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/python/test_cmg_extraction.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_navigation'`

- [ ] **Step 3: Implement navigation extraction**

Rewrite `src/python/pipeline/cmg/extractor.py`:

```python
"""
Stage 2: Guideline Extraction
Extracts navigation tree and route mappings from the main JS bundle,
then parses clinical content from lazy-loaded chunks.
"""
import json
import logging
import os
import re
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Patterns for finding page objects in the JS bundle
SPOTLIGHT_ID_PATTERN = re.compile(r'"spotlightId"\s*:\s*"([^"]+)"')
PAGE_OBJECT_PATTERN = re.compile(r'\{[^{}]*"spotlightId"[^{}]*\}')
# Pattern for finding arrays of page objects (may be nested)
PAGES_ARRAY_PATTERN = re.compile(r'\[(\{[^]]*?"spotlightId"[^]]*?\})(\,\{[^]]*?"spotlightId"[^]]*?\})*\]')
# Pattern for route definitions with lazy loading
ROUTE_PATTERN = re.compile(
    r'\{path\s*:\s*"([^"]+)"[^}]*?loadChildren\s*:\s*\(\)\s*=>\s*import\("([^"]+)"\)'
)


def _extract_json_with_bracket_matching(content: str, start_pos: int) -> str:
    """Extract a JSON array starting at start_pos using balanced bracket matching."""
    bracket_count = 0
    for i in range(start_pos, len(content)):
        if content[i] == '[':
            bracket_count += 1
        elif content[i] == ']':
            bracket_count -= 1
            if bracket_count == 0:
                return content[start_pos:i + 1]
    return ""


def _extract_page_objects(content: str) -> List[Dict[str, Any]]:
    """Extract all individual page objects containing spotlightId from JS content."""
    pages = []
    seen_ids = set()

    for match in PAGE_OBJECT_PATTERN.finditer(content):
        raw = match.group(0)
        try:
            obj = json.loads(raw)
            sid = obj.get("spotlightId", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                pages.append(obj)
        except json.JSONDecodeError:
            continue

    return pages


def _extract_section_arrays(content: str) -> List[Dict[str, Any]]:
    """Extract section objects that contain nested pages arrays."""
    sections = []
    # Find objects that have both a sectionId/title AND a pages array
    # These are parent groupings like "Clinical Protocols", "Skills", etc.
    section_pattern = re.compile(
        r'\{[^{}]*"title"\s*:\s*"([^"]+)"[^{}]*"pages"\s*:\s*\['
    )
    for match in section_pattern.finditer(content):
        title = match.group(1)
        # Find the pages array start
        pages_start = content.index("[", match.start() + len(match.group(0)) - 1)
        # Go back to find the full section object start
        obj_start = content.rfind("{", 0, match.start() + 1)

        # Extract pages array using bracket matching from the "[" position
        pages_json = _extract_json_with_bracket_matching(content, pages_start)
        if not pages_json:
            continue

        try:
            pages = json.loads(pages_json)
            sections.append({
                "title": title,
                "pages": pages
            })
        except json.JSONDecodeError:
            continue

    return sections


def extract_navigation(
    js_bundle_path: str = "data/cmgs/investigation/2_main.c43a7059549a252e.js",
    output_path: str = "data/cmgs/raw/cmg_navigation.json"
) -> str:
    """Extract the full navigation tree from the main JS bundle.

    Returns path to the output JSON file containing:
    - all_pages: flat list of all page objects with spotlightId
    - sections: grouped sections with their child pages
    - cmg_count: number of pages with CMG section numbers
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not os.path.exists(js_bundle_path):
        logger.error(f"JS bundle not found at {js_bundle_path}")
        result = {"all_pages": [], "sections": [], "cmg_count": 0}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return output_path

    with open(js_bundle_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract all page objects
    all_pages = _extract_page_objects(content)
    sections = _extract_section_arrays(content)

    cmg_pages = [p for p in all_pages if p.get("section", "").startswith("CMG")]

    result = {
        "all_pages": all_pages,
        "sections": sections,
        "cmg_count": len(cmg_pages),
        "total_pages": len(all_pages),
        "source_file": os.path.basename(js_bundle_path)
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Extracted {len(all_pages)} pages ({len(cmg_pages)} CMGs) from {js_bundle_path}")
    return output_path


def extract_route_mappings(
    js_bundle_path: str = "data/cmgs/investigation/2_main.c43a7059549a252e.js",
    output_path: str = "data/cmgs/raw/route_mappings.json"
) -> str:
    """Extract lazy-loading route definitions mapping paths to JS chunk files.

    Returns path to JSON file: { "chunk_filename": { "path": "...", "module": "..." } }
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not os.path.exists(js_bundle_path):
        logger.error(f"JS bundle not found at {js_bundle_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return output_path

    with open(js_bundle_path, "r", encoding="utf-8") as f:
        content = f.read()

    routes = {}
    for match in ROUTE_PATTERN.finditer(content):
        path = match.group(1)
        chunk_file = match.group(2)
        # Strip ./ prefix if present
        chunk_file = chunk_file.lstrip("./")
        routes[chunk_file] = {"path": path}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(routes, f, indent=2)

    logger.info(f"Extracted {len(routes)} route mappings")
    return output_path


def extract_guidelines(
    js_bundle_path: str = "data/cmgs/investigation/2_main.c43a7059549a252e.js",
    output_path: str = "data/cmgs/raw/guidelines.json"
) -> str:
    """High-level extraction: navigation + route mappings.

    Content extraction is a separate stage (see content_extractor).
    """
    nav_path = extract_navigation(js_bundle_path)
    routes_path = extract_route_mappings(js_bundle_path)

    # Read navigation and convert CMG pages to guideline format
    with open(nav_path, "r", encoding="utf-8") as f:
        nav_data = json.load(f)

    guidelines = []
    for page in nav_data["all_pages"]:
        section = page.get("section", "")
        if not section.startswith("CMG"):
            continue
        guidelines.append({
            "cmg_number": section.replace("CMG ", ""),
            "title": page.get("title", ""),
            "section": _classify_section(section),
            "spotlightId": page.get("spotlightId", ""),
            "tags": page.get("tags", []),
            "atp": page.get("atp", []),
            "content_html": "",  # Filled by content extraction stage
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(guidelines, f, indent=2)

    logger.info(f"Extracted {len(guidelines)} CMG guideline entries to {output_path}")
    return output_path


def _classify_section(cmg_number: str) -> str:
    """Map CMG number to a clinical category."""
    try:
        num = int(cmg_number.replace("CMG ", "").rstrip("ABCDabcd"))
    except ValueError:
        return "Other"

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
        11: "Environmental",
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
