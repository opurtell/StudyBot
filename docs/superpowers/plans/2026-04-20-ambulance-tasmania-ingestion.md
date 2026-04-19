# Ambulance Tasmania CPG Ingestion — Implementation Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract, structure, and ingest the full Ambulance Tasmania Clinical Practice Guideline (CPG) library into the Clinical Recall Assistant. Cover text, medication dosing, flowcharts, qualification tagging, and version tracking. Produce a working AT adapter at `src/python/pipeline/at/` that writes into service-scoped ChromaDB collections (`guidelines_at`, `personal_at`) and produces structured data at `data/services/at/structured/`.

**Architecture:** Ambulance Tasmania's CPG site (`https://cpg.ambulance.tas.gov.au`) is an Angular + Ionic SPA architecturally identical to the ACTAS CMG site. All clinical content is embedded in JavaScript bundles (no API calls). Extraction follows the same JS-bundle-parsing approach proven with ACTAS. Key difference: AT dose information is narrative step-by-step text (not pre-computed lookup tables), and flowcharts likely require vision-LLM extraction.

**Tech Stack:** Python 3.12, FastAPI, ChromaDB, pydantic, pytest, httpx; Playwright (SPA crawling and screenshot capture for flowcharts); vision LLM via `src/python/llm/vision.py`.

**Spec:** `docs/superpowers/specs/2026-04-19-multi-service-support-design.md` (sections 7.3--7.6)
**Phase 0 findings:** `Guides/at-cpg-extraction-findings.md`
**Service addition guide:** `Guides/adding-a-service.md`
**Reference adapter:** `src/python/pipeline/actas/`

---

## File structure

### Created

**Adapter pipeline:**
- `src/python/pipeline/at/__init__.py` — re-exports `run_pipeline`
- `src/python/pipeline/at/orchestrator.py` — stage chaining, defines `run_pipeline()`
- `src/python/pipeline/at/discover.py` — Playwright probe for AT CPG site
- `src/python/pipeline/at/extractor.py` — JS bundle download and parsing
- `src/python/pipeline/at/content_extractor.py` — per-guideline content extraction
- `src/python/pipeline/at/dose_extractor.py` — narrative dose text parsing
- `src/python/pipeline/at/flowcharts.py` — flowchart extraction (data/SVG/image paths)
- `src/python/pipeline/at/structurer.py` — raw data to `GuidelineDocument` JSON conversion
- `src/python/pipeline/at/chunker.py` — service-scoped ChromaDB ingestion into `guidelines_at`
- `src/python/pipeline/at/medications_index.py` — per-medication denormalised index
- `src/python/pipeline/at/version_tracker.py` — source hash tracking for incremental updates
- `src/python/pipeline/at/models.py` — AT-specific pydantic schemas
- `src/python/pipeline/at/qualifications_tagger.py` — maps AT scope tags to qualification IDs

**Vision module (real implementation):**
- `src/python/llm/vision.py` — replace stub with `describe_flowchart(image_bytes, model_id) -> str` (returns Mermaid text)

**Category mapping:**
- `Guides/categories-at.md` — AT category taxonomy mapped to project-wide broad categories

**Tests:**
- `tests/python/pipeline/at/test_adapter_contract.py` — adapter importable + callable
- `tests/python/pipeline/at/test_extractor.py` — JS bundle parsing
- `tests/python/pipeline/at/test_content_extractor.py` — guideline content extraction
- `tests/python/pipeline/at/test_dose_extractor.py` — dose text parsing
- `tests/python/pipeline/at/test_structurer.py` — `GuidelineDocument` output validation
- `tests/python/pipeline/at/test_chunker.py` — ChromaDB ingestion into `guidelines_at`
- `tests/python/pipeline/at/test_qualifications_tagger.py` — qualification tagging
- `tests/python/pipeline/at/test_medications_index.py` — medication index generation
- `tests/python/pipeline/at/test_flowcharts.py` — flowchart conversion tests
- `tests/python/pipeline/at/test_version_tracker.py` — hash/change detection
- `tests/python/llm/test_vision.py` — vision module tests (gated behind `AT_VISION_TESTS=1`)
- `tests/python/fixtures/services/at/` — AT-specific test fixtures

**Data output (generated, committed after validation):**
- `data/services/at/structured/AT_CPG_<code>.json` — per-guideline structured JSON
- `data/services/at/medications/<med_id>.json` — denormalised medication index
- `build/resources/data/services/at/chroma/` — pre-built ChromaDB for packaging

### Modified

**Backend:**
- `src/python/llm/vision.py` — replace stub with real implementation (was placeholder from Plan A)
- `src/renderer/pages/Settings.tsx` — add "Vision model" row (spec 15.13)
- `src/renderer/types/api.ts` — add `vision_model` setting type
- `src/python/settings/router.py` — expose `vision_model` setting

**Packaging:**
- `electron-builder.yml` — add AT bundled Chroma tree
- `scripts/package-backend.sh` — include AT data in staging
- `scripts/package-backend.ps1` — include AT data in staging
- `scripts/build_bundled_chroma.py` — include AT in build loop

### No changes needed

- `src/python/services/registry.py` — AT entry already registered in Plan A Task 1
- `src/python/quiz/retriever.py` — already queries `guidelines_<service_id>` per Plan A
- `src/python/seed.py` — already iterates registry per Plan A Task 14

---

## Implementation order & task index

The plan has **18 tasks** grouped into four phases. Each task leaves `main` in a working, tested state. Tasks within a phase can be done in order; phases must be completed sequentially because later phases depend on earlier invariants.

- **Phase 1 — AT structured data extraction** (Tasks 1--6): discover, parse JS bundles, extract guideline content, extract dose text, handle calculators/checklists, handle flowcharts.
- **Phase 2 — AT qualifications backfill** (Tasks 7--9): map qualification levels, tag content sections, tag medicines.
- **Phase 3 — AT adapter pipeline** (Tasks 10--14): structurer, chunker, medication index, version tracker, orchestrator integration.
- **Phase 4 — Vision model + packaging** (Tasks 15--18): real `vision.py`, Settings UI, bundled Chroma, AT sign-off.

---

## Phase 1 — AT structured data extraction

### Task 1: AT adapter scaffolding + `discover.py`

**Files:**
- Create: `src/python/pipeline/at/__init__.py`
- Create: `src/python/pipeline/at/orchestrator.py`
- Create: `src/python/pipeline/at/discover.py`
- Create: `src/python/pipeline/at/models.py`
- Test: `tests/python/pipeline/at/test_adapter_contract.py`

This task creates the minimum viable adapter that the service registry can call. `discover.py` extends the Phase 0 probe with Playwright-based content enumeration.

- [ ] **Step 1: Write failing test for adapter contract**

```python
# tests/python/pipeline/at/test_adapter_contract.py
import importlib

def test_adapter_importable():
    mod = importlib.import_module("src.python.pipeline.at")
    assert callable(mod.run_pipeline)

def test_run_pipeline_returns_dict():
    from src.python.pipeline.at import run_pipeline
    result = run_pipeline(stages="", dry_run=True)
    assert isinstance(result, dict)
    assert "stages" in result
    assert "dry_run" in result
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
pytest tests/python/pipeline/at/test_adapter_contract.py -v
```

- [ ] **Step 3: Implement `__init__.py`**

```python
# src/python/pipeline/at/__init__.py
"""Ambulance Tasmania CPG Extraction Pipeline"""

from .orchestrator import run_pipeline  # noqa: F401
```

- [ ] **Step 4: Implement `orchestrator.py`** with stage list and `run_pipeline()` returning the required dict shape. Stages for AT: `discover, extract, content, dose, flowcharts, structure, qualifications, chunk, medications, version`. All stages no-op initially.

- [ ] **Step 5: Implement `models.py`** with AT-specific pydantic schemas:

```python
# src/python/pipeline/at/models.py
"""Pydantic schemas for the AT CPG Extraction Pipeline."""
from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field


class ATGuidelineRef(BaseModel):
    """Reference to a single AT guideline discovered in the JS bundles."""
    cpg_code: str                          # e.g. "A0201-1", "D003"
    title: str
    category: str                          # e.g. "Cardiac Arrest", "Medicines"
    route_slug: str                        # e.g. "cardiac-arrest"
    source_bundle: str                     # JS bundle filename
    has_flowchart: bool = False
    has_dose_table: bool = False


class ATMedicineRef(BaseModel):
    """Reference to an AT medicine monograph."""
    cpg_code: str                          # D-code, e.g. "D003"
    name: str                              # e.g. "Adrenaline"
    route_slug: str                        # URL slug


class ATDiscoveryResult(BaseModel):
    """Output of the discover stage."""
    guidelines: List[ATGuidelineRef] = []
    medicines: List[ATMedicineRef] = []
    categories: List[str] = []
    total_bundles_analysed: int = 0
    errors: List[str] = []


class ATContentSection(BaseModel):
    """A single section within an AT guideline."""
    heading: str
    body: str
    qualifications_required: List[str] = []


class ATFlowchart(BaseModel):
    """Flowchart associated with an AT guideline."""
    cpg_code: str
    title: str
    source_format: Literal["data", "svg", "image", "pdf"]
    mermaid: Optional[str] = None
    asset_ref: Optional[str] = None
    review_required: bool = False
```

- [ ] **Step 6: Implement `discover.py`** using Playwright to:
  1. Navigate to `https://cpg.ambulance.tas.gov.au/tabs/guidelines`
  2. Dismiss disclaimer modal (click "OK")
  3. Remove level selector modal (force-remove `ion-modal` from DOM)
  4. Extract the navigation tree from the rendered category list
  5. For each category, enumerate guideline links and capture CPG codes
  6. Navigate to `/tabs/medicines` and capture all medicine names + D-codes
  7. Save `ATDiscoveryResult` JSON to `data/services/at/raw/discovery.json`

- [ ] **Step 7: Run tests, expect pass**

```bash
pytest tests/python/pipeline/at/test_adapter_contract.py -v
```

- [ ] **Step 8: Commit**

```bash
git add src/python/pipeline/at/ tests/python/pipeline/at/
git commit -m "feat(at): adapter scaffolding with discover stage"
```

---

### Task 2: JS bundle download and parsing

**Files:**
- Create: `src/python/pipeline/at/extractor.py`
- Test: `tests/python/pipeline/at/test_extractor.py`

Extract the ~9.5 MB main JS bundle and ~882 KB common bundle. Parse for CPG number registry, medicine data, route definitions, and qualification-level markers.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_extractor.py
import json
from src.python.pipeline.at.extractor import (
    parse_cpg_registry,
    parse_medicine_registry,
    parse_route_definitions,
)

def test_parse_cpg_registry_finds_known_codes():
    # Use a synthetic JS fragment containing AT CPG codes
    js_fragment = '"A0201","A0201-1","A0201-2","D003","D010","M001","P0201"'
    codes = parse_cpg_registry(js_fragment)
    assert "A0201" in codes
    assert "A0201-1" in codes
    assert "D003" in codes
    assert "M001" in codes
    assert "P0201" in codes

def test_parse_medicine_registry_extracts_names_and_dcodes():
    js_fragment = '{"D003":"Adrenaline","D010":"Fentanyl","D024":"Morphine"}'
    medicines = parse_medicine_registry(js_fragment)
    assert len(medicines) == 3
    by_code = {m["code"]: m["name"] for m in medicines}
    assert by_code["D003"] == "Adrenaline"
    assert by_code["D010"] == "Fentanyl"

def test_parse_route_definitions_finds_guidelines_routes():
    js_fragment = '{path:"tabs/guidelines/adult-patient-guidelines/cardiac-arrest"}'
    routes = parse_route_definitions(js_fragment)
    assert any("cardiac-arrest" in r for r in routes)
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `extractor.py`**

Download functions:
- `download_main_bundle(output_dir) -> str` — fetches `main.*.js` via Playwright or requests
- `download_common_bundle(output_dir) -> str` — fetches `common.*.js`
- `download_lazy_chunks(output_dir) -> list[str]` — fetches per-guideline lazy chunks

Parsing functions:
- `parse_cpg_registry(js_content) -> list[str]` — regex for CPG code patterns (A0xxx, D0xx, M0xx, P0xxx, E0xx, A0xxx-N)
- `parse_medicine_registry(js_content) -> list[dict]` — extracts medicine name + D-code pairs
- `parse_route_definitions(js_content) -> list[str]` — extracts Angular route paths
- `parse_qualification_levels(js_content) -> list[str]` — extracts VAO, PARAMEDIC, ICP, PACER, CP_ECP from the level selector modal

Key patterns from Phase 0 findings:
- CPG codes follow `A\d{4}(-\d+)?`, `D\d{3}`, `M\d{3}`, `P\d{4}`, `E\d{3}`
- 168 unique CPG numbers in the main bundle
- 38 medicines with D-codes (D002--D047)
- 95 route definitions in the common bundle
- Qualification level names are in the level selector modal logic

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/extractor.py tests/python/pipeline/at/test_extractor.py
git commit -m "feat(at): JS bundle download and CPG/medicine/route parsing"
```

---

### Task 3: Per-guideline content extraction

**Files:**
- Create: `src/python/pipeline/at/content_extractor.py`
- Test: `tests/python/pipeline/at/test_content_extractor.py`

Extract clinical text, section tree, categories, and metadata from each guideline's lazy-loaded JS chunk. Output is a per-guideline dict containing structured content.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_content_extractor.py
from src.python.pipeline.at.content_extractor import (
    extract_guideline_content,
    parse_html_sections,
)

def test_parse_html_sections_extracts_headings_and_body():
    html = """
    <h2>Pharmacology</h2><p>Adrenaline acts on alpha and beta receptors.</p>
    <h2>Indications</h2><p>Cardiac arrest. Anaphylaxis.</p>
    """
    sections = parse_html_sections(html)
    assert len(sections) == 2
    assert sections[0]["heading"] == "Pharmacology"
    assert "alpha" in sections[0]["body"]

def test_extract_guideline_content_produces_required_fields():
    # Use a synthetic JS chunk containing Ionic template content
    chunk = 'class SomeComponent{template:`<ion-content><h2>Cardiac Arrest</h2><p>Content here.</p></ion-content>`}'
    result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Medical Cardiac Arrest")
    assert result["cpg_code"] == "A0201-1"
    assert len(result["sections"]) >= 1
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `content_extractor.py`**

Key functions:
- `extract_guideline_content(js_content, cpg_code, title) -> dict` — parses a single lazy chunk for its guideline content
- `parse_html_sections(html) -> list[dict]` — extracts heading/body pairs from Ionic `<ion-content>` HTML
- `extract_all_guidelines(discovery_path, output_dir) -> list[dict]` — iterates discovery results, downloads each lazy chunk, extracts content

The AT site renders content as HTML within Ionic components (confirmed in Phase 0 Section 5.1). Sections observed on medicine pages include: Common Trade Names, Presentation, Pharmacology, Metabolism, Primary Emergency Indication, Contraindications, Precautions, Route of Administration, Interactions, Side Effects, Pregnancy Category, Breastfeeding Category, Special Notes, Dose Recommendations.

For adult guidelines, expected sections include: Indications, Contraindications, Precautions, Clinical Management, Cross-references to medicine D-codes.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/content_extractor.py tests/python/pipeline/at/test_content_extractor.py
git commit -m "feat(at): per-guideline content extraction from JS bundles"
```

---

### Task 4: Narrative dose text extraction

**Files:**
- Create: `src/python/pipeline/at/dose_extractor.py`
- Test: `tests/python/pipeline/at/test_dose_extractor.py`

AT dose information is narrative step-by-step text, not pre-computed lookup tables like ACTAS. This module extracts dose information from the structured text and converts it into `MedicationDose` schema entries.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_dose_extractor.py
from src.python.pipeline.at.dose_extractor import (
    extract_dose_sections,
    parse_dose_text,
    normalise_dose_entry,
)

def test_extract_dose_sections_finds_dose_recommendations():
    content = {
        "sections": [
            {"heading": "Dose Recommendations", "body": "Adult bolus: 1 mg IV..."},
            {"heading": "Pharmacology", "body": "No dose info here."},
        ]
    }
    dose_sections = extract_dose_sections(content)
    assert len(dose_sections) == 1
    assert "Adult bolus" in dose_sections[0]["body"]

def test_parse_dose_text_extracts_structured_entries():
    text = "Adult bolus dosing: 1 mg (1:10,000) IV every 3-5 minutes. Max total 10 mg."
    entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
    assert len(entries) >= 1
    assert entries[0]["medication"] == "Adrenaline"
    assert "1 mg" in entries[0]["dose"]

def test_normalise_dose_entry_produces_valid_schema():
    raw = {
        "medication": "Adrenaline",
        "indication": "Cardiac Arrest",
        "dose": "1 mg IV",
        "route": "IV",
    }
    result = normalise_dose_entry(raw)
    assert result["medication"] == "Adrenaline"
    assert result["route"] == "IV"
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `dose_extractor.py`**

Key functions:
- `extract_dose_sections(content) -> list[dict]` — finds sections with dose-related headings
- `parse_dose_text(text, medicine, indication) -> list[dict]` — regex-based extraction of dose entries from narrative text
- `normalise_dose_entry(raw) -> dict` — converts raw extraction into a schema-valid dict

AT dose format (from Phase 0 Section 5.2) is step-by-step instructions:
- "Adult bolus dosing (dilution instructions)"
- "Adult infusion (hard max 100 microg/min, dilution recipe)"
- "Paediatric infusion (hard max 1 microg/kg/min, double-dilution steps)"
- "Paediatric bolus dosing (dilution steps)"

Regex patterns needed:
- Dose quantities: `\d+\.?\d*\s*(mg|mcg|microg|ml|IU|mmol|g|mg/kg|mcg/kg|ml/kg)`
- Routes: `IV`, `IO`, `IM`, `SC`, `inhaled`, `intranasal`, `topical`, `oral`, `rectal`
- Dilution instructions with ratios (e.g., "1:10,000", "1:100,000")
- Max dose markers: "max", "maximum", "hard max"

If regex extraction is insufficient for complex dose narratives, fall back to the LLM normalisation approach from spec 7.4: structured-prompt LLM call using the user's configured cleaning model, with schema validation on output.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/dose_extractor.py tests/python/pipeline/at/test_dose_extractor.py
git commit -m "feat(at): narrative dose text extraction from AT CPGs"
```

---

### Task 5: Calculator and checklist extraction

**Files:**
- Modify: `src/python/pipeline/at/extractor.py` (add calculator route parsing)
- Test: `tests/python/pipeline/at/test_extractor.py` (extend)

AT has four calculators and several checklists (Phase 0 Section 8). Extract their content as structured text.

- [ ] **Step 1: Write failing tests for calculator/checklist enumeration**

```python
def test_parse_calculator_routes():
    js_fragment = '{path:"tabs/calculators/medicine-calculator"},{path:"tabs/calculators/news-two"}'
    routes = parse_calculator_routes(js_fragment)
    assert "medicine-calculator" in routes
    assert "news-two" in routes

def test_parse_checklist_routes():
    js_fragment = '{path:"tabs/checklists/clinical-handover"},{path:"tabs/checklists/stemi-referral-script"}'
    routes = parse_checklist_routes(js_fragment)
    assert "clinical-handover" in routes
    assert "stemi-referral-script" in routes
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement** calculator and checklist route parsing in `extractor.py`. Add functions:
  - `parse_calculator_routes(js_content) -> list[str]`
  - `parse_checklist_routes(js_content) -> list[str]`
  - `extract_calculator_content(js_content, route_slug) -> dict`
  - `extract_checklist_content(js_content, route_slug) -> dict`

Calculator handling strategy:
- **Medicine Calculator**: Likely JS logic with weight/indication lookups. Extract the computation logic as structured text. May contain weight-band dose tables internally.
- **NEWS2 / CEWT**: Scoring tools. Extract the scoring criteria as structured text.
- **Palliative Care Medication Calculator**: Extract medication/dose matrix as text.

Checklist handling: Extract checklist items as structured text. Checklists (clinical-handover, stemi-referral-script, reperfusion-checklist, cardiac-arrest-and-rosc-checklist, cold-intubation-checklist, sedation-checklist) are captured as `GuidelineDocument` entries with `source_type: "checklist"` in metadata.

Reference tools (wallace-rules-of-nine, lund-and-browder) are also extracted as structured text.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/extractor.py tests/python/pipeline/at/test_extractor.py
git commit -m "feat(at): calculator and checklist route parsing"
```

---

### Task 6: Flowchart extraction

**Files:**
- Create: `src/python/pipeline/at/flowcharts.py`
- Test: `tests/python/pipeline/at/test_flowcharts.py`

The AT CPG site has flowcharts as first-class content (confirmed in Phase 0 Section 5.3). The `common` bundle contains `has_flowchart_refs: true` and there is a dedicated `flowchart` route.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_flowcharts.py
from src.python.pipeline.at.flowcharts import (
    classify_flowchart_format,
    extract_data_driven_flowchart,
    convert_svg_to_mermaid,
)

def test_classify_data_driven_format():
    js_content = '{"nodes":[{"id":"start","label":"Assessment"}],"edges":[{"from":"start","to":"decision"}]}'
    fmt = classify_flowchart_format(js_content)
    assert fmt == "data"

def test_classify_svg_format():
    content = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0"/><text>Start</text></svg>'
    fmt = classify_flowchart_format(content)
    assert fmt == "svg"

def test_classify_image_format():
    content = b'\x89PNG\r\n\x1a\n'
    fmt = classify_flowchart_format(content)
    assert fmt == "image"

def test_extract_data_driven_flowchart_to_mermaid():
    js_content = '{"nodes":[{"id":"A","label":"Start"},{"id":"B","label":"Decision"}],"edges":[{"from":"A","to":"B"}]}'
    mermaid = extract_data_driven_flowchart(js_content)
    assert "graph TD" in mermaid
    assert "A" in mermaid
    assert "B" in mermaid

def test_convert_svg_to_mermaid():
    svg = '<svg><text x="10" y="20">Start</text><text x="10" y="60">Decision</text></svg>'
    mermaid = convert_svg_to_mermaid(svg)
    assert "graph TD" in mermaid
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `flowcharts.py`**

Flowchart handling follows the four-way decision tree from spec 7.5:

1. **Data-driven nodes/edges JSON**: Deterministic transform to Mermaid `graph TD`. No LLM. Parse JSON nodes/edges structure, map to Mermaid syntax. Fully audit-able.

2. **Rendered HTML/SVG with semantic DOM**: Parse SVG `<text>` elements by Y-coordinate to determine flow order. Convert to node/edge graph, then to Mermaid. Same deterministic transform.

3. **Raster image (PNG/JPG/bitmap SVG)**: Vision-LLM path. Uses `src/python/llm/vision.py` (implemented in Phase 4 Task 15). Results cached by `sha256(image_bytes)` to avoid re-billing. Output marked `review_required: true` until user approves.

4. **PDF**: Rasterise via `pdf2image` or `pypdf` + Pillow, then route through path 3.

Each flowchart is stored with:
- Mermaid text
- Reference to original asset (URL or bundled file path)
- `source_format` field ("data", "svg", "image", "pdf")
- `review_required: bool` — true for vision-LLM outputs

Key functions:
- `classify_flowchart_format(content) -> str` — determines which path to use
- `extract_data_driven_flowchart(js_content) -> str` — path 1
- `convert_svg_to_mermaid(svg_content) -> str` — path 2
- `process_all_flowcharts(discovery_path, output_dir) -> list[dict]` — iterates guidelines with flowcharts
- `capture_flowchart_screenshot(page, url) -> bytes` — Playwright screenshot for path 3/4

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/flowcharts.py tests/python/pipeline/at/test_flowcharts.py
git commit -m "feat(at): flowchart extraction with data/SVG/image paths"
```

---

## Phase 2 — AT qualifications backfill

### Task 7: Map AT qualification levels to guideline sections

**Files:**
- Create: `src/python/pipeline/at/qualifications_tagger.py`
- Test: `tests/python/pipeline/at/test_qualifications_tagger.py`

Map AT's five qualification levels (VAO, PARAMEDIC, ICP, PACER, CP_ECP) to guideline content. The scope-of-practice information is embedded in the app's qualification level selector (Phase 0 Section 7).

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_qualifications_tagger.py
from src.python.pipeline.at.qualifications_tagger import (
    tag_section_qualifications,
    tag_guideline_qualifications,
)

def test_universal_section_gets_empty_required():
    section = {"heading": "Indications", "body": "Chest pain."}
    result = tag_section_qualifications(section)
    assert result["qualifications_required"] == []

def test_icp_tagged_section():
    section = {"heading": "ICP Management", "body": "Cold intubation protocol."}
    result = tag_section_qualifications(section)
    assert "ICP" in result["qualifications_required"]

def test_vao_scope_section():
    section = {"heading": "Basic Life Support", "body": "BPR, AED, OPA."}
    result = tag_section_qualifications(section)
    # VAO content is available to all AT levels
    assert result["qualifications_required"] == []

def test_guideline_with_mixed_sections():
    guideline = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "sections": [
            {"heading": "Initial Assessment", "body": "DRABC."},
            {"heading": "ICP Interventions", "body": "Cold intubation, extended meds."},
        ]
    }
    result = tag_guideline_qualifications(guideline)
    assert result["sections"][0]["qualifications_required"] == []
    assert "ICP" in result["sections"][1]["qualifications_required"]
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `qualifications_tagger.py`**

AT qualification tagging strategy:
- **Default** (no specific qualification markers): `qualifications_required: []` (universally available)
- **ICP-tagged sections**: Look for ICP markers in section headings or body text ("ICP", "Intensive Care", "cold intubation", ICP-exclusive medicine names from AT formulary)
- **PACER-tagged sections**: Look for PACER-specific markers
- **CP/ECP-tagged sections**: Look for community paramedic markers
- **VAO-only content**: Generally not restricted (VAO content is baseline); VAO-restricted content is unusual and would be explicitly marked

The level selector modal may filter visible content at each qualification level. During extraction, content should be probed at each level to determine if filtering occurs (Phase 0 Section 7 recommendation). If filtering does occur, the qualification tags reflect what is visible at each level.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/qualifications_tagger.py tests/python/pipeline/at/test_qualifications_tagger.py
git commit -m "feat(at): qualification level tagging for guideline sections"
```

---

### Task 8: Per-medicine qualification tags

**Files:**
- Modify: `src/python/pipeline/at/qualifications_tagger.py`
- Test: `tests/python/pipeline/at/test_qualifications_tagger.py` (extend)

Tag each medicine monograph with `qualifications_required` based on its position in the scope-of-practice hierarchy.

- [ ] **Step 1: Write failing tests**

```python
def test_paramedic_medicine_gets_empty_required():
    """Medicines available to all PARAMEDIC-level staff."""
    med = {"name": "Adrenaline", "cpg_code": "D003"}
    result = tag_medicine_qualifications(med)
    assert result["qualifications_required"] == []

def test_icp_medicine_gets_icp_required():
    """Medicines restricted to ICP endorsement."""
    # AT-specific ICP medicines identified during extraction
    med = {"name": "Amiodarone", "cpg_code": "D004"}
    result = tag_medicine_qualifications(med)
    assert "ICP" in result["qualifications_required"]
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

Add `tag_medicine_qualifications(med) -> dict` function. AT medicine qualification mapping:
- Medicines in the general formulary (adrenaline, morphine, fentanyl, etc.): `qualifications_required: []`
- ICP-restricted medicines (if any identified during extraction): `qualifications_required: ["ICP"]`
- PACER-specific medication protocols: `qualifications_required: ["PACER"]`
- CP/ECP medication authorities: `qualifications_required: ["CP_ECP"]`

The definitive mapping comes from the AT CPG site's content when viewed at each qualification level. During Phase 1 extraction, probe at each level and record which medicines/guidelines appear/disappear.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/qualifications_tagger.py tests/python/pipeline/at/test_qualifications_tagger.py
git commit -m "feat(at): per-medicine qualification tagging"
```

---

### Task 9: Author `Guides/categories-at.md`

**Files:**
- Create: `Guides/categories-at.md`

Map AT's clinical category taxonomy to the project's broad study categories. Reviewed with the user before ingestion begins.

- [ ] **Step 1: Draft the mapping** based on Phase 0 findings (Section 6.3 confirmed categories)

AT category to project category mapping:

| AT Category | CPG Range | Project Broad Category |
|-------------|-----------|----------------------|
| Assessment | A0101--A0112 | Clinical Skills |
| Mental Health | A0106 | Clinical Guidelines |
| Cardiac Arrest | A0201--A0203 | Clinical Guidelines |
| Airway Management | A0300--A0307 | Clinical Skills |
| Cardiac | A0401--A0411 | Clinical Guidelines |
| Pain Relief | A0501 | Medication Guidelines |
| Respiratory | A0601--A0604 | Clinical Guidelines |
| Medical | A0701--A0712 | Clinical Guidelines |
| Trauma | A0801--A0809 | Clinical Guidelines |
| Environment | A0901--A0902 | Clinical Guidelines |
| Obstetrics | M001--M010 | Clinical Guidelines |
| Medicines | D002--D047 | Medication Guidelines, Pharmacology |
| Paediatric | P0201--P0710 | Clinical Guidelines |
| Reference Notes | E002--E009 | Operational Guidelines |

Medicines also map to Pharmacology. Dose-related content maps to both Medication Guidelines and Pharmacology.

- [ ] **Step 2: Submit for user review before committing**

- [ ] **Step 3: Commit**

```bash
git add Guides/categories-at.md
git commit -m "docs: add AT category mapping to broad study categories"
```

---

## Phase 3 — AT adapter pipeline

### Task 10: Structurer — raw data to `GuidelineDocument` JSON

**Files:**
- Create: `src/python/pipeline/at/structurer.py`
- Test: `tests/python/pipeline/at/test_structurer.py`

Convert extracted raw content into `GuidelineDocument` JSON files that conform to the shared schema in `src/python/services/schema.py`.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_structurer.py
import json
from src.python.services.schema import GuidelineDocument
from src.python.pipeline.at.structurer import structure_guideline

def test_structure_guideline_produces_valid_document():
    raw = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "category": "Cardiac Arrest",
        "sections": [
            {"heading": "Initial Assessment", "body": "Confirm cardiac arrest."},
            {"heading": "Defibrillation", "body": "Analyse rhythm."},
        ],
        "medicines": [
            {"medication": "Adrenaline", "indication": "Cardiac Arrest", "dose": "1 mg IV", "route": "IV"},
        ],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/cardiac-arrest/medical-cardiac-arrest",
        "source_hash": "abc123",
    }
    doc_dict = structure_guideline(raw)
    # Validate against the shared schema
    doc = GuidelineDocument(**doc_dict)
    assert doc.service == "at"
    assert doc.guideline_id == "AT_CPG_A0201-1"
    assert doc.title == "Medical Cardiac Arrest"
    assert len(doc.content_sections) == 2
    assert len(doc.medications) == 1

def test_structure_medicine_monograph_produces_valid_document():
    raw = {
        "cpg_code": "D003",
        "title": "Adrenaline",
        "category": "Medicines",
        "sections": [
            {"heading": "Pharmacology", "body": "Alpha and beta receptor agonist."},
            {"heading": "Dose Recommendations", "body": "Adult bolus: 1 mg IV every 3-5 min."},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/medicines/page/adrenaline",
        "source_hash": "def456",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)
    assert doc.guideline_id == "AT_CPG_D003"
    assert doc.categories == ["Medication Guidelines", "Pharmacology"]
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `structurer.py`**

Key functions:
- `structure_guideline(raw) -> dict` — converts a raw extraction dict into a `GuidelineDocument`-compatible dict
- `structure_all_guidelines(raw_dir, output_dir) -> int` — processes all raw extractions

Mapping logic:
- `guideline_id`: `"AT_CPG_" + cpg_code` (e.g., `"AT_CPG_A0201-1"`, `"AT_CPG_D003"`)
- `service`: always `"at"`
- `categories`: mapped via `Guides/categories-at.md` mapping
- `qualifications_required`: populated by `qualifications_tagger` outputs
- `content_sections`: list of `ContentSection` from parsed HTML sections
- `medications`: list of `MedicationDose` from dose_extractor outputs
- `flowcharts`: list of `Flowchart` from flowcharts module
- `source_hash`: SHA-256 of the raw extraction content
- `last_modified`: extracted from version history if available (Phase 0 Section 9)

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/structurer.py tests/python/pipeline/at/test_structurer.py
git commit -m "feat(at): structurer converting raw extraction to GuidelineDocument JSON"
```

---

### Task 11: Chunker — service-scoped ChromaDB ingestion

**Files:**
- Create: `src/python/pipeline/at/chunker.py`
- Test: `tests/python/pipeline/at/test_chunker.py`

Chunk `GuidelineDocument` content and ingest into the `guidelines_at` ChromaDB collection with correct metadata.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_chunker.py
import chromadb
from src.python.pipeline.at.chunker import chunk_and_ingest

def test_chunk_and_ingest_writes_to_guidelines_at(tmp_path):
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    # Write a minimal AT_CPG fixture JSON
    fixture = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Medical Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [
            {"heading": "Initial Assessment", "body": "Confirm cardiac arrest. Begin CPR.", "qualifications_required": []},
        ],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_hash": "abc",
        "extra": {},
    }
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(fixture))

    db_path = str(tmp_path / "chroma")
    chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection("guidelines_at")
    assert collection.count() > 0

def test_chunks_carry_at_metadata(tmp_path):
    # ... (ingest fixture, then verify metadata)
    pass

def test_qualifications_required_in_chunk_metadata(tmp_path):
    # Ingest a guideline with ICP-required section
    # Verify chunk metadata has qualifications_required: ["ICP"]
    pass
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `chunker.py`**

Follows the ACTAS chunker pattern but writes to `guidelines_at` instead of `cmg_guidelines`. Key differences from ACTAS:
- Collection name: `"guidelines_at"`
- All chunks carry `service: "at"` in metadata
- No `visibility` field (AT uses `qualifications_required` list instead of AP/ICP visibility split)
- `guideline_id` replaces `cmg_number`

Chunk metadata fields:
```python
metadata = {
    "source_type": "cmg",
    "source_file": os.path.basename(file_path),
    "guideline_id": guideline_id,
    "section": category,
    "qualifications_required": [...],  # list of qualification IDs
    "chunk_type": "general" | "dosage" | "safety" | "protocol" | "reference" | "assessment",
    "last_modified": timestamp,
}
```

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/chunker.py tests/python/pipeline/at/test_chunker.py
git commit -m "feat(at): chunker with service-scoped ChromaDB ingestion"
```

---

### Task 12: Medication denormalised index

**Files:**
- Create: `src/python/pipeline/at/medications_index.py`
- Test: `tests/python/pipeline/at/test_medications_index.py`

Build a per-medicine JSON index aggregating all doses across all AT guidelines, so the medication router can read from `data/services/at/medications/`.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_medications_index.py
from src.python.pipeline.at.medications_index import build_medications_index

def test_build_index_produces_per_medicine_files(tmp_path):
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    # Write two guideline JSONs that reference Adrenaline
    # ...
    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))
    assert count >= 1
    assert (output_dir / "adrenaline.json").exists()
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `medications_index.py`**

Iterates all `AT_CPG_D*.json` medicine monograph files plus any guideline JSONs with non-empty `medications` lists. Aggregates into one file per medicine at `data/services/at/medications/<slug>.json`. Each file contains a list of `MedicationDose`-compatible entries plus `service`, `guideline_id`, and `source_file`.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/medications_index.py tests/python/pipeline/at/test_medications_index.py
git commit -m "feat(at): per-medication denormalised index builder"
```

---

### Task 13: Version tracker

**Files:**
- Create: `src/python/pipeline/at/version_tracker.py`
- Test: `tests/python/pipeline/at/test_version_tracker.py`

Track source content hashes for incremental re-scraping. Prefer AT's own version signal (content-updated timestamp from version history, Phase 0 Section 9) over content hashing.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/pipeline/at/test_version_tracker.py
from src.python.pipeline.at.version_tracker import (
    compute_source_hash,
    detect_changes,
    update_version_tracking,
)

def test_compute_source_hash_deterministic():
    content = {"cpg_code": "A0201-1", "body": "Cardiac arrest management."}
    h1 = compute_source_hash(content)
    h2 = compute_source_hash(content)
    assert h1 == h2

def test_detect_changes_identifies_new_and_modified():
    previous = {"A0201-1": {"hash": "abc"}, "A0300": {"hash": "def"}}
    current = {"A0201-1": {"hash": "abc"}, "A0300": {"hash": "xyz"}, "A0401": {"hash": "new"}}
    new, modified, unchanged = detect_changes(previous, current)
    assert new == ["A0401"]
    assert modified == ["A0300"]
    assert unchanged == ["A0201-1"]
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `version_tracker.py`**

- `compute_source_hash(content) -> str` — SHA-256 of canonical JSON
- `detect_changes(previous, current) -> tuple[list, list, list]` — returns new, modified, unchanged CPG codes
- `update_version_tracking(structured_dir, tracker_path) -> dict` — reads current hashes, compares to previous, returns summary
- Version history timestamps from the AT site (Phase 0 Section 9) are stored alongside hashes as an additional change signal

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/version_tracker.py tests/python/pipeline/at/test_version_tracker.py
git commit -m "feat(at): version tracking with hash-based change detection"
```

---

### Task 14: Orchestrator integration — wire all stages

**Files:**
- Modify: `src/python/pipeline/at/orchestrator.py`
- Modify: `src/python/pipeline/at/__init__.py`
- Test: `tests/python/pipeline/at/test_adapter_contract.py` (extend)

Wire all implemented stages into the orchestrator. `run_pipeline()` now calls real implementations.

- [ ] **Step 1: Extend adapter contract test**

```python
def test_run_pipeline_all_stages_dry_run():
    from src.python.pipeline.at import run_pipeline
    result = run_pipeline(stages="all", dry_run=True)
    assert result["stages"] == [
        "discover", "extract", "content", "dose",
        "flowcharts", "structure", "qualifications",
        "chunk", "medications", "version",
    ]
    assert result["dry_run"] is True
    # No ChromaDB writes in dry_run mode
```

- [ ] **Step 2: Run, expect fail (chunk stage not yet wired)**

- [ ] **Step 3: Update orchestrator to chain all stages**

```python
# src/python/pipeline/at/orchestrator.py
ALL_STAGES = [
    "discover",       # Playwright site probe
    "extract",        # JS bundle download + parse
    "content",        # Per-guideline content extraction
    "dose",           # Narrative dose text extraction
    "flowcharts",     # Flowchart handling
    "structure",      # Raw -> GuidelineDocument JSON
    "qualifications", # Qualification tagging
    "chunk",          # ChromaDB ingestion
    "medications",    # Medication index
    "version",        # Version tracking
]
```

Stage chaining:
1. `discover` — runs `discover.py`, outputs `discovery.json`
2. `extract` — runs `extractor.py`, downloads + parses bundles
3. `content` — runs `content_extractor.py`, extracts per-guideline content
4. `dose` — runs `dose_extractor.py`, extracts dose information
5. `flowcharts` — runs `flowcharts.py`, processes flowcharts
6. `structure` — runs `structurer.py`, produces `GuidelineDocument` JSON files
7. `qualifications` — runs `qualifications_tagger.py`, adds qualification tags to structured JSON
8. `chunk` — runs `chunker.py`, ingests into `guidelines_at` (skipped if `dry_run=True`)
9. `medications` — runs `medications_index.py`, builds medication index
10. `version` — runs `version_tracker.py`, updates hash tracking

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/at/orchestrator.py src/python/pipeline/at/__init__.py tests/python/pipeline/at/test_adapter_contract.py
git commit -m "feat(at): orchestrator wiring all extraction stages"
```

---

## Phase 4 — Vision model + packaging

### Task 15: Implement `llm/vision.py` real module

**Files:**
- Modify: `src/python/llm/vision.py` (replace stub from Plan A)
- Test: `tests/python/llm/test_vision.py` (gated behind `AT_VISION_TESTS=1`)

Replace the placeholder stub with a working implementation that uses the provider abstraction to call a vision-capable LLM for flowchart description.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/llm/test_vision.py
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("AT_VISION_TESTS"),
    reason="Vision tests require AT_VISION_TESTS=1"
)

def test_describe_flowchart_returns_mermaid():
    from src.python.llm.vision import describe_flowchart
    # Use a small test image (1x1 PNG or synthetic flowchart screenshot)
    result = describe_flowchart(b"test_image_bytes", model_id="test-model")
    assert "graph TD" in result or "graph LR" in result

def test_describe_flowchart_caches_by_hash():
    from src.python.llm.vision import describe_flowchart, _cache
    _cache.clear()
    r1 = describe_flowchart(b"test_image_bytes", model_id="test-model")
    r2 = describe_flowchart(b"test_image_bytes", model_id="test-model")
    # Second call should return cached result without re-calling LLM
    assert r1 == r2

def test_vision_not_supported_error_for_unsupported_provider():
    from src.python.llm.vision import describe_flowchart, VisionNotSupportedError
    # If a provider doesn't support vision, raise VisionNotSupportedError
    with pytest.raises(VisionNotSupportedError):
        describe_flowchart(b"test", model_id="glm-4.7-flash")
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `vision.py`**

```python
# src/python/llm/vision.py
"""Vision LLM module for flowchart extraction."""

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# SHA-256 keyed cache to avoid re-billing on re-runs
_cache: dict[str, str] = {}


class VisionNotSupportedError(Exception):
    """Raised when the selected model/provider does not support vision."""
    pass


def describe_flowchart(
    image_bytes: bytes,
    model_id: str,
    prompt: Optional[str] = None,
) -> str:
    """
    Send a flowchart image to a vision-capable LLM and receive Mermaid text.

    Args:
        image_bytes: Raw image data (PNG/JPG).
        model_id: The model to use (must be vision-capable).
        prompt: Optional custom prompt. Defaults to a flowchart extraction prompt.

    Returns:
        Mermaid.js graph text describing the flowchart.

    Raises:
        VisionNotSupportedError: If the model/provider doesn't support vision.
    """
    cache_key = hashlib.sha256(image_bytes).hexdigest() + f":{model_id}"
    if cache_key in _cache:
        logger.info("Vision cache hit for %s", cache_key[:16])
        return _cache[cache_key]

    if prompt is None:
        prompt = (
            "You are a clinical flowchart extraction tool. Analyse this flowchart image "
            "and produce a Mermaid.js graph that faithfully represents the clinical decision "
            "logic. Use 'graph TD' (top-down) layout. Label each node with the exact clinical "
            "text visible in the image. Preserve all decision branches, outcomes, and "
            "loops. Output ONLY the Mermaid code block, no explanation."
        )

    # Determine provider from model_id and call vision API
    from src.python.llm.factory import get_provider_for_model
    provider = get_provider_for_model(model_id)

    if not provider.supports_vision():
        raise VisionNotSupportedError(
            f"Model {model_id} via {provider.name} does not support vision inputs. "
            f"Please select a vision-capable model in Settings."
        )

    result = provider.complete_vision(
        image_bytes=image_bytes,
        prompt=prompt,
        model_id=model_id,
    )

    _cache[cache_key] = result
    return result
```

Provider capability matrix (spec 15.13):
- Anthropic Claude: supported (Claude Sonnet/Opus)
- Google Gemini: supported
- Z.ai GLM: vision support varies; raise `VisionNotSupportedError` for unsupported models, fall back to Anthropic/Gemini per user preference

The `complete_vision` method needs to be added to the provider abstraction. Each provider implementation adds `supports_vision() -> bool` and `complete_vision(image_bytes, prompt, model_id) -> str`.

- [ ] **Step 4: Run tests (with `AT_VISION_TESTS=1`), expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/llm/vision.py tests/python/llm/test_vision.py
git commit -m "feat(llm): implement vision module for flowchart extraction"
```

---

### Task 16: Add "Vision model" Settings row

**Files:**
- Modify: `src/python/settings/router.py`
- Modify: `src/renderer/pages/Settings.tsx`
- Modify: `src/renderer/types/api.ts`
- Test: update Settings tests

Per spec 15.13: a distinct "Vision model" row in Settings so the user can pin a vision-capable model without affecting other LLM calls.

- [ ] **Step 1: Write failing test for backend setting**

```python
def test_vision_model_setting():
    # GET /settings returns vision_model field
    # PUT /settings with vision_model persists it
    pass
```

- [ ] **Step 2: Implement backend** — add `vision_model` to settings schema and router.

- [ ] **Step 3: Implement frontend** — add a "Vision model" dropdown in Settings under the existing model selection section. Dropdown lists only vision-capable models (filtered by `supports_vision()` from the provider matrix).

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/python/settings/ src/renderer/pages/Settings.tsx src/renderer/types/api.ts tests/
git commit -m "feat(settings): add Vision model selection row"
```

---

### Task 17: AT bundled Chroma + packaging updates

**Files:**
- Modify: `scripts/build_bundled_chroma.py` (add AT to build loop)
- Modify: `electron-builder.yml`
- Modify: `scripts/package-backend.sh`
- Modify: `scripts/package-backend.ps1`
- Test: update packaging tests if they exist

Add AT to the per-service bundled Chroma build. AT structured data is bundled into `build/resources/data/services/at/chroma/` for packaged builds.

- [ ] **Step 1: Update `build_bundled_chroma.py`** to include `at` in its service iteration loop. The script already iterates `REGISTRY` (from Plan A Task 23); verify it processes AT's `data/services/at/structured/` into `guidelines_at` and writes the Chroma tree.

- [ ] **Step 2: Update `electron-builder.yml`** to add AT's bundled Chroma tree:

```yaml
extraResources:
  # ... existing ACTAS entries ...
  - from: data/services/at/structured
    to: data/services/at/structured
    filter:
      - "**/*.json"
  - from: build/resources/data/services/at/chroma
    to: data/services/at/chroma
    filter:
      - "**/*"
```

- [ ] **Step 3: Update `scripts/package-backend.sh`** and `scripts/package-backend.ps1`** to copy AT structured data into the staging area.

- [ ] **Step 4: Run a packaging dry-run** (macOS arm64) and verify the AT data is included.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_bundled_chroma.py electron-builder.yml scripts/package-backend.sh scripts/package-backend.ps1
git commit -m "build: add AT bundled Chroma and packaging rules"
```

---

### Task 18: AT fixtures + sign-off checklist

**Files:**
- Create: `tests/python/fixtures/services/at/` (3 representative AT guideline JSONs)
- Test: `tests/python/services/test_isolation.py` (extend to include AT real data)

Create representative test fixtures and verify end-to-end AT pipeline behaviour against the sign-off checklist from `Guides/adding-a-service.md` Step 8.

- [ ] **Step 1: Create AT test fixtures**

Select three representative AT CPGs and create trimmed `GuidelineDocument` JSON files:

1. **AT_CPG_A0201-1.json** — Medical Cardiac Arrest (text-heavy, references multiple medicines)
2. **AT_CPG_D003.json** — Adrenaline monograph (dose-heavy, step-by-step dosing)
3. **AT_CPG_A0701.json** — A guideline with a flowchart (if flowcharts are data-driven)

Each fixture is a minimal valid `GuidelineDocument` with real section headings and a few lines of real content, committed under `tests/python/fixtures/services/at/`.

- [ ] **Step 2: Extend isolation test** to ingest AT fixtures and verify cross-service isolation still holds.

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/python/ -x -q
```

- [ ] **Step 4: Run the sign-off checklist** from `Guides/adding-a-service.md` Step 8:

**Scope-of-practice accuracy:**
- [ ] Every AT qualification level listed with correct scope (VAO, PARAMEDIC, ICP, PACER, CP_ECP)
- [ ] AT medication formulary (38 medicines) is accurate per qualification
- [ ] ICP/endorsement restrictions match actual AT CPG content
- [ ] No phantom medications listed (compare against Phase 0 Section 6.4 list of 38)

**Clinical content integrity:**
- [ ] Sample quiz questions from AT data are clinically accurate
- [ ] Source citations reference correct AT guidelines (e.g. `Ref: AT CPG A0201-1`)
- [ ] Feedback responses quote actual AT source text
- [ ] Flowchart conversions are clinically accurate (check golden flowcharts manually)

**Qualification filtering correctness:**
- [ ] Content tagged as PARAMEDIC-level is visible to PARAMEDIC, ICP, PACER, CP_ECP
- [ ] Content tagged as ICP-only is hidden from PARAMEDIC users
- [ ] VAO content is visible to all AT levels
- [ ] Cross-service isolation: ACTAS content does not appear in AT quizzes and vice versa

**Retrieval and quiz behaviour:**
- [ ] Retriever with `service_id="at"` queries only `guidelines_at` and `personal_at`
- [ ] `effective_qualifications` parameter correctly filters AT content
- [ ] Source ranking respects AT's `source_hierarchy`

**Packaging:**
- [ ] AT structured data is included in packaged app via `electron-builder.yml`
- [ ] `seed.py` correctly copies AT bundled data on first launch
- [ ] Settings page allows selecting AT as `active_service`

- [ ] **Step 5: Get user sign-off** on the checklist before marking Plan B complete.

- [ ] **Step 6: Commit**

```bash
git add tests/python/fixtures/services/at/ tests/python/services/test_isolation.py
git commit -m "test(at): add AT test fixtures and sign-off verification"
```

---

## Plan review corrections

Addresses plan-review feedback. Authoritative where it conflicts with earlier task descriptions.

### Task ordering fixes

- **Task 6 (flowcharts) depends on Task 15 (vision module) for image-based flowcharts.** Tasks 6 and 15 can be implemented in parallel if flowcharts are data-driven or SVG (paths 1 and 2). Image-based flowcharts (path 3) are not testable until Task 15 is complete. Task 6 tests cover only paths 1 and 2; path 3 is tested in Task 15.
- **Task 7 (qualification tagging) runs after Task 3 (content extraction)** because qualification markers are found within extracted content sections. Task 7 Step 3 probes the content sections for ICP/PACER/CP_ECP markers.
- **Task 14 (orchestrator) must be the last task in Phase 3** because it wires together all preceding modules. Each module is independently testable before orchestration.
- **Task 17 (packaging) depends on Task 11 (chunker) and Task 12 (medication index)** because `build_bundled_chroma.py` needs the chunker to produce the `guidelines_at` collection.

### Missing-task additions

**Task 9b — Update `Guides/scope-of-practice-at.md` with Phase 0 URL.** Between Task 9 and Task 10. The scope-of-practice doc has `[AT URL: TBD]` from Plan A Task 6. Now that Task 22 (Phase 0 probe) is complete, fill in the authoritative URL. Phase 0 findings (Section 12) confirm there is no separate scope-of-practice URL; the scope matrix is app-embedded at `https://cpg.ambulance.tas.gov.au`. Update the doc and remove `[REVIEW REQUIRED]` tags with confirmed information.

**Task 14b — Run pipeline against real AT data.** After Task 14 wires the orchestrator, run the full pipeline against the real AT CPG site. This produces `data/services/at/structured/*.json` files and the `guidelines_at` ChromaDB collection. Validate the output (count of guidelines, count of medicines, sample content inspection) before committing generated data.

### Task clarifications

- **Task 3 content extraction strategy.** The AT site embeds clinical content in lazy-loaded JS chunks (Phase 0 Section 4). Content is rendered as HTML within Ionic components. The extraction approach is: (a) download the lazy chunk for each guideline via the route slug, (b) parse the HTML template from the JavaScript string, (c) extract section headings and body text. This mirrors the ACTAS approach but adapts to AT's specific template structure.
- **Task 4 dose text fallback to LLM.** Regex extraction may not cover all dose narrative formats (e.g., "Administer 0.5 mL of 1:1000 adrenaline IM" or complex dilution instructions). The fallback is a structured-prompt LLM call using the user's cleaning model, with output validated against the `MedicationDose` schema. This fallback is gated: if regex produces zero results for a medicine known to have dosing, trigger the LLM path.
- **Task 6 flowchart format determination.** The `classify_flowchart_format()` function checks for JSON nodes/edges (data), SVG markup, PNG/JPG magic bytes, or PDF header. If a flowchart's format cannot be determined from the JS bundle alone, use Playwright to navigate to the flowchart route and capture a screenshot (path 3 fallback).
- **Task 15 provider abstraction extension.** Adding `supports_vision()` and `complete_vision()` to the provider interface is a prerequisite for the vision module. This requires updating `src/python/llm/factory.py` and each provider implementation. The vision tests are gated behind `AT_VISION_TESTS=1` to avoid burning API budget in routine CI.
- **Task 17 seed.py already iterates registry.** Plan A Task 14 rewrote `seed.py` to iterate all registered services. AT's bundled Chroma tree at `build/resources/data/services/at/chroma/` will be automatically discovered and seeded. No changes to `seed.py` are needed for AT.

### Vision settings row — explicit scope

The "Vision model" Settings row (Task 16) is distinct from the existing "Cleaning model" and "Quiz model" rows. The user selects a model specifically for vision tasks (flowchart extraction). The vision module falls back to Anthropic or Google if the user's selected provider doesn't support vision (per spec 15.13). The default vision model is the user's configured medium-tier model if it supports vision, otherwise the first vision-capable model in the registry.

---

## Acceptance criteria

At Plan B completion the app must:

- Successfully extract and structure the full AT CPG library (~80 adult guidelines, 38 medicines, ~10 obstetrics, ~6 paediatrics, reference notes) from the AT CPG site.
- Produce `data/services/at/structured/AT_CPG_*.json` files, each a valid `GuidelineDocument` conforming to the shared pydantic schema.
- Ingest all structured AT content into the `guidelines_at` ChromaDB collection with correct metadata (service, guideline_id, qualifications_required, chunk_type, source_type).
- Build a denormalised medication index at `data/services/at/medications/*.json` covering all 38 AT medicines.
- Tag every content section and medicine with `qualifications_required` reflecting the AT qualification model.
- Handle flowcharts via the appropriate path (data/SVG deterministic, image via vision LLM).
- Pass all AT-specific tests (adapter contract, extraction, chunker, structurer, qualifications, medications index).
- Pass the cross-service isolation test confirming ACTAS content does not appear in AT retrieval paths and vice versa.
- Bundle AT structured data and pre-built ChromaDB in the packaged app.
- Have a working `llm/vision.py` module with caching and the "Vision model" Settings row.
- Have user sign-off on the `Guides/adding-a-service.md` Step 8 checklist for AT.
- Have updated `Guides/scope-of-practice-at.md` with confirmed information from Phase 0.
