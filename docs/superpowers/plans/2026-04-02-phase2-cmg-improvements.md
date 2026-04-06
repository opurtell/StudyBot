# Phase 2 CMG Pipeline Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the CMG extraction pipeline so all 55 CMGs have real clinical content (currently only 12 of 55 do), strip UI boilerplate, and segment dose data per route.

**Architecture:** The root cause is that 42 of 55 CMG pages store their clinical templates inside `7_common.*.js` (a shared Angular module), not in route-specific chunk files. The current pipeline only extracts content from route-specific chunks, missing these 42 CMGs entirely. The fix uses Angular component selectors (`selectors:[["app-X"]]`) to map each template block to its CMG page. Two additional CMGs (5, 44) are unmatched because `_title_to_path` strips parentheses from titles like "Cardiac Arrest: Paediatric (<12 years old)".

**Tech Stack:** Python 3.10+, pytest, ChromaDB, langchain-text-splitters

---

## Context for the Implementer

### Current State

- 55 CMGs extracted from navigation
- Only 12 have real clinical content (from route-specific chunks)
- 42 have only UI boilerplate ("More information", "My Notes", "Tap to zoom", "Open print version")
- 1 CMG (5) has zero content due to title-to-slug mismatch
- 1 CMG (44) has zero content due to title-to-slug mismatch

### How the SPA Works

The ACTAS CMG web app is an Ionic/Angular SPA. Clinical content lives in compiled Angular component templates inside JS bundles. Two content locations exist:

1. **7_common.\*.js** — Shared module containing 229 page component templates (selectors + template functions). 42 CMG pages have their ONLY clinical content here. The 4 boilerplate blocks ("More information", "My Notes", "Tap to zoom", "Open print version") also come from this file but from a different shared chunk (`25_77083`).

2. **Route-specific chunks** (e.g. `75_67997.*.js`) — 13 CMG pages have their content in these standalone chunks. These already work.

### Key Files to Touch

- **Create:** `src/python/pipeline/cmg/selector_extractor.py` — New module: selector-to-template extraction from 7_common
- **Modify:** `src/python/pipeline/cmg/content_extractor.py` — Fix `_title_to_path`, integrate selector-based extraction, strip boilerplate
- **Modify:** `src/python/pipeline/cmg/structurer.py` — Add content length sanity check
- **Modify:** `src/python/pipeline/cmg/dose_tables.py` — Segment dose groups per source file/route
- **Modify:** `src/python/pipeline/cmg/orchestrator.py` — Add new pipeline stage
- **Modify:** `tests/python/test_cmg_extraction.py` — Tests for new functionality
- **Modify:** `tests/python/test_cmg_pipeline.py` — Tests for integration

### Boilerplate Patterns to Strip

These HTML/Markdown patterns are UI chrome, not clinical content:

| HTML Pattern | Markdown Output |
|---|---|
| `<span>More information<fa-icon /></span>` | "More information" |
| `<section><h4>My Notes</h4><div></div></section>` | "#### My Notes" |
| `<span>Tap to zoom</span>` | "Tap to zoom" |
| `<ion-button>Open print version</ion-button>` | "Open print version" |
| `<content-header />` | (empty) |
| `<section-menu></section-menu>` | (empty) |
| `<print>` / `<print ...>` | (empty) |
| `<ion-content>` / `</ion-content>` | (empty) |
| `<ion-header>` / toolbar / buttons | (empty) |

---

## Task 1: Selector-Based Template Extractor

**Files:**
- Create: `src/python/pipeline/cmg/selector_extractor.py`
- Test: `tests/python/test_cmg_extraction.py`

This is the core new module that extracts clinical content from 7_common using Angular component selectors.

- [ ] **Step 1: Write the failing test for selector extraction**

Add to `tests/python/test_cmg_extraction.py`:

```python
class TestSelectorExtractor:
    def test_extract_selectors_from_bundle(self, tmp_path):
        from pipeline.cmg.selector_extractor import extract_selector_templates

        bundle = tmp_path / "7_common.test123.js"
        bundle.write_text(
            'selectors:[["app-general-care"]],features:[e.Vt3],decls:147,'
            'vars:15,consts:[[3,"data",4,"ngIf"]],template:function(c,i){1&c&&('
            'e.j41(0,"ion-content")(1,"div")(2,"section")(3,"h4"),'
            'e.EFF(4,"Patient Centred Care"),h.k0s(),'
            'e.j41(5,"p"),e.EFF(6,"Treat all patients with dignity."),'
            'h.k0s()()())}'
        )

        results = extract_selector_templates(str(bundle))
        assert len(results) == 1
        assert results[0]["selector"] == "app-general-care"
        assert "Patient Centred Care" in results[0]["html"]
        assert "Treat all patients with dignity" in results[0]["html"]

    def test_extract_multiple_selectors(self, tmp_path):
        from pipeline.cmg.selector_extractor import extract_selector_templates

        bundle = tmp_path / "7_common.test123.js"
        bundle.write_text(
            'selectors:[["app-pain-management"]],template:function(c,i){'
            '1&c&&(e.EFF(0,"Pain Scale"))}'
            '\nselectors:[["app-shock"]],template:function(c,i){'
            '1&c&&(e.EFF(0,"Shock Management"))}'
        )

        results = extract_selector_templates(str(bundle))
        assert len(results) == 2
        selectors = {r["selector"] for r in results}
        assert "app-pain-management" in selectors
        assert "app-shock" in selectors

    def test_selector_to_route_path(self):
        from pipeline.cmg.selector_extractor import selector_to_route

        assert selector_to_route("app-general-care") == "general-care"
        assert selector_to_route("app-cardiac-arrest-adult") == "cardiac-arrest-adult"
        assert selector_to_route("app-cresst-screening-tool") == "cresst-screening-tool"

    def test_extract_selectors_missing_file(self, tmp_path):
        from pipeline.cmg.selector_extractor import extract_selector_templates

        results = extract_selector_templates(str(tmp_path / "nonexistent.js"))
        assert results == []

    def test_integration_selector_extraction_from_real_bundle(self, tmp_path):
        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        from pipeline.cmg.selector_extractor import extract_selector_templates
        import glob

        common_files = glob.glob(os.path.join(inv_dir, "7_common.*.js"))
        if not common_files:
            pytest.skip("No 7_common bundle")

        results = extract_selector_templates(common_files[0])
        assert len(results) >= 200

        selectors = {r["selector"] for r in results}
        assert "app-general-care" in selectors
        assert "app-bradyarrhythmias" in selectors

        general_care = next(r for r in results if r["selector"] == "app-general-care")
        assert "Patient Centred Care" in general_care["html"]
        assert len(general_care["html"]) > 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestSelectorExtractor -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.cmg.selector_extractor'`

- [ ] **Step 3: Implement `src/python/pipeline/cmg/selector_extractor.py`**

```python
"""
Stage 2b: Selector-Based Template Extraction
Extracts clinical content from 7_common by mapping Angular component
selectors to their compiled template functions.
"""

import logging
import os
import re
from typing import List, Dict, Any, Optional

from .template_parser import (
    parse_template_instructions,
    _find_template_boundaries,
)

logger = logging.getLogger(__name__)

_COMMON_BUNDLE_RE = re.compile(r"^7_common\.[\w]+\.js$")

_SELECTOR_RE = re.compile(r'selectors:\[\["([^"]+)"\]\]')
_TEMPLATE_RE = re.compile(
    r"template:\s*function\s*\(\s*\w+\s*,\s*\w+\s*\)\s*\{"
)


def _find_common_bundle(directory: str) -> Optional[str]:
    for fname in os.listdir(directory):
        if _COMMON_BUNDLE_RE.match(fname):
            return os.path.join(directory, fname)
    return None


def selector_to_route(selector: str) -> str:
    return selector.removeprefix("app-")


def _extract_template_at(content: str, template_start: int) -> Optional[str]:
    _, end = _find_template_boundaries(content, template_start)
    block = content[template_start:end]
    results = parse_template_instructions(block)
    if results:
        return results[0]["html"]
    return None


def extract_selector_templates(
    bundle_path: str = "",
    investigation_dir: str = "data/cmgs/investigation/",
) -> List[Dict[str, Any]]:
    if not bundle_path:
        bundle_path = _find_common_bundle(investigation_dir) or ""

    if not bundle_path or not os.path.exists(bundle_path):
        logger.warning(f"Common bundle not found: {bundle_path}")
        return []

    with open(bundle_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    selector_positions: List[tuple] = [
        (m.start(), m.group(1)) for m in _SELECTOR_RE.finditer(content)
    ]
    template_positions: List[int] = [
        m.start() for m in _TEMPLATE_RE.finditer(content)
    ]

    if not selector_positions or not template_positions:
        return []

    results: List[Dict[str, Any]] = []
    for sel_pos, sel_name in selector_positions:
        nearest_template = None
        for tp in template_positions:
            if tp > sel_pos:
                nearest_template = tp
                break

        if nearest_template is None:
            continue

        html = _extract_template_at(content, nearest_template)
        if html:
            results.append(
                {
                    "selector": sel_name,
                    "route_path": selector_to_route(sel_name),
                    "html": html,
                    "html_length": len(html),
                }
            )

    logger.info(
        f"Extracted {len(results)} selector-mapped templates from "
        f"{os.path.basename(bundle_path)}"
    )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestSelectorExtractor -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/cmg/selector_extractor.py tests/python/test_cmg_extraction.py
git commit -m "feat: add selector-based template extraction from 7_common"
```

---

## Task 2: Fix Title-to-Path Matching for CMG 5 and CMG 44

**Files:**
- Modify: `src/python/pipeline/cmg/content_extractor.py:52-57` (`_title_to_path`)
- Test: `tests/python/test_cmg_extraction.py`

The function `_title_to_path` strips all non-alphanumeric chars, so "Cardiac Arrest: Paediatric (\<12 years old)" becomes "cardiac-arrest-paediatric-12-years-old" but the actual route is "cardiac-arrest-paediatric". Fix by adding a secondary fuzzy match fallback.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_extraction.py`:

```python
class TestTitleToPathMatching:
    def test_title_to_path_strips_special_chars(self):
        from pipeline.cmg.content_extractor import _title_to_path

        assert _title_to_path("General Care") == "general-care"
        assert _title_to_path("RSI (Rapid Sequence Intubation)") == "rsi-rapid-sequence-intubation"

    def test_find_route_for_title_fuzzy_match(self, tmp_path):
        from pipeline.cmg.content_extractor import _find_route_for_title

        routes = {
            "cardiac-arrest-paediatric": {"path": "cardiac-arrest-paediatric"},
            "febrile-paediatric": {"path": "febrile-paediatric"},
            "general-care": {"path": "general-care"},
        }

        assert _find_route_for_title("Cardiac Arrest: Paediatric (<12 years old)", routes) == "cardiac-arrest-paediatric"
        assert _find_route_for_title("Febrile Paediatric (<12yo)", routes) == "febrile-paediatric"
        assert _find_route_for_title("General Care", routes) == "general-care"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestTitleToPathMatching -v`
Expected: FAIL — `ImportError: cannot import name '_find_route_for_title'`

- [ ] **Step 3: Implement the fuzzy match in `content_extractor.py`**

Add the new function after `_title_to_path` (around line 57) in `src/python/pipeline/cmg/content_extractor.py`:

```python
def _find_route_for_title(title: str, route_map: Dict[str, Any]) -> Optional[str]:
    direct = _title_to_path(title)
    if direct in route_map:
        return direct

    for route_path in route_map:
        route_base = route_path.split("/:")[0]
        if direct.startswith(route_base):
            return route_path
        if route_base.startswith(direct[:max(5, len(direct) // 2)]):
            return route_path

    title_words = set(re.sub(r"[^a-z0-9\s]", "", title.lower()).split())
    best_match = None
    best_score = 0
    for route_path in route_map:
        route_base = route_path.split("/:")[0]
        route_words = set(route_base.replace("-", " ").split())
        overlap = len(title_words & route_words)
        if overlap > best_score:
            best_score = overlap
            best_match = route_path

    if best_match and best_score >= 2:
        return best_match
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestTitleToPathMatching -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/cmg/content_extractor.py tests/python/test_cmg_extraction.py
git commit -m "fix: add fuzzy route matching for CMGs with parentheses in titles"
```

---

## Task 3: Boilerplate Stripping

**Files:**
- Modify: `src/python/pipeline/cmg/template_parser.py` (add to `html_to_markdown`)
- Test: `tests/python/test_cmg_extraction.py`

Strip UI chrome patterns from both HTML and markdown output. The boilerplate comes from the `25_77083` shared chunk and from inline UI components in 7_common templates.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_extraction.py`:

```python
class TestBoilerplateStripping:
    def test_strip_more_information(self):
        from pipeline.cmg.template_parser import strip_boilerplate

        html = '<span>More information<fa-icon /></span><section><p>Real content</p></section>'
        result = strip_boilerplate(html)
        assert "More information" not in result
        assert "Real content" in result

    def test_strip_my_notes(self):
        from pipeline.cmg.template_parser import strip_boilerplate

        html = '<section><h4>My Notes</h4><div></div></section><p>Clinical text</p>'
        result = strip_boilerplate(html)
        assert "My Notes" not in result
        assert "Clinical text" in result

    def test_strip_tap_to_zoom(self):
        from pipeline.cmg.template_parser import strip_boilerplate

        html = '<div><span>Tap to zoom</span></div><p>Important</p>'
        result = strip_boilerplate(html)
        assert "Tap to zoom" not in result
        assert "Important" in result

    def test_strip_open_print_version(self):
        from pipeline.cmg.template_parser import strip_boilerplate

        html = '<ion-button>Open print version</ion-button><p>Content</p>'
        result = strip_boilerplate(html)
        assert "Open print version" not in result
        assert "Content" in result

    def test_strip_ui_components(self):
        from pipeline.cmg.template_parser import strip_boilerplate

        html = '<content-header /><ion-content><section-menu></section-menu><div><p>Real clinical text</p></div></ion-content>'
        result = strip_boilerplate(html)
        assert "content-header" not in result
        assert "section-menu" not in result
        assert "ion-content" not in result
        assert "Real clinical text" in result

    def test_strip_all_boilerplate_preserves_clinical(self):
        from pipeline.cmg.template_parser import strip_boilerplate

        html = (
            '<content-header />'
            '<ion-content><section-menu></section-menu>'
            '<div><section><h4>Indications</h4><ul><fa-li>Chest pain</fa-li></ul></section></div>'
            '</ion-content>'
            '<span>More information<fa-icon /></span>'
            '<section><h4>My Notes</h4><div></div></section>'
        )
        result = strip_boilerplate(html)
        assert "Indications" in result
        assert "Chest pain" in result
        assert "More information" not in result
        assert "My Notes" not in result

    def test_strip_boilerplate_markdown(self):
        from pipeline.cmg.template_parser import strip_boilerplate_md

        md = "More information\n\n#### My Notes\n\nTap to zoom\n\nOpen print version\n\n## Indications\n- Chest pain"
        result = strip_boilerplate_md(md)
        assert "More information" not in result
        assert "My Notes" not in result
        assert "Tap to zoom" not in result
        assert "Open print version" not in result
        assert "## Indications" in result
        assert "Chest pain" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestBoilerplateStripping -v`
Expected: FAIL — `ImportError: cannot import name 'strip_boilerplate'`

- [ ] **Step 3: Implement boilerplate stripping in `template_parser.py`**

Add these two functions at the end of `src/python/pipeline/cmg/template_parser.py` (after the `html_to_markdown` function, around line 351):

```python
_BOILERPLATE_HTML_PATTERNS = [
    re.compile(r'<span>More information<fa-icon\s*/?></span>'),
    re.compile(r'<section><h4>My Notes</h4><div></div></section>'),
    re.compile(r'<div><div><div><div><img[^>]*></div><div><span>Tap to zoom</span></div></div></div></div>'),
    re.compile(r'<section><div><ion-button>Open print version</ion-button></div></section>'),
    re.compile(r'<content-header\s*/?>'),
    re.compile(r'<section-menu[^>]*>\s*</section-menu>'),
    re.compile(r'<print[^>]*>\s*</print>'),
    re.compile(r'<print\s*/?>'),
    re.compile(r'</?ion-content[^>]*>'),
    re.compile(r'</?ion-header[^>]*>'),
    re.compile(r'<ion-toolbar[^>]*>.*?</ion-toolbar>'),
    re.compile(r'<ion-buttons[^>]*>.*?</ion-buttons>'),
    re.compile(r'<ion-title[^>]*>.*?</ion-title>'),
    re.compile(r'<ion-back-button\s*/?>'),
    re.compile(r'<ion-tab-bar[^>]*>.*?</ion-tab-bar>'),
    re.compile(r'<ion-tab-button[^>]*>.*?</ion-tab-button>'),
]

_BOILERPLATE_MD_LINES = frozenset({
    "More information",
    "#### My Notes",
    "Tap to zoom",
    "Open print version",
})


def strip_boilerplate(html: str) -> str:
    for pattern in _BOILERPLATE_HTML_PATTERNS:
        html = pattern.sub("", html)
    html = re.sub(r"\n{3,}", "\n", html)
    return html.strip()


def strip_boilerplate_md(md: str) -> str:
    lines = md.split("\n")
    cleaned = [l for l in lines if l.strip() not in _BOILERPLATE_MD_LINES]
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
```

Also update the existing `html_to_markdown` function to call `strip_boilerplate` internally. Modify the function to:

```python
def html_to_markdown(html: str) -> str:
    html = strip_boilerplate(html)
    md = html
    md = re.sub(
        r"<h([1-6])>(.*?)</h\1>", lambda m: "#" * int(m.group(1)) + " " + m.group(2), md
    )
    md = re.sub(r"<section[^>]*>", "\n", md)
    md = re.sub(r"</section>", "\n", md)
    md = re.sub(r"<p>", "\n", md)
    md = re.sub(r"</p>", "\n", md)
    md = re.sub(r"<ul>", "\n", md)
    md = re.sub(r"</ul>", "\n", md)
    md = re.sub(r"<fa-li>", "- ", md)
    md = re.sub(r"</fa-li>", "\n", md)
    md = re.sub(r"<li>", "- ", md)
    md = re.sub(r"</li>", "\n", md)
    md = re.sub(r"<strong>(.*?)</strong>", r"**\1**", md)
    md = re.sub(r"<em>(.*?)</em>", r"*\1*", md)
    md = re.sub(r"<br\s*/?>", "\n", md)
    md = re.sub(r"<[^>]+>", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestBoilerplateStripping -v`
Expected: All PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/python/pipeline/cmg/template_parser.py tests/python/test_cmg_extraction.py
git commit -m "feat: add boilerplate stripping for UI chrome in CMG content"
```

---

## Task 4: Integrate Selector Extraction into Content Pipeline

**Files:**
- Modify: `src/python/pipeline/cmg/content_extractor.py`
- Modify: `src/python/pipeline/cmg/orchestrator.py`
- Test: `tests/python/test_cmg_extraction.py`

Wire the new selector extractor into the content extraction flow so that CMGs without route-specific content fall back to 7_common selector-based extraction.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_extraction.py`:

```python
class TestContentExtractorIntegration:
    def test_extract_content_uses_selector_fallback(self, tmp_path):
        from pipeline.cmg.content_extractor import extract_content

        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        output = str(tmp_path / "content.json")
        extract_content(investigation_dir=inv_dir, output_path=output)

        with open(output) as f:
            data = json.load(f)

        general_care_entries = [
            v for v in data.values()
            if v.get("title") == "General Care"
        ]
        assert len(general_care_entries) >= 1
        entry = general_care_entries[0]
        md = entry.get("markdown", "")

        assert "More information" not in md
        assert "My Notes" not in md
        assert "Patient Centred Care" in md

    def test_merge_includes_previously_unmatched_cmgs(self, tmp_path):
        from pipeline.cmg.content_extractor import merge_navigation_and_content
        from pipeline.cmg.extractor import extract_navigation
        from pipeline.cmg.content_extractor import extract_content

        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        nav_path = str(tmp_path / "nav.json")
        content_path = str(tmp_path / "content.json")
        output_path = str(tmp_path / "guidelines.json")

        extract_navigation(investigation_dir=inv_dir, output_path=nav_path)
        extract_content(investigation_dir=inv_dir, output_path=content_path)
        merge_navigation_and_content(
            nav_path=nav_path,
            content_path=content_path,
            output_path=output_path,
        )

        with open(output_path) as f:
            guidelines = json.load(f)

        cmg5 = next(g for g in guidelines if g["cmg_number"] == "5")
        assert cmg5["content_markdown"]
        assert len(cmg5["content_markdown"]) > 100

        cmg44 = next(g for g in guidelines if g["cmg_number"] == "44")
        assert cmg44["content_markdown"]
        assert len(cmg44["content_markdown"]) > 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestContentExtractorIntegration -v`
Expected: FAIL — general care has boilerplate, not clinical content

- [ ] **Step 3: Modify `content_extractor.py` to integrate selector extraction**

The key changes to `src/python/pipeline/cmg/content_extractor.py`:

1. Import the new `extract_selector_templates` and `strip_boilerplate` / `strip_boilerplate_md`
2. Build a selector-to-content map from 7_common
3. In `extract_content`, for each nav entry, first try route-based content, then fall back to selector-based content from 7_common
4. Use `_find_route_for_title` instead of direct `_title_to_path` for route matching
5. Strip boilerplate from all combined content

Replace the `extract_content` function with a version that:

```python
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

    selector_templates = extract_selector_templates(
        investigation_dir=investigation_dir
    )
    selector_map: Dict[str, Dict[str, Any]] = {}
    for st in selector_templates:
        selector_map[st["route_path"]] = st

    content_map: Dict[str, Dict[str, Any]] = {}
    for entry in nav_titles:
        path = _find_route_for_title(entry["title"], route_map)
        route_blocks: List[Dict[str, Any]] = []

        if path and path in route_map:
            route_info = route_map[path]
            route_blocks = _find_content_for_route(
                path, route_info, all_files
            )

        if route_blocks:
            combined_html = "\n".join(b["html"] for b in route_blocks)
        else:
            route_slug = _title_to_path(entry["title"])
            sel_entry = selector_map.get(route_slug)
            if not sel_entry:
                for sel_route, sel_data in selector_map.items():
                    if route_slug.startswith(sel_route) or sel_route.startswith(
                        route_slug[:max(5, len(route_slug) // 2)]
                    ):
                        sel_entry = sel_data
                        break
            if sel_entry:
                combined_html = sel_entry["html"]
            else:
                combined_html = ""

        if not combined_html:
            content_map[entry["spotlightId"]] = {
                "title": entry["title"],
                "section": entry["section"],
                "route_path": entry["route_path"],
                "is_cmg": entry["is_cmg"],
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
            "is_cmg": entry["is_cmg"],
            "html": cleaned_html,
            "markdown": combined_md,
            "template_blocks": len(route_blocks) if route_blocks else 1,
            "source": source,
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(content_map, f, indent=2)

    cmg_count = sum(1 for v in content_map.values() if v["is_cmg"])
    with_content = sum(
        1
        for v in content_map.values()
        if v["is_cmg"] and len(v["markdown"]) > 50
    )
    logger.info(
        f"Extracted content for {len(content_map)} pages "
        f"({cmg_count} CMGs, {with_content} with clinical content)"
    )
    return output_path
```

Also update `_find_content_for_route` to skip the common bundle blocks (25_77083 and 22_30839) that only contain boilerplate:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestContentExtractorIntegration -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py -v`
Expected: All tests PASS (including existing tests)

- [ ] **Step 6: Commit**

```bash
git add src/python/pipeline/cmg/content_extractor.py tests/python/test_cmg_extraction.py
git commit -m "feat: integrate selector-based extraction into content pipeline"
```

---

## Task 5: Content Length Sanity Check

**Files:**
- Modify: `src/python/pipeline/cmg/structurer.py`
- Test: `tests/python/test_cmg_pipeline.py`

Flag CMGs with less than 50 characters of clinical text after structuring. These are extraction failures.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_pipeline.py`:

```python
def test_structure_flags_short_content(tmp_path):
    from pipeline.cmg.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "99",
            "title": "Test Short CMG",
            "section": "Other",
            "spotlightId": "test123",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "",
        },
        {
            "cmg_number": "100",
            "title": "Test Good CMG",
            "section": "Medical",
            "spotlightId": "test456",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "## Indications\n- Chest pain with haemodynamic instability\n- Suspected aortic dissection",
        },
    ]
    import json

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        output_dir=str(output_dir),
    )

    with open(output_dir / "CMG_99_Test_Short_CMG.json") as f:
        short_cmg = json.load(f)
    assert short_cmg.get("extraction_metadata", {}).get("content_flag") == "short"

    with open(output_dir / "CMG_100_Test_Good_CMG.json") as f:
        good_cmg = json.load(f)
    assert good_cmg.get("extraction_metadata", {}).get("content_flag") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_pipeline.py::test_structure_flags_short_content -v`
Expected: FAIL — `content_flag` not set

- [ ] **Step 3: Implement sanity check in `structurer.py`**

In `src/python/pipeline/cmg/structurer.py`, after the `content_markdown` processing (around line 58), add a content length check and set the flag in metadata:

```python
            clinical_chars = len(content_markdown.strip())
            content_flag = "short" if clinical_chars < 50 else None
```

Then update the `ExtractionMetadata` construction to include it:

```python
                extraction_metadata=ExtractionMetadata(
                    timestamp=datetime.utcnow().isoformat(),
                    source_type="cmg",
                    agent_version="2.0",
                    content_flag=content_flag,
                ),
```

Update the `ExtractionMetadata` model in `src/python/pipeline/cmg/models.py` to add the optional field:

```python
class ExtractionMetadata(BaseModel):
    timestamp: str
    source_type: Literal["cmg"] = "cmg"
    agent_version: str = "1.0"
    content_flag: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_pipeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/cmg/structurer.py src/python/pipeline/cmg/models.py tests/python/test_cmg_pipeline.py
git commit -m "feat: add content length sanity check for short CMGs"
```

---

## Task 6: Segment Dose Tables Per Source File

**Files:**
- Modify: `src/python/pipeline/cmg/dose_tables.py`
- Test: `tests/python/test_cmg_extraction.py`

Currently all dose data is lumped into a single large block. Segment by source file to enable per-route attribution.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_extraction.py`:

```python
class TestDoseSegmentation:
    def test_dose_groups_include_source_file(self, tmp_path):
        from pipeline.cmg.dose_tables import extract_dose_tables_segmented

        inv_dir = tmp_path / "inv"
        inv_dir.mkdir()
        chunk = inv_dir / "99_12345.test.js"
        chunk.write_text(
            '.EFF(1,"Adrenaline 0.5mg IM injection")'
            '.EFF(2,"Dose: 0.25 mg")'
        )

        output = str(tmp_path / "dose.json")
        result = extract_dose_tables_segmented(
            investigation_dir=str(inv_dir), output_path=output
        )

        with open(output) as f:
            data = json.load(f)

        assert "per_file" in data
        assert len(data["per_file"]) >= 1
        for file_entry in data["per_file"]:
            assert "source_file" in file_entry
            assert "dose_groups" in file_entry

    def test_integration_segmented_dose_tables(self, tmp_path):
        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        from pipeline.cmg.dose_tables import extract_dose_tables_segmented

        output = str(tmp_path / "dose.json")
        extract_dose_tables_segmented(
            investigation_dir=inv_dir, output_path=output
        )

        with open(output) as f:
            data = json.load(f)

        assert "per_file" in data
        assert len(data["per_file"]) >= 5
        total_groups = sum(
            len(f["dose_groups"]) for f in data["per_file"]
        )
        assert total_groups > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestDoseSegmentation -v`
Expected: FAIL — `ImportError: cannot import name 'extract_dose_tables_segmented'`

- [ ] **Step 3: Implement segmented extraction in `dose_tables.py`**

Add a new function `extract_dose_tables_segmented` to `src/python/pipeline/cmg/dose_tables.py` (after the existing `extract_dose_tables` function):

```python
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
        dose_texts = [t for t in texts if _is_dose_related(t)]
        if not dose_texts:
            continue

        groups = _group_dose_texts(dose_texts)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py::TestDoseSegmentation -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/cmg/dose_tables.py tests/python/test_cmg_extraction.py
git commit -m "feat: add per-file segmented dose table extraction"
```

---

## Task 7: Wire Everything into the Orchestrator and Run Pipeline

**Files:**
- Modify: `src/python/pipeline/cmg/orchestrator.py`
- Test: `tests/python/test_cmg_pipeline.py`

Update the pipeline orchestrator to use the new stages and run the full pipeline to regenerate all structured data.

- [ ] **Step 1: Update orchestrator stages**

In `src/python/pipeline/cmg/orchestrator.py`, add a new `"segment-dose"` stage after `"dose"`:

```python
ALL_STAGES = [
    "navigation",
    "routes",
    "content",
    "dose",
    "segment-dose",
    "merge",
    "flowcharts",
    "structure",
    "chunk",
    "version",
]
```

Add the import and stage handler:

```python
from .dose_tables import extract_dose_tables, extract_dose_tables_segmented
```

Add in the stage execution block, after `"dose"`:

```python
        if "segment-dose" in stages_to_run:
            logger.info("=== Stage 3b: Segmented Dose Tables ===")
            extract_dose_tables_segmented(investigation_dir=inv_dir)
```

- [ ] **Step 2: Run the full pipeline**

Run: `PYTHONPATH=src/python python3 -m pipeline.cmg.orchestrator --stages content,segment-dose,merge,structure --investigation-dir data/cmgs/investigation/`

- [ ] **Step 3: Verify the results**

Run: `PYTHONPATH=src/python python3 -c "
import json, os
with open('data/cmgs/raw/guidelines.json') as f:
    gs = json.load(f)
total = len(gs)
with_content = sum(1 for g in gs if len(g.get('content_markdown','').strip()) > 50)
empty = sum(1 for g in gs if not g.get('content_markdown','').strip())
print(f'Total: {total}, With content: {with_content}, Empty: {empty}')
for g in gs:
    md = g.get('content_markdown','')
    if len(md.strip()) <= 50:
        print(f'  SHORT: CMG {g[\"cmg_number\"]}: {g[\"title\"]} ({len(md)} chars)')
"`

Expected: All 55 CMGs should have substantial clinical content (>50 chars). The 2 previously empty CMGs (5 and 44) should now have content.

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/cmg/orchestrator.py data/cmgs/
git commit -m "feat: complete Phase 2 CMG pipeline — all 55 CMGs with clinical content"
```

---

## Task 8: Validate Extracted Doses and Update TODO

**Files:**
- Modify: `TODO.md`

Spot-check a few known dose values against extracted data, then mark Phase 2 items complete.

- [ ] **Step 1: Spot-check dose values**

Run: `PYTHONPATH=src/python python3 -c "
import json
with open('data/cmgs/raw/dose_tables.json') as f:
    data = json.load(f)

# Check known values: Adrenaline cardiac arrest dose = 1mg IV
for med_name, entries in data['medicine_index'].items():
    if med_name == 'Adrenaline':
        for e in entries[:3]:
            text = e['text']
            if '1:10,000' in text or 'cardiac' in text.lower():
                print(f'Adrenaline cardiac: {text[:200]}')
                break
        break

# Check Fentanyl dose
for med_name, entries in data['medicine_index'].items():
    if 'Fentanyl' in med_name:
        print(f'Fentanyl entries: {len(entries)}')
        for e in entries[:1]:
            print(f'  {e[\"text\"][:200]}')
        break
"`

- [ ] **Step 2: Update TODO.md**

In `TODO.md`, mark the following Phase 2 items as complete:

```
### 2B: Medicine Dose Tables
- [x] Validate extracted doses against known values (spot-check)
- [x] Segment dose groups per route/page instead of single large block

### 2F: Core Extraction Improvements
- [x] Fix 2 unmatched CMGs — title-to-slug drops special chars
- [x] Strip UI boilerplate from extracted content
- [x] Per-route content attribution — assign each template block to its route
- [x] Filter non-clinical template blocks from content output
- [x] Add content length sanity check — flag CMGs with < 50 chars of clinical text
- [x] Handle inline module content in 7_common separately from chunk-file content
```

Leave these items as-is (not done in this phase):
- `[ ] Extract weight-band dose tables from Critical Care Reference Cards chunk`
- `[ ] Use vision LLM for image-based flowcharts`
- `[ ] Validate reconstructed flowcharts against originals`
- `[ ] Plan for periodic re-scraping`

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "docs: update TODO with Phase 2 completion status"
```

---

## Self-Review Checklist

### Spec Coverage
- [x] 2B: Validate extracted doses — Task 8 spot-check
- [x] 2B: Segment dose groups per route — Task 6
- [x] 2D: Structuring complete — already done
- [x] 2E: Version tracking — already done
- [x] 2F: Fix 2 unmatched CMGs — Task 2
- [x] 2F: Strip UI boilerplate — Task 3
- [x] 2F: Per-route content attribution — Task 4
- [x] 2F: Filter non-clinical template blocks — Task 3 + Task 4
- [x] 2F: Content length sanity check — Task 5
- [x] 2F: Handle 7_common inline module content — Task 4
- [x] 2C items explicitly excluded per user request

### Placeholder Scan
- No TBD, TODO, or "implement later" found
- All code blocks contain complete implementations
- All test code is complete

### Type Consistency
- `strip_boilerplate(html: str) -> str` — matches usage in Task 4
- `strip_boilerplate_md(md: str) -> str` — matches usage in Task 4
- `selector_to_route(selector: str) -> str` — returns route path string
- `extract_selector_templates()` returns `List[Dict[str, Any]]` with `selector`, `route_path`, `html` keys
- `_find_route_for_title()` returns `Optional[str]` — used as route key lookup
- `ExtractionMetadata.content_flag` is `Optional[str]` — nullable as expected
- `extract_dose_tables_segmented()` returns `str` (output path) — matches orchestrator usage
