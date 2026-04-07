# CMG Bundling, Auto-Seed, and Refresh Fix

**Date:** 2026-04-07
**Status:** Approved

## Problem Statement

The release build has three issues:

1. **Broken buttons** — "Refresh CMGs" crashes with `ImportError: No module named 'pipeline.cmg.capture_assets'` because `capture_assets.py` doesn't exist. Button labels don't explain what they do.
2. **No ChromaDB on first launch** — Quiz and search are broken until the user manually triggers a pipeline run.
3. **No data freshness indicator** — Users can't tell how old the bundled CMG data is.

## Design Decisions

| Decision | Choice |
|----------|--------|
| ChromaDB seeding | Auto-seed in background thread on first launch |
| Capture date tracking | `.manifest.json` in `data/cmgs/structured/` |
| Button layout | Rebuild Index / Update from Web / Clear Vector Store + relabelled Notes Pipeline |
| Web update method | Playwright crawler → web_structurer → existing chunker |
| Update strategy | Incremental — compare version strings, only process changed guidelines |
| Structured data resolution | User-data overrides bundled per-file (fallback chain) |

---

## 1. Auto-Seed ChromaDB on First Launch

**Current:** `seed.py` creates empty directories. ChromaDB starts empty, breaking quiz and search.

**Change:** After directory creation, check if the `cmg_guidelines` ChromaDB collection has documents. If not, run `chunker.chunk_and_ingest()` against the bundled `CMG_STRUCTURED_DIR`.

- Runs in a background thread so the backend accepts requests immediately.
- Quiz/search endpoints return a "warming up" state until seeding completes.
- A module-level `seeding_complete: threading.Event` is set when done; quiz/search check this event before querying ChromaDB.
- On subsequent launches, the collection already has data, so seeding is skipped.

**Files changed:**
- `src/python/seed.py` — add `_seed_cmg_index()` function
- `src/python/quiz/router.py` (or retriever) — check seeding state before querying

**Paths involved:**
- Reads: `CMG_STRUCTURED_DIR` (bundled read-only in packaged mode)
- Writes: `CHROMA_DB_DIR` (writable user data)

---

## 2. Capture Date Manifest

**Current:** No way to know when bundled CMG data was captured.

**Change:**

### Manifest file format

`data/cmgs/structured/.manifest.json`:
```json
{
  "captured_at": "2025-04-07T10:30:00+00:00",
  "source": "cmg.ambulance.act.gov.au",
  "pipeline_version": "1",
  "guideline_count": 55,
  "medication_count": 35,
  "clinical_skill_count": 99
}
```

### Generation

- Appended to the orchestrator's final stage (`version_tracker.py` or a new stage).
- Counts are derived from the structured output files.
- Bundled in `electron-builder.yml` alongside the structured JSON.

### API

- `GET /settings/cmg-manifest` — reads `.manifest.json` from the resolved structured dir (user-data first, then bundled).

### UI

- Settings > Data Management displays: "Bundled CMG data captured: 7 Apr 2025"
- When "Update from Web" completes, the manifest is updated in user-data with the new crawl date and "Updated from web" annotation.

**Files changed:**
- `src/python/pipeline/cmg/version_tracker.py` (or orchestrator) — generate manifest
- `electron-builder.yml` — bundle `.manifest.json`
- `src/python/settings/router.py` — add `/settings/cmg-manifest` endpoint
- `src/renderer/pages/Settings.tsx` — display capture date
- `src/renderer/providers/SettingsProvider.tsx` — fetch manifest

---

## 3. Button Redesign

**Current:**
- "Re-run Pipeline" → Notability ingest (unrelated to CMGs)
- "Refresh CMGs" → crashes
- "Clear Vector Store" → works

**New layout in Settings > Data Management:**

### CMG Data section

| Button | Action | Description |
|--------|--------|-------------|
| **Rebuild Index** | Re-chunk bundled structured JSON into ChromaDB | "Re-ingest the bundled CMG data into the search index. Use this if quiz or search results seem incomplete." |
| **Update from Web** | Playwright crawl → structure → chunk (incremental) | "Download the latest CMG data from cmg.ambulance.act.gov.au. Requires an internet connection." |
| **Clear Vector Store** | Delete ChromaDB | "Delete all indexed data. The next search or quiz will trigger a rebuild." |

### Notes Pipeline section (separated)

| Button | Action | Description |
|--------|--------|-------------|
| **Re-run Notes Pipeline** | Notability ingest | "Re-process personal study notes into the search index." |

### Status display

- Bundled data capture date (from manifest)
- Last web update date
- Last rebuild date
- Running/error states per operation

### Backend changes

- `POST /settings/cmg-rebuild` (new) — runs `chunker.chunk_and_ingest()` from bundled structured dir. Background thread with status tracking.
- `POST /settings/cmg-refresh/run` (fixed) — runs the incremental web update flow (see section 4).
- `POST /settings/pipeline/rerun` — unchanged, relabelled in UI only.

**Files changed:**
- `src/python/settings/router.py` — add `/cmg-rebuild` endpoint, fix `/cmg-refresh/run`
- `src/python/pipeline/cmg/refresh.py` — remove `capture_assets` import, integrate new flow
- `src/renderer/pages/Settings.tsx` — new button layout with descriptions
- `src/renderer/providers/SettingsProvider.tsx` — add `rebuildIndex` action

---

## 4. Update from Web — Incremental Playwright Flow

### Overview

```
"Update from Web" button
  │
  ▼
refresh.py::run_refresh()
  │
  ├── 1. discover_metadata() — lightweight crawl of guideline list
  │     Extract: title, version string, date per guideline
  │
  ├── 2. compare_versions() — compare against bundled structured JSON
  │     Identify: new, updated, unchanged, removed guidelines
  │
  ├── 3. discover_changed() — full Playwright crawl of changed only
  │     Output: crawled HTML/text per changed guideline
  │
  ├── 4. web_structurer.py — parse crawled HTML → CMGGuideline models
  │     Output: structured JSON in USER_CMG_STRUCTURED_DIR
  │
  ├── 5. chunker.py — re-chunk affected guidelines into ChromaDB
  │     Delete old chunks for changed guidelines, ingest new ones
  │
  ├── 6. Update manifest with new capture date
  │
  └── 7. Invalidate caches
```

### New module: `pipeline/cmg/web_structurer.py`

Parses crawled HTML into `CMGGuideline` Pydantic models:
- `cmg_number`, `section` — from title/category mapping (reuse `selector_extractor.py` data)
- `content_markdown` — HTML → markdown conversion
- `dose_lookup` — parse HTML tables from crawled content
- `is_icp_only` — from category or content indicators
- `extraction_metadata.timestamp` — crawl timestamp
- Version string and date preserved in metadata

### New module: `pipeline/cmg/discover_metadata.py`

Lightweight function that:
- Uses Playwright to load the CMG listing page only
- Extracts guideline titles + version strings + dates from the list
- Does NOT crawl individual guideline pages
- Returns a dict of `{guideline_id: {version, date, title}}`

### Fallback chain: `USER_CMG_STRUCTURED_DIR` → `CMG_STRUCTURED_DIR`

- New path constant: `USER_CMG_STRUCTURED_DIR = DATA_DIR / "cmgs" / "structured"`
- Resolver function in `paths.py`: `resolve_cmg_structured(guideline_id)` checks user-data first, then bundled
- Guidelines router and chunker use the resolver
- Per-file override: if a guideline exists in user-data (from web update), it takes precedence over the bundled version

### Version comparison

- Extend `version_tracker.py` to store web version strings (e.g. "1.0.2.1") and dates
- During "Update from Web", compare crawled metadata against tracked versions
- Only flag as "changed" if version string differs or guideline is new
- Unchanged guidelines remain served from bundled JSON

### Error handling

- If Playwright is not installed: show clear error message "Playwright is required for web updates. Install with..."
- If network unavailable: show "Unable to connect to cmg.ambulance.act.gov.au"
- If individual guideline crawl fails: log and continue (don't fail the whole batch)
- If structurer fails for a guideline: fall back to chunking raw text for that guideline only

**Files changed:**
- `src/python/pipeline/cmg/refresh.py` — rewritten flow
- `src/python/pipeline/cmg/web_structurer.py` — new
- `src/python/pipeline/cmg/discover_metadata.py` — new
- `src/python/pipeline/cmg/discover.py` — minor adjustments for metadata extraction
- `src/python/pipeline/cmg/version_tracker.py` — extend with web version tracking
- `src/python/paths.py` — add `USER_CMG_STRUCTURED_DIR`, add resolver
- `src/python/guidelines/router.py` — use resolver for structured dir

---

## Implementation Order

1. **Auto-seed ChromaDB** (independent, high impact)
2. **Capture date manifest** (independent, simple)
3. **Fix and relabel buttons** (independent, includes new `/cmg-rebuild` endpoint)
4. **Update from Web — Playwright flow** (depends on 1-3, most complex)

Steps 1-3 can ship together. Step 4 is additive and can follow.

---

## Testing Strategy

- **Auto-seed:** Unit test that verifies `seed.py` calls chunker when ChromaDB is empty, skips when populated. Integration test: fresh ChromaDB dir → seed → verify collection has documents.
- **Manifest:** Unit test for manifest generation during pipeline run. Verify bundled in electron-builder output.
- **Buttons:** Backend tests for new `/cmg-rebuild` endpoint. Frontend tests for button rendering and descriptions.
- **Web update:** Unit tests for `discover_metadata.py` (mock Playwright), `web_structurer.py` (crawled HTML → structured JSON), version comparison logic. Integration test with mock crawled data.
- **Fallback chain:** Unit test for path resolver with user-data override.
