# Phase 2 Design: ACTAS CMG Extraction Pipeline

**Date:** 2026-04-01
**Status:** Approved
**Scope:** Full Phase 2 (2A-2E) — Discovery through ingestion and version tracking

---

## Overview

Extract all ACTAS Clinical Management Guidelines from the CMG web app (`https://cmg.ambulance.act.gov.au`) into structured, queryable data stored in ChromaDB. The pipeline targets raw JSON data from the site's JavaScript bundle rather than rendered HTML, preserving the full data hierarchy.

Key constraint: medicine dose data is pre-computed lookup tables (24 weight bands x medicines x indications), not formula-based calculators. Vision LLM for image-based flowcharts is deferred — SVG flowcharts only in this phase.

---

## Architecture: Modular Pipeline

Separate module per stage. Each stage reads the previous stage's output file and writes its own. Stages are independently testable and re-runnable.

### Module Structure

```
src/pipeline/cmg/
├── __init__.py
├── models.py          # Pydantic schemas
├── discover.py        # Stage 1: Playwright SPA discovery, JS bundle capture
├── extractor.py       # Stage 2: Parse JS bundle into raw guideline JSON
├── dose_tables.py     # Stage 3: Extract pre-computed dose lookup tables
├── flowcharts.py      # Stage 4: SVG to Mermaid.js conversion
├── structurer.py      # Stage 5: Normalise to CMG Guideline Schema
├── chunker.py         # Stage 6: Semantic chunking + ChromaDB ingestion
├── version_tracker.py # Stage 7: Version/date tracking, change detection
├── orchestrator.py    # Chains stages, error handling, CLI
```

### Data Flow

```
discover.py    → data/cmgs/raw/discovery.json       (JS bundle URLs, captured payloads)
extractor.py   → data/cmgs/raw/guidelines.json       (raw guideline data)
dose_tables.py → data/cmgs/raw/dose_tables.json       (dose lookup tables)
flowcharts.py  → data/cmgs/flowcharts/*.mmd           (Mermaid.js files)
structurer.py  → data/cmgs/structured/*.json           (validated schema objects)
chunker.py     → data/chroma_db/                       (ChromaDB, source_type="cmg")
version_tracker → data/cmgs/version_tracking.csv       (version tracking)
```

Each stage's output is the next stage's input. This enables:
- Re-running structuring without re-extracting
- Reviewing discovery output before proceeding
- Independent testing with fixture data

---

## Stage 1: Discovery (`discover.py`)

Uses Playwright (sync API) for headless browser automation.

**Steps:**
1. Launch headless Chromium, navigate to `https://cmg.ambulance.act.gov.au/tabs/guidelines`
2. Intercept all network responses during page load — capture URL, content-type, size, and full JSON payloads
3. Identify the primary data payload (the ~10MB main JS bundle)
4. Download and save the JS bundle to `data/cmgs/raw/main.js`
5. If no JSON API is found, fall back to probing common asset paths (`/assets/data/guidelines.json`, etc.)

**Output:** `data/cmgs/raw/discovery.json`
```json
{
  "url": "https://cmg.ambulance.act.gov.au/tabs/guidelines",
  "captured_at": "2026-04-01T...",
  "js_bundles": [{"url": "...", "size_bytes": 10485760}],
  "json_payloads": [{"url": "...", "size_bytes": 5000}],
  "asset_paths_probed": ["..."],
  "recommendation": "js_bundle_extraction"
}
```

The orchestrator pauses after discovery for manual review before proceeding to extraction.

---

## Stage 2: Guideline Extraction (`extractor.py`)

Parses the downloaded JS bundle to extract all clinical guidelines.

**Steps:**
1. Load the JS bundle from `data/cmgs/raw/main.js`
2. Regex-based parsing to find guideline data structures — `MED##` section codes, weight band references, clinical text blocks
3. Extract each guideline as raw JSON: CMG number, title, section text (HTML), embedded tables, version dates, internal cross-references
4. Output array of raw guideline objects

**Output:** `data/cmgs/raw/guidelines.json`

Errors are logged per-guideline without failing the batch.

---

## Stage 3: Dose Table Extraction (`dose_tables.py`)

Extracts pre-computed dose lookup tables from the JS bundle.

**Steps:**
1. Search for weight band markers (24 bands: 3kg newborn through 120kg adult)
2. Extract complete lookup table: all medicines x all indications x all weight bands
3. Validate completeness:
   - All 24 weight bands present
   - All medicines and indications captured
   - Spot-check known values (e.g. Adrenaline 25kg Anaphylaxis = 0.25mg IM)

**Output:** `data/cmgs/raw/dose_tables.json`
```json
{
  "weight_bands": [
    {"id": "w3", "weight_kg": 3, "label": "3kg (Newborn)"},
    {"id": "w25", "weight_kg": 25, "label": "25kg (8 years)"}
  ],
  "medicines": [
    {"id": "MED03", "name": "Adrenaline", "indications": ["Anaphylaxis", "Cardiac Arrest"]}
  ],
  "dose_table": {
    "w25": {
      "Adrenaline": {
        "Anaphylaxis": {
          "route": "IM",
          "dose": "0.25 mg",
          "volume": "0.25 ml",
          "notes": "Repeat @5/60 if required (max. 3 doses)"
        }
      }
    }
  }
}
```

---

## Stage 4: Flowchart Conversion (`flowcharts.py`)

SVG-based flowcharts only. Image-based flowcharts are flagged for future vision LLM processing.

**Steps:**
1. Extract SVG flowchart elements from the JS bundle or rendered DOM
2. Parse SVG `<text>`, `<path>`, `<line>` elements
3. Spatial analysis: sort nodes by Y position (top-to-bottom flow)
4. Reconstruct as Mermaid.js `graph TD` code:
   - Decision nodes (containing "?", "if", "yes/no") → `{}` diamond syntax
   - Process nodes → `[]` rectangle syntax
   - Terminal nodes → `(()) rounded syntax
5. Syntax validation on each Mermaid file
6. Image-based flowcharts get a placeholder: `[VISION_LLM_REQUIRED: <description>]`

**Output:** Individual `.mmd` files in `data/cmgs/flowcharts/`, named by CMG number.

---

## Stage 5: Schema Normalisation (`structurer.py`)

Maps raw extraction data to the CMG Guideline Schema using Pydantic models.

**Pydantic model fields per CMG:**
- `id`: unique identifier (e.g. `CMG_12_Asthma`)
- `cmg_number`: original number (e.g. `12`, `14C`)
- `title`: guideline title
- `version_date`: official version date
- `section`: clinical category enum (Respiratory, Cardiac, Trauma, Medical, Pediatric, Obstetric, Other)
- `content_markdown`: HTML to Markdown conversion (tables → pipe format, headings normalised, clinical notation preserved exactly)
- `dose_lookup`: attached for medicine CMGs
- `flowchart`: Mermaid code attached if present
- `checksum`: SHA-256 of content for change detection
- `extraction_metadata`: timestamp, source type, agent version

**Process:**
1. Read raw guidelines from `extractor.py` output
2. Read dose tables from `dose_tables.py` output (attach to relevant medicine CMGs)
3. Read flowcharts from `flowcharts.py` output (attach to relevant CMGs)
4. Convert HTML content to Markdown
5. Validate each CMG against Pydantic schema — malformed CMGs logged and skipped
6. Write individual validated JSON files

**Output:** `data/cmgs/structured/CMG_12_Asthma.json` etc.

---

## Stage 6: Semantic Chunking and ChromaDB Ingestion (`chunker.py`)

### Chunking Strategy

Semantic chunk types with token-aware splitting:

| Chunk Type | Trigger Headers | Max Tokens |
|------------|----------------|------------|
| Dosage | dosage, administration, dose, amount | 500 |
| Safety | contraindications, warnings, precautions | 300 |
| Protocol | procedure, treatment, management | 1000 |
| Reference | table, appendix, reference | 800 |
| Assessment | indications, presentation, diagnosis | 400 |
| General | (default) | 600 |

Process: scan markdown headers, classify chunk type, split content when token limit is reached, carry type forward for continuation chunks.

### ChromaDB Ingestion

- `PersistentClient` instance (same as Notability pipeline)
- Collection: `"cmg_guidelines"` (separate collection per source type)
- Metadata per chunk:
  - `source_type`: `"cmg"`
  - `source_file`: original CMG JSON filename
  - `cmg_number`: e.g. `"12"`, `"14C"`
  - `section`: clinical category
  - `chunk_type`: `"dosage"`, `"safety"`, `"protocol"`, etc.
  - `last_modified`: ISO date
- Embedding function: ChromaDB default (or matching the Notability pipeline's choice)

---

## Stage 7: Version Tracking (`version_tracker.py`)

Tracks CMG version dates and content checksums for update detection.

**Process:**
1. After each extraction run, compare new data against `data/cmgs/version_tracking.csv`
2. New CMGs: added with status `"new"`
3. Changed CMGs (different checksum): status `"updated"`, previous version preserved
4. Unchanged CMGs: status `"unchanged"`
5. Output updated CSV with columns: `id`, `title`, `version_date`, `checksum`, `status`, `last_extracted`

This enables future periodic re-scraping to detect and ingest only changed guidelines.

---

## Orchestrator (`orchestrator.py`)

Pipeline entrypoint that chains all stages.

### CLI Interface

```bash
# Full pipeline
python -m pipeline.cmg.orchestrator

# Specific stages only
python -m pipeline.cmg.orchestrator --stages discover
python -m pipeline.cmg.orchestrator --stages structure,ingest

# Dry run (no ChromaDB writes)
python -m pipeline.cmg.orchestrator --dry-run
```

### Run Flow

1. Parse CLI args (stages, dry-run flag)
2. Run each requested stage in sequence
3. After discovery: pause for manual review if interactive
4. Per-CMG error handling: log errors with CMG number and stage, continue processing
5. Progress reporting: `Processing CMG 14/47: Asthma...`
6. Summary report at end: extracted count, structured count, chunked count, errors, warnings

### Error Handling

| Scenario | Response |
|----------|----------|
| Network failure during discovery | Retry 3x with exponential backoff. Use cached JS bundle if available. |
| JS bundle format changed | Log warning, attempt adaptive parsing, flag for review. |
| Pydantic validation failure | Log the CMG and skip. Don't fail the batch. |
| Missing weight bands in dose table | Log warning, save partial data, flag in report. |
| Mermaid syntax error | Log warning, save raw SVG as fallback. |
| ChromaDB write failure | Retry once, then log and continue. |

---

## Pydantic Models (`models.py`)

Core schemas:

- `WeightBand`: id, weight_kg, label
- `MedicineEntry`: id, name, indications, routes
- `DoseEntry`: indication, route, dose, volume, notes, presentation, concentration
- `FlowchartEntry`: cmg_number, mermaid_code, source_type ("svg" | "image_flagged")
- `CMGGuideline`: full schema with all fields from Section 5 above
- `DiscoveryResult`: captured JS bundles, JSON payloads, recommendation
- `ExtractionResult`: summary with counts, errors, warnings

---

## Testing Strategy

- **Unit tests** per module with fixture data (small sample JS bundle, mock SVG, test guideline JSON)
- **Integration test** running the full pipeline on a captured JS bundle
- **Validation tests** spot-checking extracted doses against known correct values
- Tests in `tests/python/test_cmg_pipeline.py`

---

## Scope Boundaries

**In scope:**
- Full discovery and extraction pipeline (2A-2E)
- SVG-based flowchart conversion
- ChromaDB ingestion with metadata
- Version tracking for future re-scraping
- Per-stage CLI control and dry-run mode

**Explicitly deferred:**
- Vision LLM for image-based flowcharts (flagged with placeholders)
- LLM provider abstraction layer (not needed for SVG-only flowcharts)
- Automated periodic re-scraping (version tracking infrastructure is built, scheduling is not)
- GUI integration (the Source Pipeline screen in Phase 6 will visualise this data)
