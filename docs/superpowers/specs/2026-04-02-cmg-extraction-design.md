# Phase 2 Core Extraction: Direct JS Bundle Parsing

**Date:** 2026-04-02
**Status:** Approved
**Scope:** CMG pipeline core extraction only — dose validation, vision LLM flowcharts, and re-scraping deferred.

---

## Context

Phase 2's pipeline architecture is complete (10 Python files in `src/python/pipeline/cmg/`), but the extraction logic produces mock data. The actual CMG data exists in ~300 JavaScript files downloaded from the ACTAS CMG web app into `data/cmgs/investigation/`. The main bundle (`2_main.*.js`, 9.9MB) contains navigation metadata for all 52 CMGs. Guideline content is spread across 35 JS chunks as compiled Angular template instructions (~141K chars of clinical text).

---

## Approach: Direct JS Bundle Parsing (Offline)

All data is already downloaded. No network access required.

---

## Architecture: 3-Stage Pipeline

```
JS Bundles (data/cmgs/investigation/)
    |
    +-> Stage 1: Navigation Extractor
    |     Input:  2_main.*.js (9.9MB)
    |     Output: cmg_navigation.json (52 CMGs + 340 pages)
    |
    +-> Stage 2: Content Extractor
    |     Input:  35 JS chunks with clinical text
    |     Output: cmg_content.json (text per page, keyed by spotlightId)
    |
    +-> Stage 3: Mapper + Structurer
          Input:  cmg_navigation.json + cmg_content.json
          Output: Structured guidelines -> existing structurer/chunker -> ChromaDB
```

---

## Stage 1: Navigation Extractor

**Input:** `data/cmgs/investigation/2_main.*.js`
**Output:** `data/cmgs/raw/cmg_navigation.json`

### What to extract

The main bundle contains a JSON-like navigation tree with entries like:

```json
{
  "title": "General Care",
  "section": "CMG 1",
  "spotlightId": "1iA3FOWukpEi",
  "icon": "angle-double-right",
  "color": "default",
  "atp": ["p", "icp"],
  "tags": ["patient"]
}
```

- **52 CMG guideline entries** with section numbers
- **340 total pages** (CMGs + sub-pages, skills, calculators, reference tools)
- **Section hierarchy**: parent folders containing child pages

### How

1. Scan for JSON arrays containing objects with `spotlightId` fields
2. Use balanced bracket matching to extract the full structure
3. Parse nested section→pages hierarchy

---

## Stage 2: Content Extractor

**Input:** 35 JS chunks in `data/cmgs/investigation/`
**Output:** `data/cmgs/raw/cmg_content.json`

Two sub-problems:

### 2a: Component-to-route mapping

The main bundle contains lazy-loading route definitions that map route paths to chunk filenames. Extract this mapping to determine which JS chunk serves which CMG page.

The route config typically looks like:
```js
{path: "cmg-1-general-care", loadChildren: () => import("./path/to/chunk.js")}
```

Extract all `loadChildren` / `loadComponent` route mappings from the main bundle.

### 2b: Angular compiled template parsing

Angular compiles component templates into instruction sequences:

| Instruction | Meaning |
|-------------|---------|
| `.EFF(N, "text")` | Text node |
| `.j41(N, "tag", attrs)` | Open element |
| `.k0s()` | Close element |
| `.Y8G("prop", value)` | Bind property |
| `.nrm(N, "tag", attrs)` | Create element (self-closing) |

**Extraction strategy:**
1. For each JS chunk, find all string literals (the clinical text content)
2. Extract text content by matching `.EFF(N, "...")` patterns
3. Reconstruct basic HTML structure by interpreting element open/close instructions
4. Handle Unicode escapes (`\u2019` -> `'`, `\u00b0` -> degree symbol, etc.)
5. Handle minified variable names by matching instruction patterns, not variable names

**Top content files by volume:**

| File | Clinical strings | Content chars |
|------|-----------------|---------------|
| `7_common.*.js` | 397 | 73,169 |
| `2_main.*.js` | 27 | 18,086 |
| `114_30259.*.js` (Palliative Care) | 49 | 14,429 |
| `6_8166.*.js` | 5 | 4,711 |
| `15_22517.*.js` | 29 | 4,349 |

---

## Stage 3: Integration with Existing Pipeline

The existing `structurer.py` and `chunker.py` are complete and working.

1. **Merge navigation + content** using `spotlightId` as the join key
2. **Build CMG guideline objects** — one per CMG, containing all its pages' content and metadata
3. **Feed into existing structurer** — normalizes to the Pydantic schema in `models.py`
4. **Ingest into ChromaDB** — existing chunker handles this with `source_type: "cmg"`

---

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `src/python/pipeline/cmg/extractor.py` | **Rewrite** | Replace mock fallback with real JS bundle parsing (Stage 1 + 2) |
| `src/python/pipeline/cmg/template_parser.py` | **New** | Angular compiled-template instruction parser |
| `src/python/pipeline/cmg/dose_tables.py` | **Update** | Extract real dose data from `7_common.*.js` |
| `src/python/pipeline/cmg/orchestrator.py` | **Update** | Wire new extraction stages |

---

## Error Handling

- **Files with no clinical content**: Skip silently, log count
- **Unicode escapes**: Handle `\uXXXX` patterns via standard Python decoding
- **Minified variable names**: Parse by instruction pattern (`.EFF`, `.j41`, `.k0s`), not by variable name
- **Missing route mappings**: Store as "unmapped" for later review
- **Empty content pages**: Log warning, include in output with empty content field
- **Mock removal**: Remove all mock data fallbacks once real extraction works

---

## Dose Tables (Real Extraction)

The `7_common.*.js` file (1.2MB, 397 clinical strings) contains the medicine dose lookup tables. The existing `dose_tables.py` creates mock data. Update it to:

1. Find the dose calculation service in `7_common.*.js`
2. Extract the pre-computed weight-band lookup tables (the app uses `dose[weight]` and `vol[weight]` patterns)
3. Parse medicine names, indications, and dose/volume pairs per weight band
4. Output structured dose table JSON

---

## Out of Scope (Deferred)

- Dose validation against known values (TODO 2B)
- Vision LLM for image-based flowcharts (TODO 2C)
- Flowchart validation against originals (TODO 2C)
- Periodic re-scraping mechanism (TODO 2E)

These are tracked in TODO.md and will be addressed in follow-up work.
