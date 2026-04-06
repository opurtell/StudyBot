# Clinical Recall Assistant — Development TODO

**Last Updated:** 2026-04-04

Legend: `[ ]` = Not started | `[~]` = In progress | `[x]` = Complete | `[!]` = Blocked

---

## Active Planning Artefacts

- [x] Loading reliability Phase 1: backend lifecycle control and renderer boot gating
  - [x] Electron backend status state machine and preload IPC
  - [x] Renderer backend status provider and boot gate
  - [x] Startup shell and backend failure retry path
  - [x] Renderer coverage for boot gating and backend status updates
- [x] Renderer API client centralisation phase
  - [x] Spec written (`docs/superpowers/specs/2026-04-04-renderer-api-client-centralisation.md`)
  - [x] Implementation plan written (`docs/superpowers/plans/2026-04-04-renderer-api-client-centralisation.md`)
  - [x] Implement central client contract hardening and hook refactors
  - [x] Add renderer transport-layer and hook coverage
  - [x] Verify with targeted `vitest` runs and `npx tsc --noEmit`
- [x] Loading reliability caching and read-path phase
  - [x] Renderer shared cache/provider layer for settings and read-mostly datasets
  - [x] Stale-while-refresh page states on Dashboard, Guidelines, Medication, and Settings
  - [x] Backend guideline and medication read caches with explicit invalidation
  - [x] Precomputed `guidelines-index.json` and `medications-index.json`
  - [x] Search and quiz disablement/loading-state refinement for backend loss
  - [x] Targeted renderer and Python cache coverage plus `npx tsc --noEmit`

---

## Phase 0: Project Setup and Scaffolding

- [x] Create project brief and vision (`brief.md`)
- [x] Define source hierarchy and language rules (`generalRules.md`)
- [x] Create acronym reference (`acronyms.md`)
- [x] Create ACTAS CMG scraping guide (`Guides/AI_Agent_Guideline_ACTAS_CMG_Scraping_Framework.md`)
- [x] Create Notability format guide (`Guides/NOTABILITY_FORMAT_GUIDE.md`)
- [x] Create pipeline agent guide (`Guides/PIPELINE_AGENT_GUIDE.md`)
- [x] Create Stitch UI design prototype (`stitchDesign/`)
- [x] Create CLAUDE.md development guide
- [x] Create TODO.md progress tracker
- [x] Initialise git repository
- [x] Confirm technology stack (GUI framework, bundler, etc.)
- [x] Set up project scaffolding (package.json / pyproject.toml, directory structure)
- [x] Create `InfoERRORS.md` for user-flagged corrections
- [x] Set up Electron main process with Python backend spawn
- [x] Set up React renderer with Vite + Tailwind CSS
- [x] Add PostCSS config for Tailwind

---

## Phase 1: Data Pipeline — Notability Notes

**Goal:** Convert `.note` files into clean, chunked markdown in the vector store.

### 1A: Extractor
- [x] Implement `.note` → raw text extractor (`src/python/pipeline/extractor.py`)
  - [x] Parse `HandwritingIndex/index.plist` for OCR text
  - [x] Parse `metadata.plist` for title, subject, date
  - [x] Handle edge cases: missing HandwritingIndex, empty pages, duplicate folders
- [x] Test extractor on sample files from each subject folder
- [x] Handle the duplicate `Paramedics 2021 sem 1` directories (trailing space issue)

### 1B: Clinical Dictionary
- [x] Create `clinical_dictionary.py` with paramedicine-specific terms
- [x] Map Notability subject folders to clinical categories
- [ ] Extend dictionary as new terms are encountered during processing

### 1C: OCR Cleaning Agent
- [x] ~~Implement LLM-powered cleaning agent (`src/python/pipeline/cleaning_agent.py`)~~ — pivoted to Claude Code subagents
- [x] System prompt: fix OCR errors only, never rephrase or add content (`cleaning_prompt.md`)
- [x] `[REVIEW_REQUIRED: ...]` flagging for uncertain corrections
- [x] Clean all extracted notes via batched Claude Code subagents (28 raw → 25 cleaned)
- [x] Review and resolve `[REVIEW_REQUIRED]` flags across cleaned files

### 1D: Markdown Structurer
- [x] Implement structurer with YAML front matter (`src/python/pipeline/structurer.py`)
- [x] Output to `docs/notabilityNotes/mdDocs/` (or `data/notes_md/`)
- [x] Preserve subject folder hierarchy in output

### 1E: Chunker and Vector Store Ingestion
- [x] Implement chunker with ChromaDB ingestion (`src/python/pipeline/chunker.py`)
- [x] RecursiveCharacterTextSplitter: 800 chars, 100 overlap
- [x] ChromaDB PersistentClient, collection: `"paramedic_notes"`
- [x] Chunk metadata: source_file, category, last_modified, has_review_flag

### 1F: Full Pipeline Orchestration
- [x] Create pipeline entrypoint that chains all stages (`src/python/pipeline/run.py`)
- [x] Per-file error handling (log and continue)
- [x] Progress reporting (X files processed)
- [x] Dry-run mode for testing without writes
- [x] Run OCR cleaning on all extracted notes (100% complete)
- [x] Run ingestion pipeline to chunk and ingest cleaned files into ChromaDB (2,209 chunks in `paramedic_notes` collection)
- [x] Review and resolve `[REVIEW_REQUIRED]` flags

---

## Phase 2: Data Pipeline — ACTAS CMGs

**Goal:** Extract all clinical management guidelines from the ACTAS web app into structured, queryable data.

### 2A: Discovery and Extraction
- [x] Set up Playwright for SPA rendering
- [x] Intercept network traffic to identify data payloads (`src/python/pipeline/cmg/discover.py`)
- [x] Locate and extract the main JS bundle (~10MB) (`src/python/pipeline/cmg/extractor.py`)
- [x] Parse embedded guideline JSON data

### 2B: Medicine Dose Tables
- [x] Extract dose data from clinical text (`src/python/pipeline/cmg/dose_tables.py`)
- [x] All 35 ACTAS medicines and their indications extracted (35 JSON files in `data/cmgs/structured/med/`)
- [x] Validate extracted doses against known values (spot-check)
- [x] Segment dose groups per route/page instead of single large block
- [x] Fix dose grouping (was 1 mega-group → 538 focused groups via per-file processing + boundary detection)
- [x] Selector-based medicine identification for medicines whose `.EFF()` texts lack keywords (Fentanyl, Calcium Chloride, Ipratropium, Salbutamol, Topical Anaesthetic)
- [x] Remove phantom keywords (entinox, tetracaine, tranexamic, clopidogrel, etc. — not in ACTAS formulary)
- [ ] Extract weight-band dose tables from Critical Care Reference Cards chunk (`118_38576.*.js`, 1525 `.EFF`)

### 2C: Flowcharts and Visual Content
- [~] Extract SVG-based flowcharts → Mermaid.js format (`src/python/pipeline/cmg/flowcharts.py`) — current module is still mock/stub logic
- [ ] Use vision LLM for image-based flowcharts
- [ ] Validate reconstructed flowcharts against originals

### 2D: Structuring and Ingestion
- [x] Structure CMG data into JSON conforming to the CMG Guideline Schema (`src/python/pipeline/cmg/structurer.py`)
- [x] Chunk and ingest into ChromaDB (406 chunks in `cmg_guidelines` collection, `source_type: "cmg"`) (`src/python/pipeline/cmg/chunker.py`)
- [x] Add CMG-specific metadata: `cmg_number`, `section`, `version_date`

### 2E: Clinical Skills (CSM)
- [x] Extract and structure clinical skill monographs (99 JSON files in `data/cmgs/structured/csm/`)
- [x] CSM data available via `/guidelines` endpoint with `type=skill` filter

### 2F: Version Management
- [x] Track CMG version dates for update detection (`src/python/pipeline/cmg/version_tracker.py`)
- [ ] Plan for periodic re-scraping (CMGs are updated)

### 2G: Core Extraction Improvements
- [x] Fix 2 unmatched CMGs — title-to-slug drops special chars (`Cardiac Arrest: Paediatric (<12 years old)`, `Febrile Paediatric (<12yo)`)
- [x] Strip UI boilerplate from extracted content ("More information", "Tap to zoom", "Open print version", "My Notes")
- [x] Per-route content attribution — assign each template block to its route instead of dumping all 7_common blocks per route
- [x] Filter non-clinical template blocks (headers, nav components, settings) from content output
- [x] Add content length sanity check — flag CMGs with < 50 chars of clinical text
- [x] Handle inline module content in 7_common separately from chunk-file content to avoid duplication
- [x] Fix selector extractor to scan all JS bundles (was 7_common only — Skills Matrix CSM was in `298_33493`)
- [x] Add number-to-word normalization for route matching ("12" ↔ "twelve", "15" ↔ "fifteen")
- [x] Add word-overlap and distinctive-word scoring for selector fallback matching
- [x] Resolve 10/11 short-content CSM entries (only Skills Matrix was unresolved, now fixed via multi-bundle scanning)

---

## Phase 3: Data Pipeline — Personal Docs

**Goal:** Ingest the existing markdown reference documents.

- [x] Scan `docs/REFdocs/` and `docs/CPDdocs/` for all `.md` files
- [x] Chunk and ingest into ChromaDB (`source_type: "ref_doc"` / `"cpd_doc"`)
- [x] Assign categories based on filename mapping via `clinical_dictionary.py`
- [x] Handle the large `ECGs.md` file (~269KB) with header-aware splitting (394 chunks)

---

## Phase 4: Quiz Agent

**Goal:** Build the LLM-powered quiz generation and evaluation engine.

### 4A: Question Generation
- [x] Implement RAG-based question generation from vector store
- [x] Support full quiz (all categories) and targeted quiz (specific category/topic)
- [x] Question types: free-text recall, definition, clinical scenario, drug dose
- [x] Difficulty scaling based on mastery data

### 4B: Answer Evaluation
- [x] Implement answer comparison using retrieved source chunks
- [x] Generate structured feedback with:
  - [x] What was correct
  - [x] What was incorrect or missing
  - [x] Exact source citation (e.g. `Ref: ACTAS CMG 14.1`)
  - [x] Source text snippet ("From the Source")
- [x] Self-grading path: reveal reference without typing

### 4C: Blacklist System
- [x] Implement topic/information blacklist (persisted)
- [x] User can add/remove items from blacklist via settings
- [x] Quiz generation respects blacklist filters

### 4D: Knowledge Tracking
- [x] Track per-topic/per-category accuracy and attempt history
- [x] Calculate mastery scores for the heatmap
- [x] Identify knowledge gaps and suggest next study topics
- [x] Store in local SQLite database (`data/mastery.db`)

---

## Phase 5: GUI — Application Shell

**Goal:** Build the desktop application framework and navigation.

- [x] Confirm GUI framework choice (Electron vs Tauri)
- [x] Set up project with React + Tailwind CSS
- [x] Implement "The Archival Protocol" design system
  - [x] Colour tokens (surface hierarchy, accent colours)
  - [x] Typography scale (Newsreader, Space Grotesk, IBM Plex Mono)
  - [x] Component library (buttons, inputs, cards per DESIGN.md)
  - [x] The "No-Line" Rule enforcement
- [x] Persistent left sidebar navigation
- [x] Universal search bar
- [x] Dark mode support (high-contrast clinical theme)

---

## Phase 6: GUI — Screens

### 6A: Command Dashboard (Home)
- [x] Knowledge heatmap (category grid: red → green mastery)
- [x] Performance metrics cards (streak, accuracy, suggested topic)
- [x] "Start Session" primary action button
- [x] Recent archival entries list
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/refined_clinical_dashboard/`

### 6B: Active Recall Quiz
- [x] Large question display (Newsreader serif)
- [x] Text area for answer input
- [x] "Reveal Reference" button (self-grading path)
- [x] "Discard Draft" and "Submit Observation" buttons
- [x] Timer display
- [x] Progress bar (thin, non-intrusive)
- [x] Session info footer (archive index, curation mode)
- [x] Keyboard shortcuts (`useQuizShortcuts.ts`: 1/2 for grading, V to reveal, Escape to dismiss, Cmd+Enter to submit, Cmd+Shift+R to discard, Cmd+Shift+A to archive, Cmd+Arrow to navigate)
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/active_recall_quiz_v6.1/`

### 6C: Feedback and Citation Panel
- [x] Split view: practitioner response (left) vs AI analysis (right)
- [x] "ACTAS Ground Truth" section with exact source quote
- [x] Correction priority markers (sequence errors, critical deviations)
- [x] Response time and guideline delay metrics
- [x] Source footnotes with clickable citations
- [~] "Request Peer Review" action — button exists but currently only navigates back to `/quiz`
- [x] "Archive Analysis & Proceed" action
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/feedback_evaluation_cleaned/`

### 6D: Source Pipeline / Library
- [x] Document repository list with source cards
- [x] Sync status indicators and progress bars
- [x] "Clinical Cleaning Feed" toggle (shows AI cleaning in progress)
- [x] Filter repository controls
- [~] "New Documentation" button — visible but not wired to any action
- [x] Replace static/hardcoded source data with API-backed data
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/library_pipeline_v6.1/`

### 6E: Settings / Curator Settings
- [x] Quiz blacklist management (add/remove/edit excluded topics)
- [x] Model selection (quiz agent model, cleaning model)
- [x] API key configuration (3 providers: Anthropic, Google, Z.ai)
- [x] Model registry editor (3 providers × 3 tiers: low/medium/high)
- [x] Skill level selector (AP / ICP)
- [x] Theme toggle (light/dark)
- [~] Data management (re-run pipeline, clear vector store) — CMG refresh endpoints exist in backend but are not exposed in the renderer

### 6F: Clinical Guidelines Browser
- [x] Backend `/guidelines` list endpoint with type and section filters
- [x] Backend `/guidelines/{id}` detail endpoint
- [x] Frontend card grid grouped by section with type/section filter chips
- [x] Side panel detail view with rendered markdown (react-markdown)
- [~] Quiz scope picker (this guideline, this section, all guidelines) — picker UI exists but selected scope is not connected to quiz session generation
- [ ] Render `dose_lookup` and `flowchart` content in the guideline detail panel
- [x] Skill-level filtering (AP/ICP)
- [x] Sidebar navigation updated ("Clinical Guidelines" → `/guidelines`)
- [x] Backend and frontend tests

---

## Phase 7: Integration and Polish

- [x] Connect quiz agent to GUI screens
- [x] End-to-end quiz flow: dashboard → quiz → feedback → dashboard
- [x] Knowledge heatmap driven by real mastery data
- [x] Performance metrics calculated from quiz history
- [x] "Suggested Next Topic" based on gap analysis
- [x] Universal search connected to vector store
- [x] Error states and loading states for all screens
- [x] Keyboard shortcuts for quiz flow

---

## Phase 8: Testing and Validation

- [x] Unit tests for pipeline stages (extractor, cleaner, structurer, chunker)
- [~] Integration tests for full pipeline (1 test in `tests/pipeline/test_integration.py`)
- [x] Quiz agent evaluation (answer quality, citation accuracy)
- [x] UI component tests (22 test files covering all pages, components, and hooks)
- [x] End-to-end flow tests
- [x] Spot-check extracted CMG doses against known correct values
- [x] LLM provider tests (Anthropic, Google, Z.ai)
- [x] Medication, search, guidelines router tests
- [x] Review all `[REVIEW_REQUIRED]` flags from notability pipeline

---

## Known Gaps

- [x] Library page `New Documentation` control is not connected to any action
- [x] Feedback page `Request Peer Review` action is label-only and currently just navigates to `/quiz`
- [x] Guideline scope picker state is not connected to quiz generation
- [x] Guideline detail panel does not render `dose_lookup` or `flowchart` data returned by the backend
- [x] Settings UI does not expose CMG refresh controls despite backend support
- [ ] Weight-band dose tables not extracted from Critical Care Reference Cards
- [ ] Vision LLM handling for image-based flowcharts
- [ ] Flowchart validation against originals
- [ ] SVG flowchart extraction module is still mock logic
- [ ] Periodic CMG re-scraping scheduling (currently manual only)
- [ ] Root-level exploratory artefacts remain in repo (`capture_assets.py`, `test_ast.py`, `test_crawl.py`, `test_dom.py`, `test_modals.py`, `test_navigation.py`, `modals_output.txt`)

---

## Future Considerations (Not V1)

- [ ] Google Docs auto-import integration
- [ ] Mobile/tablet companion app
- [ ] Spaced repetition scheduling (SM-2 or similar)
- [ ] Multi-user support
- [ ] Export quiz history / study analytics
- [ ] Periodic CMG re-scraping for updates
- [ ] Audio recording playback from original Notability notes
