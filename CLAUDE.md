# Clinical Recall Assistant — Development Guide

## Project Overview

A desktop study tool for an ACT Ambulance Service (ACTAS) paramedic. The app quizzes the user on clinical knowledge drawn from two authoritative source pools:

1. **ACTAS Clinical Management Guidelines (CMGs)** — scraped from `https://cmg.ambulance.act.gov.au`
2. **Personal study notes and reference documents** — located in `docs/`

The app exposes an active-recall quiz interface through a local GUI, with AI-powered feedback grounded in source material. The design language follows "The Archival Protocol" — an editorial, clinical aesthetic defined in the Stitch design prototype.

---

## Development Workflow

All project-building work (coding, pipelines, scaffolding, debugging) is done via **Claude Code** using the developer's subscription. Do not call the Anthropic API or any other LLM API to assist in building the project — use Claude Code subagents and tools instead.

API keys are **only consumed at app runtime** by the end-user-facing quiz and pipeline features.

### Standalone Packaging Record

`Guides/standalone-packaging-macos-windows.md` is the living source of truth for the macOS and Windows standalone app effort.

- Update it whenever packaging architecture, runtime paths, bundled assets, signing, release steps, platform constraints, or packaging decisions change.
- Update it whenever a packaging attempt uncovers a failure mode, workaround, or platform-specific lesson worth preserving.
- Treat `docs/superpowers/plans/2026-04-04-standalone-packaging-macos-windows.md` as the original snapshot plan, not the ongoing tracker.

### Fresh Clone Setup

Before running the app end-to-end, create the local runtime config:

```bash
cp config/settings.example.json config/settings.json
```

`config/settings.json` is gitignored and is where local API keys, active provider selection, and quiz/cleaning model choices are stored. The backend now falls back to `config/settings.example.json` when `settings.json` is missing, which keeps tests and basic startup paths working in a fresh clone, but the copied file is still required for real local configuration changes to persist.

---

## Source Hierarchy (Strict)

When sources conflict, resolve using this order. Never break this unless the user has flagged a specific `InfoERROR`.

| Priority | Source | Location |
|----------|--------|----------|
| 1 | ACTAS CMGs | Scraped from web / `data/cmgs/` once processed |
| 2 | REF docs | `docs/REFdocs/` (2 files — ACTAS policies, CMG reference tables) |
| 3 | CPD docs | `docs/CPDdocs/` (9 files — clinical study notes, ECGs, assessments) |
| 4 | Notability Notes | `docs/notabilityNotes/` (handwritten OCR, may contain errors) |

If no source exists for a piece of information, **do not fabricate it**. Say you don't have the information.

Maintain an `InfoERRORS.md` list of any errors flagged by the user.

---

## Language and Spelling Rules

1. **Australian English** spelling, terminology, and acronyms throughout (colour, haemorrhage, organisation, etc.)
2. **Australian medical terminology** — use ACTAS-specific terms (e.g. "ambulance paramedic" not "EMT", "adrenaline" not "epinephrine" in clinical context)
3. **Tone:** Straightforward, concise, clear. The app should feel like an expert helping the user study — not a chatbot being their best mate. Avoid excessive personality.
4. See `acronyms.md` for the canonical acronym list. Add new acronyms as they are encountered.

---

## Directory Structure

```
StudyBot/
├── CLAUDE.md                          # This file
├── TODO.md                            # Development progress tracker
├── brief.md                           # Product vision and screen requirements
├── generalRules.md                    # Source hierarchy + language rules
├── acronyms.md                        # Canonical acronym list
├── InfoERRORS.md                      # User-flagged factual errors
│
├── Guides/                            # Agent and pipeline reference docs
│   ├── AI_Agent_Guideline_ACTAS_CMG_Scraping_Framework.md
│   ├── NOTABILITY_FORMAT_GUIDE.md
│   ├── PIPELINE_AGENT_GUIDE.md
│   └── standalone-packaging-macos-windows.md
│
├── docs/                              # Source documents (DO NOT modify originals)
│   ├── REFdocs/                       # Tier 2: Reference documents (2 .md files)
│   │   ├── ACTAS Policies and procedures.md
│   │   └── Reference Info ACTAS CMGs.md
│   ├── CPDdocs/                       # Tier 3: CPD/study documents (9 .md files)
│   │   ├── ECGs.md, Febrile seizures.md, Finals Study.md, ...
│   │   └── CAA306 assessment files, Neurological Assessment.md, etc.
│   └── notabilityNotes/               # Tier 4: Handwritten notes
│       ├── noteDocs/                  # Raw .note files from Notability (~476 files)
│       │   └── drive-download-.../    # Organised by subject folder
│       └── mdDocs/                    # Output dir for converted markdown (empty)
│
├── stitchDesign/                      # UI design prototype
│   ├── product_requirements_document.md   # (Ignore — placeholder, not project-specific)
│   └── stitch_remix_of_studybot/
│       ├── refined_clinical_dashboard/    # Dashboard / home screen
│       ├── active_recall_quiz_v6.1/       # Quiz screen
│       ├── feedback_evaluation_cleaned/   # Feedback & citation panel
│       ├── library_pipeline_v6.1/         # Library / source pipeline view
│       └── clinical_archive/              # DESIGN.md — full design system spec
│
├── src/                               # Application source code
│   ├── electron/                      # Electron main + preload process
│   ├── python/                        # FastAPI backend (pipeline, quiz, llm stubs)
│   │   ├── main.py                    # FastAPI app on :7777
│   │   ├── pipeline/                  # Data ingestion pipeline
│   │   │   ├── extractor.py           # .note → raw text extraction
│   │   │   ├── clinical_dictionary.py # Category mappings + clinical terms
│   │   │   ├── structurer.py          # YAML front matter validation
│   │   │   ├── chunker.py             # Text splitting + ChromaDB ingestion
│   │   │   ├── run.py                 # CLI entrypoint (extract, ingest, status)
│   │   │   ├── cleaning_prompt.md     # Claude Code OCR cleaning prompt
│   │   │   └── cmg/                   # ACTAS CMG extraction pipeline
│   │   ├── quiz/                      # Quiz agent (retriever, agent, tracker, router)
│   │   ├── medication/                # Medication doses API (reads structured CMG med files)
│   │   ├── search/                    # Vector search API (ChromaDB-backed)
│   │   ├── settings/                  # Settings persistence API
│   │   ├── guidelines/                # Clinical guidelines browser API (reads structured CMG/med/CSM JSON)
│   │   └── llm/                       # Provider abstraction (multi-provider)
│   │       ├── models.py              # Model registry (.env backed)
│   │       ├── factory.py             # Provider factory
│   │       └── ...                    # Provider implementations
│   └── renderer/                      # React renderer (TypeScript + Tailwind)
│       ├── App.tsx                    # Root: ThemeProvider + BrowserRouter + AppShell
│       ├── main.tsx                   # React entry point
│       ├── components/                # Reusable UI primitives
│       │   ├── AppShell.tsx           # Layout wrapper (sidebar + search + routes)
│       │   ├── Sidebar.tsx            # Persistent left nav with dark mode toggle
│       │   ├── SearchBar.tsx          # Universal search input
│       │   ├── Button.tsx             # 3-variant button (primary/secondary/tertiary)
│       │   ├── Input.tsx              # "Field Note" style input (bottom-border)
│       │   ├── Card.tsx               # Document-stack card with hover lift
│       │   ├── Tag.tsx                # Metadata chip
│       │   └── MasteryIndicator.tsx   # Progress bar + status dot
│       ├── pages/                     # Route-level views
│       │   ├── Dashboard.tsx          # Knowledge heatmap + metrics + recent entries
│       │   ├── Quiz.tsx               # Active recall protocol (random, gap-driven, topic modes)
│       │   ├── Feedback.tsx           # Split-view analysis
│       │   ├── Library.tsx            # Source pipeline view
│       │   ├── Medication.tsx         # Medication reference (typed MedicationDose)
│       │   ├── Guidelines.tsx         # Clinical guidelines browser (card grid + side panel + quiz launcher)
│       │   └── Settings.tsx           # Curator settings (API keys, models, data management)
│       ├── hooks/                     # React hooks
│       │   ├── useTheme.tsx           # ThemeProvider context + dark mode toggle
│       │   ├── useApi.ts              # Generic fetch hook with loading/error states
│       │   ├── useQuizSession.ts      # Quiz session state machine (start, answer, evaluate)
│       │   ├── useMastery.ts          # Mastery + streak data from backend
│       │   └── useHistory.ts          # Quiz history from backend
│       ├── types/
│       │   └── api.ts                 # Shared TypeScript interfaces (MedicationDose, SearchResult, etc.)
│       └── styles/
│           └── global.css             # Tailwind layers + CSS custom properties (light/dark)
├── data/                              # Processed data stores
│   ├── cmgs/                          # Extracted CMG JSON/markdown
│   ├── notes_md/                      # Cleaned notability markdown
│   └── chroma_db/                     # Vector store
├── tests/                             # Test suites
│   ├── python/                        # pytest tests for FastAPI backend
│   ├── pipeline/                      # pytest tests for data pipeline
│   └── renderer/                      # vitest + @testing-library/react tests
├── config/                            # App configuration
│   ├── settings.example.json          # Committed reference config
│   └── settings.json                  # User config (gitignored)
├── .env.example                       # Model name template
└── .env                               # Local model names (gitignored)
```

---

## Broad Study Categories

Non-exhaustive; a single piece of information may span multiple categories.

- Clinical Guidelines
- Medication Guidelines
- Operational Guidelines
- Clinical Skills
- Pathophysiology
- Pharmacology
- ECGs

---

## Data Pipeline Architecture

The app requires two data ingestion pipelines that produce a unified vector store.

### Pipeline 1: ACTAS CMG Extraction

**Reference:** `Guides/AI_Agent_Guideline_ACTAS_CMG_Scraping_Framework.md`

- **Source:** `https://cmg.ambulance.act.gov.au` (Ionic/Angular SPA)
- **Strategy:** Extract raw JSON from the ~10MB main JS bundle, not rendered HTML
- **Key finding:** Medicine "calculators" are pre-computed database lookup tables (24 weight bands x medicines x indications), NOT formula-based calculators
- **Medicines:** 35 ACTAS medicines extracted across 538 dose groups. Selector-based extraction catches medicines whose `.EFF()` texts lack keywords (Fentanyl, Calcium Chloride, Ipratropium, Salbutamol, Topical Anaesthetic)
- **Selector extraction:** Scans ALL JS bundles (not just `7_common`) — some CSMs (e.g. Skills Matrix) live in separate chunks
- **Medicines:** 35 ACTAS medicines extracted across 538 dose groups (35 from `.EFF()` text + selector-based extraction for 5 medicines whose texts lack keywords)
- **Selector extraction:** Scans ALL JS bundles (not just `7_common`) — some CSMs (e.g., Skills Matrix) live in separate chunks
- **Output schema:** JSON conforming to the CMG Guideline Schema (see guide Section 4.1)
- **Flowcharts:** Store as Mermaid.js; use vision LLM for image-based flowcharts
- **Tools:** Playwright (SPA rendering), BeautifulSoup4, Pandas

### Pipeline 2: Notability Notes Extraction

**Reference:** `Guides/NOTABILITY_FORMAT_GUIDE.md` and `Guides/PIPELINE_AGENT_GUIDE.md`

- **Source:** 476 `.note` files (ZIP archives containing binary plists)
- **Primary text source:** `HandwritingIndex/index.plist` (OCR text, 1-indexed pages)
- **Metadata:** `metadata.plist` (NSKeyedArchiver format, Apple epoch +978307200)
- **Stages:**
  1. **Extract** — unzip, parse plists for OCR text + metadata
  2. **Clean** — LLM-powered OCR error correction using clinical dictionary (use strong model for drug names)
  3. **Structure** — wrap in markdown with YAML front matter
  4. **Chunk** — RecursiveCharacterTextSplitter (800 chars, 100 overlap)
  5. **Ingest** — ChromaDB with `PersistentClient`, collection `"paramedic_notes"`
- **Low-confidence flag:** `[REVIEW_REQUIRED: <text>]` for uncertain OCR corrections
- **Subject mapping:** Notability folder names map to clinical categories via `SUBJECT_TO_CATEGORY` dict

### Pipeline 3: REF and CPD Docs

- **Sources:**
  - `docs/REFdocs/` — 2 high-authority reference files (ACTAS policies, CMG reference tables)
  - `docs/CPDdocs/` — 9 clinical study/CPD files (ECGs, assessments, clinical topics)
- **Processing:** Already in Markdown — chunk and ingest directly (no OCR cleaning needed)
- **Metadata:** Each chunk must carry `source_type: "ref_doc"` or `"cpd_doc"` to preserve the source hierarchy distinction

### Unified Vector Store

All three pipelines feed into a single ChromaDB instance. Each chunk carries metadata:
- `source_type`: `"cmg"` | `"ref_doc"` | `"cpd_doc"` | `"notability_note"`
- `source_file`: original filename
- `category`: clinical category
- `last_modified`: ISO date
- `has_review_flag`: boolean (notability notes only)
- `cmg_number`: CMG reference number (CMGs only)

---

## Quiz Agent Architecture

The quiz agent is a lightweight LLM-powered component that:

1. **Generates questions** from the vector store, targeted by category or topic
2. **Evaluates answers** by retrieving relevant chunks and comparing user response
3. **Provides feedback** with exact source citations (e.g. `Ref: ACTAS CMG 14.1`)
4. **Tracks mastery** per topic/category for the knowledge heatmap

### Model Selection

All LLM calls in the app route through a provider abstraction layer (`src/python/llm/`). 

- **Quiz & Cleaning:** The user selects any model from any provider in Settings; results are routed to the appropriate provider automatically.
- **Data Pipeline:** Uses the strongest available model for OCR cleaning (defaulting to the specified cleaning model).
- **Persistence:** Model IDs are stored in `.env`, while API keys and active selections are in `config/settings.json`.

**Supported providers:**

| Provider | Models | Use case |
|----------|--------|----------|
| Anthropic | `claude-haiku-4-5-20251001` (low), `claude-sonnet-4.6` (medium), `claude-opus-4.6` (high) | Default; highest quality feedback |
| Google | `gemini-3.1-flash-lite-preview` (low), `gemini-3-flash-preview` (medium), `gemini-2.5-pro` (high) | Fast / alternative |
| Z.ai (Zhipu) | `glm-4.7-flash` (low), `glm-4.7` (medium), `glm-5` (high) | Cost-effective alternative |

**Task defaults (overridable in settings):**

- **Quiz generation + evaluation:** Fast model recommended (e.g. Haiku, GLM-4-Flash, Gemini Flash) — latency-sensitive
- **OCR cleaning (pipeline):** Strongest available model — drug name errors are high-stakes

The provider abstraction must expose a single `complete(messages, model_config) -> str` interface so quiz and pipeline code is provider-agnostic.

### Quiz Modes

- **Full quiz:** Questions from all categories
- **Targeted quiz:** Questions from a specific category or topic
- **Blacklist support:** User can exclude specific topics/information from quizzes (persisted, editable)
- **Self-grading option:** "Reveal Reference" button for users who prefer not to type answers

### Feedback Requirements

- Always cite the source with a reference (e.g. `Ref: ACTAS CMG 14.1`, `Ref: Personal Notes — Pharmacology`)
- Show the exact relevant text snippet from the source ("From the Source")
- Identify specific errors in the user's answer with corrections
- Tone: supportive expert, not overly casual (see Language rules above)

---

## UI / Design System

**Reference:** `stitchDesign/stitch_remix_of_studybot/clinical_archive/DESIGN.md`

The design system is called **"The Archival Protocol"** — a high-end editorial archive aesthetic.

### Key Design Decisions

- **Fonts:** Newsreader (serif, for headlines/display) + Space Grotesk (sans-serif, for body/labels) + IBM Plex Mono (monospace, for data)
- **Primary colour:** `#2D5A54` (dark archival teal/ink) — high-authority actions
- **Highlighter accent:** `#DAE058` (yellow-green) — active states, critical highlights
- **Surface base:** `#FBF9F3` (warm off-white, parchment)
- **The "No-Line" Rule:** No 1px borders. Use background colour shifts, whitespace, and ghost borders (outline-variant at max 15% opacity)
- **Elevation:** No heavy drop shadows. Use surface-container tier shifts for depth. Glassmorphism for nav (80% opacity + backdrop-blur)
- **Cards:** No divider lines between list items. Use spacing and background shifts.
- **Medical status colours:** Success Green, Caution Yellow, Critical Red for mastery levels

### Screen Map

| Screen | Design Reference | Purpose |
|--------|-----------------|---------|
| Command Dashboard | `refined_clinical_dashboard/` | Knowledge heatmap, metrics, start session |
| Active Recall Quiz | `active_recall_quiz_v6.1/` | Question display, answer input, timer |
| Feedback Panel | `feedback_evaluation_cleaned/` | Split view: user answer vs AI critique + source |
| Source Pipeline | `library_pipeline_v6.1/` | Document repository, sync status, cleaning feed |
| Clinical Guidelines | — | Browse CMGs, medication monographs, clinical skills; quiz launcher |

### Navigation

- Persistent left sidebar with iconic navigation (Field Archive, Clinical Protocols, Research Notes, Medication Ledger, Curator Settings)
- Universal search bar at top
- User should reach a quiz in under 2 clicks from launch

---

## Technology Stack (Confirmed)

| Concern | Choice | Notes |
|---------|--------|-------|
| GUI Framework | **Electron 32** + **React 19** | Desktop app, main process spawns Python backend |
| Bundler | **Vite 6** | Dev server on :5173, builds to `dist/` |
| Styling | **Tailwind CSS 3** | Archival Protocol design tokens via CSS custom properties, darkMode: "class" |
| Routing | **React Router v7** | Client-side navigation with nested routes |
| Language | **TypeScript 5** (renderer), **Python 3.10+** (backend) | |
| Backend | **FastAPI** on `127.0.0.1:7777` | CORS configured for dev server origins |
| Vector DB | **ChromaDB** | Local persistent client, collection per source type |
| LLM Integration | Multi-provider abstraction layer | Anthropic (Claude), Google (Gemini), Z.ai (GLM) — user selects per-task in settings |
| Data Pipeline | Python scripts | Playwright for SPA scraping, langchain for chunking |
| Testing | **vitest** + **@testing-library/react** + **@testing-library/user-event** (renderer), **pytest** + **httpx** (Python) | |
| State Management | SQLite for quiz history + user prefs | Lightweight, local, no server needed |

---

## Development Conventions

### Code Style
- Python: follow PEP 8, type hints on public functions
- TypeScript/React: functional components, named exports
- Use Australian English in all user-facing strings and comments

### File Naming
- Python: `snake_case.py`
- TypeScript/React: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Data files: descriptive `kebab-case`

### Git
- Commit messages: imperative mood, concise
- Branch naming: `feature/`, `fix/`, `pipeline/`, `ui/`

### Source Documents
- **NEVER modify original files** in `docs/notabilityNotes/noteDocs/` or `docs/personalDocs/`
- Processed/cleaned outputs go to separate output directories
- Original `.note` files are the archival source of truth for personal notes

### Error Handling
- Pipeline: log errors per-file and continue processing (don't fail the whole batch)
- Quiz agent: if retrieval fails, tell the user honestly rather than fabricating
- OCR cleaning: flag uncertain corrections with `[REVIEW_REQUIRED: ...]`

---

## Key Gotchas

1. **The PRD in `stitchDesign/product_requirements_document.md` is a placeholder** — it describes a generic "Acme Project Manager", not this project. Ignore it entirely.
2. **Notability exports have duplicate folder trees** — there are two copies of `Paramedics 2021 sem 1` (one with trailing space, one without). The pipeline must handle this gracefully (deduplicate or process both).
3. **`.note` files are ZIP archives** — rename to `.zip` or use `zipfile` directly. The `.rtf` companion files are often empty shells; the `.note` is authoritative.
4. **NSDate epoch** uses Jan 1 2001 as base. Add `978307200` to convert to Unix timestamp.
5. **Medicine dose data is pre-computed lookups**, not formulas. Extract the complete table from the JS bundle.
6. **Selector extraction scans all JS bundles** — some components (e.g., Skills Matrix) are in separate chunks, not `7_common`.
7. **OCR quality varies significantly** — expect character substitutions (`8` for `g`, `1` for `l`, `rn` for `m`). The cleaning agent must handle these without altering correct content.
8. **The `mdDocs/` directory is currently empty** — this is the intended output location for converted notability notes.
9. **Route matching needs number normalization** — "12 Lead ECG" maps to selector `twelve-lead-ecg-monitoring`, not `12-lead-ecg-monitoring`.
10. **Phantom medicine keywords removed** — entinox, tetracaine, tranexamic acid, clopidogrel, ticagrelor, diazepam, furosemide, rocuronium, promethazine, sodium chloride are NOT in the ACTAS formulary and have been removed from `_MEDICINE_KEYWORDS`.
