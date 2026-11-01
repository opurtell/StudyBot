# Clinical Recall Assistant — Development Guide

## Project Overview

A desktop study tool for Australian ambulance paramedics, originally built for an ACT Ambulance Service (ACTAS) paramedic. The app quizzes the user on clinical knowledge drawn from two authoritative source pools:

1. **Service clinical guidelines** — one set per supported ambulance service (see Multi-Service Architecture below):
   - **ACTAS Clinical Management Guidelines (CMGs)** — scraped from `https://cmg.ambulance.act.gov.au`
   - **Ambulance Tasmania (AT) Clinical Practice Guidelines (CPGs)** — scraped from `https://cpg.ambulance.tas.gov.au`
2. **Personal study notes and reference documents** — located in `docs/`

The app exposes an active-recall quiz interface through a local GUI, with AI-powered feedback grounded in source material. The design language follows "The Archival Protocol" — an editorial, clinical aesthetic defined in the Stitch design prototype.

---

## Multi-Service Architecture

The app supports more than one ambulance service. The user picks the active service in Settings; guidelines, medications, quiz retrieval and citations all follow it.

- **Registry:** `src/python/services/registry.py` — one `Service(...)` entry per service (`id`, display name, source URL, qualification model, adapter module, section aliases)
- **Supported services:**

| `id` | Service | Guideline source | Adapter | Qualifications |
|------|---------|------------------|---------|----------------|
| `actas` | ACT Ambulance Service | `cmg.ambulance.act.gov.au` | `src/python/pipeline/actas/` | AP, ICP |
| `at` | Ambulance Tasmania | `cpg.ambulance.tas.gov.au` | `src/python/pipeline/at/` | VAO, PARAMEDIC + ICP / PACER / CP_ECP endorsements |

- **Active service:** stored as `active_service` in `config/settings.json`; read via `services/active.py`. Defaults to the first registry entry (`actas`)
- **ChromaDB collections:** `guidelines_<id>` for guidelines, `personal_<id>` for personal docs (legacy `cmg_guidelines` is migrated to `guidelines_actas` on startup)
- **Data paths:** `data/services/<id>/structured/` and `data/services/<id>/medications/` (bundled), with user-local equivalents under `USER_DATA_DIR/services/<id>/`
- **Service switching:** retriever/search singletons are reset when `active_service` changes — new code that caches per-service state must do the same
- **Frontend:** `ServiceProvider.tsx` exposes the active service to the renderer
- **Citations:** prefix with the service's `short_name` (`ACTAS`, `AT`), as `quiz/agent.py` does — never hardcode "ACTAS"
- **Adding a service:** follow `Guides/adding-a-service.md`; scope-of-practice docs live in `Guides/scope-of-practice-<id>.md`

---

## Web Port (`web/`)

A Cloudflare-native rewrite for a hosted multi-user version lives in `web/` (TypeScript Worker + React, D1). It has its
own `package.json`, tests and CI (`.github/workflows/web-*.yml`); the desktop app and its checks ignore it. Read
`web/README.md` and `docs/web-port-plan.md` before working there. The web corpus is ACTAS guideline content only.

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
| 1 | Active service's guidelines (ACTAS CMGs / AT CPGs) | Scraped from web / `data/services/<id>/structured/` once processed |
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
├── scripts/                           # Build and data management scripts
│   ├── package-backend.sh             # macOS backend staging (python-build-standalone, Python 3.12.13)
│   ├── package-backend.ps1            # Windows backend staging
│   ├── verify-backend-payload.sh      # macOS payload structural validation
│   ├── verify-backend-payload.ps1     # Windows payload structural validation
│   └── upload-personal-data.sh        # Upload ChromaDB + CMG data to GitHub Release (personal build)
│
├── src/                               # Application source code
│   ├── electron/                      # Electron main + preload process
│   ├── python/                        # FastAPI backend
│   │   ├── main.py                    # FastAPI app on :7777 (lifespan: auto-seed + warmup thread)
│   │   ├── seed.py                    # Auto-seed ChromaDB on startup (bundled copy or chunker fallback)
│   │   ├── paths.py                   # All runtime path constants + resolve_service_structured_dir()
│   │   ├── services/                  # Service registry, active service, qualifications API
│   │   ├── pipeline/                  # Data ingestion pipeline
│   │   │   ├── extractor.py           # .note → raw text extraction
│   │   │   ├── clinical_dictionary.py # Category mappings + clinical terms
│   │   │   ├── structurer.py          # YAML front matter validation
│   │   │   ├── chunker.py             # Text splitting + ChromaDB ingestion
│   │   │   ├── run.py                 # CLI entrypoint (extract, ingest, status)
│   │   │   ├── cleaning_prompt.md     # Claude Code OCR cleaning prompt
│   │   │   ├── actas/                 # ACTAS CMG extraction pipeline (reference adapter)
│   │   │   ├── at/                    # Ambulance Tasmania CPG extraction pipeline
│   │   │   └── personal_docs/         # REFdocs/CPDdocs chunk + ingest pipeline
│   │   ├── quiz/                      # Quiz agent (retriever, agent, tracker, router, store)
│   │   │   └── store.py               # SQLite-backed question/session store (thread-safe, clears stale on startup)
│   │   ├── medication/                # Medication doses API (reads structured CMG med files)
│   │   ├── search/                    # Vector search API (ChromaDB-backed)
│   │   ├── settings/                  # Settings persistence API
│   │   ├── guidelines/                # Clinical guidelines browser API (CMG/med/CSM JSON)
│   │   ├── sources/                   # Source repository status API (/sources)
│   │   ├── upload/                    # User document upload API (/upload)
│   │   │   ├── router.py              # POST /upload, GET /upload/formats
│   │   │   └── extractor.py           # PDF/TXT → Markdown conversion (pypdf)
│   │   └── llm/                       # Provider abstraction (multi-provider)
│   │       ├── models.py              # Model registry (.env backed)
│   │       ├── factory.py             # Provider factory
│   │       ├── lmstudio_provider.py   # Local models via LM Studio (OpenAI-compatible)
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
│       │   ├── MasteryIndicator.tsx   # Progress bar + status dot
│       │   ├── Modal.tsx              # Reusable overlay modal (backdrop, escape/click dismiss)
│       │   └── UploadDialog.tsx       # File picker + drag-and-drop upload UI
│       ├── pages/                     # Route-level views
│       │   ├── Dashboard.tsx          # Knowledge heatmap + metrics + recent entries
│       │   ├── Quiz.tsx               # Active recall protocol (random, gap-driven, topic modes)
│       │   ├── Feedback.tsx           # Split-view analysis
│       │   ├── Library.tsx            # Source pipeline view (wired to /sources + /upload)
│       │   ├── Medication.tsx         # Medication reference (typed MedicationDose)
│       │   ├── Guidelines.tsx         # Clinical guidelines browser (card grid + side panel + quiz launcher)
│       │   └── Settings.tsx           # Curator settings (API keys, models, indexed data management)
│       ├── hooks/                     # React hooks
│       │   ├── useTheme.tsx           # ThemeProvider context + dark mode toggle
│       │   ├── useApi.ts              # Generic fetch hook with loading/error states
│       │   ├── useQuizSession.ts      # Quiz session state machine (start, answer, evaluate)
│       │   ├── useMastery.ts          # Mastery + streak data from backend
│       │   └── useHistory.ts          # Quiz history from backend
│       ├── providers/                 # React context providers
│       │   ├── SettingsProvider.tsx   # Global settings + CMG manifest context
│       │   └── ResourceCacheProvider.tsx  # Stale-while-refresh cache for read-mostly data
│       ├── types/
│       │   └── api.ts                 # Shared TypeScript interfaces (MedicationDose, SearchResult, UploadResponse, CmgManifest, etc.)
│       └── styles/
│           └── global.css             # Tailwind layers + CSS custom properties (light/dark)
├── data/                              # Processed data stores (gitignored, user-local)
│   ├── services/<id>/structured/      # Per-service guideline JSON; ACTAS skills in csm/, monographs in med/ (bundled via electron-builder.yml)
│   ├── services/<id>/medications/     # Per-service medication data
│   ├── notes_md/raw/                  # Extracted uncleaned notability markdown
│   ├── notes_md/cleaned/              # LLM-cleaned notability markdown (380 files)
│   ├── personal_docs/structured/      # Structured REFdocs + CPDdocs (11 files)
│   ├── uploads/                       # User-uploaded documents + structured output
│   └── chroma_db/                     # Vector store (user-data copy, seeded from bundled on first launch)
├── build/resources/data/services/     # Per-service bundled data + pre-built ChromaDB for packaged app
├── tests/                             # Test suites
│   ├── python/                        # pytest tests for FastAPI backend
│   ├── quiz/                          # pytest tests for quiz agent
│   ├── pipeline/                      # pytest tests for data pipeline
│   └── renderer/                      # vitest + @testing-library/react tests
├── config/                            # App configuration
│   ├── settings.example.json          # Committed reference config
│   └── settings.json                  # User config (gitignored)
├── electron-builder.yml               # Release build (bundles CMG structured data + pre-built ChromaDB)
├── electron-builder.personal.yml      # Personal build (downloads ChromaDB from GitHub Release)
├── KNOWN_TEST_FAILURES.md             # Pre-existing test failures (17 frontend, 4 Python) — do not treat as regressions
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

The app has three data ingestion pipelines feeding a unified ChromaDB instance, plus a user document upload path.

### Pipeline 1: Service Guideline Extraction

One adapter per service under `src/python/pipeline/<id>/`, following the contract in `Guides/adding-a-service.md`. ACTAS is the reference implementation; AT findings are in `Guides/at-cpg-extraction-findings.md`. The ACTAS specifics are below.

#### ACTAS CMGs

**Reference:** `Guides/AI_Agent_Guideline_ACTAS_CMG_Scraping_Framework.md`

- **Source:** `https://cmg.ambulance.act.gov.au` (Ionic/Angular SPA)
- **Strategy:** Extract raw JSON from the ~10MB main JS bundle, not rendered HTML
- **Key finding:** Medicine "calculators" are pre-computed database lookup tables (24 weight bands x medicines x indications), NOT formula-based calculators
- **Medicines:** 35 ACTAS medicines extracted across 538 dose groups (35 from `.EFF()` text + selector-based extraction for 5 medicines whose texts lack keywords: Fentanyl, Calcium Chloride, Ipratropium, Salbutamol, Topical Anaesthetic)
- **Selector extraction:** Scans ALL JS bundles (not just `7_common`) — some CSMs (e.g., Skills Matrix) live in separate chunks
- **Output schema:** JSON conforming to the CMG Guideline Schema (see guide Section 4.1)
- **Flowcharts:** Store as Mermaid.js; use vision LLM for image-based flowcharts
- **Tools:** Playwright (SPA rendering), BeautifulSoup4, Pandas
- **Structured data path:** `data/services/actas/structured/` — resolved at runtime via `resolve_service_structured_dir(service_id)`, which prefers user-fetched data over bundled app data

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

**Module:** `src/python/pipeline/personal_docs/`

- **Sources:**
  - `docs/REFdocs/` — 2 high-authority reference files (ACTAS policies, CMG reference tables)
  - `docs/CPDdocs/` — 9 clinical study/CPD files (ECGs, assessments, clinical topics)
- **Structured output:** `data/personal_docs/structured/` (11 files)
- **Processing:** Already in Markdown — chunk and ingest directly (no OCR cleaning needed)
- **Metadata:** Each chunk must carry `source_type: "ref_doc"` or `"cpd_doc"` to preserve the source hierarchy distinction

### Pipeline 4: User Document Uploads

**Module:** `src/python/upload/`

- **Trigger:** User uploads via Library page "+New Documentation" button → `POST /upload`
- **Accepted formats:** Markdown (`.md`), PDF (`.pdf`), plain text (`.txt`); max 20 MB
- **PDF extraction:** `pypdf` — text only (no image OCR)
- **Output:** Saved to `data/uploads/`, structured to `data/uploads/structured/`, chunked and ingested with `source_type: "upload"`
- **Frontend:** `Modal.tsx` + `UploadDialog.tsx` components; file picker with drag-and-drop and progress feedback

### Unified Vector Store

All pipelines feed into a single ChromaDB instance (`data/chroma_db/`), split into per-service collections (`guidelines_<id>`, `personal_<id>`). Each chunk carries metadata:
- `source_type`: `"cmg"` | `"ref_doc"` | `"cpd_doc"` | `"notability_note"` | `"upload"`
- `source_file`: original filename
- `category`: clinical category
- `last_modified`: ISO date
- `has_review_flag`: boolean (notability notes only)
- `cmg_number`: CMG reference number (CMGs only)

### ChromaDB First-Launch Seeding

`seed.py` runs in the FastAPI lifespan on every startup:
1. For each registered service, skip if `guidelines_<id>` already has data (migrating legacy `cmg_guidelines` if found)
2. Otherwise copy from bundled ChromaDB (`APP_ROOT/data/chroma_db/` or `APP_ROOT/data/services/<id>/chroma/`) — packaged app fast path
3. Otherwise run the service adapter's chunker as fallback auto-seed (dev environment path)
4. Personal notes / REFdocs / CPDdocs are not auto-seeded — user must run the pipeline or use the "Re-run Pipeline" button in Settings

---

## Quiz Agent Architecture

The quiz agent is a lightweight LLM-powered component that:

1. **Generates questions** from the vector store, targeted by category or topic
2. **Evaluates answers** by retrieving relevant chunks and comparing user response
3. **Provides feedback** with exact source citations (e.g. `Ref: ACTAS CMG 14.1`)
4. **Tracks mastery** per topic/category for the knowledge heatmap

**Session and question state** is persisted in SQLite (`quiz/store.py` → `QuizStore` class, stored in `data/mastery.db`). Stale data is cleared on backend startup. Public module-level API is unchanged so `router.py` is unaffected by the store implementation.

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
| OpenAI | `gpt-5.4-nano` (low), `gpt-5.4-mini` (medium), `gpt-5.4` (high) | Alternative |
| LM Studio (local) | `openai/gpt-oss-20b` (low), `qwen/qwen3.6-35b-a3b` (medium), `qwen/qwen3.8-27b` (high) | Offline / no API key / no data leaves the device |

**LM Studio (local models):**

- Runs against LM Studio's OpenAI-compatible server, default `http://127.0.0.1:1234/v1`
  (configurable in Settings > Local Model). No API key is required.
- The server must be running (LM Studio > Developer > Start Server) before the app can
  use a local model. Requests fail with a plain-language "start the server" message otherwise.
- `GET /settings/lmstudio/status` reports reachability and the chat-capable models the
  server can serve; Settings uses it for the "Detect Models" button. Embedding models are
  filtered out. Model discovery prefers LM Studio's native `/api/v0/models` (which reports
  model type and load state) and falls back to the OpenAI-compatible `/v1/models`.
- Local model IDs must match what LM Studio reports exactly — they are namespaced
  (`qwen/qwen3.8-27b`), not bare names.
- Vision is not offered for local models. Some LM Studio models are VLMs, but `vision.py`
  has no implementation for them, so `lmstudio` is deliberately absent from
  `VISION_CAPABLE_PROVIDERS`.
- Local generation uses a 600 s client timeout — a cold model load plus a long answer
  vastly exceeds hosted-provider latencies.
- **Reasoning models are handled explicitly.** LM Studio returns chain of thought either in
  a separate `reasoning_content` field or inline in `<think>` tags. The provider strips
  inline blocks and raises a clear error when a model burns its whole token budget thinking
  without answering. The local token cap is 4096 (not 1024) to leave room for reasoning.
- **The provider sends `reasoning_effort: "none"` by default** (`DEFAULT_REASONING_EFFORT`).
  Every LM Studio model tested accepted it, and it is the single biggest latency win
  available: gemma-4-e4b went from 38 s to ~8 s per evaluation and qwen3.6-35b-a3b from
  39 s to ~11 s, with no loss of marking accuracy. The app never displays chain of thought,
  so paying for it buys nothing. A server that rejects the parameter is detected once and
  the provider stops sending it. Set `reasoning_effort` in the `lmstudio` provider config to
  `"low"`/`"medium"`/`"high"` to opt back in.
**Local model evaluation (M5 MacBook Air, 32 GB)**

Re-run with `scripts/bench-local-models.py` when new models appear. It scores the four
things this app actually needs, using the real `EVALUATION_SYSTEM_PROMPT` and real CMG
text: strict JSON, conservative marking, verbatim source quotes, and latency. General
leaderboards do **not** predict these — the two models that top sub-7B instruction-following
charts both failed here.

| Model | Size | Median | JSON | Grading | Fabricated | Grounded | Verdict |
|-------|------|--------|------|---------|-----------|----------|---------|
| `openai/gpt-oss-20b` | 12.1 GB | 8-14 s | 20/20 | **10/10** | **0** | 5-9/10 | **Default - the only model good at everything** |
| `medgemma-1.5-4b-it` | 3.4 GB | **3.6 s** | 17/20 | **3/10** | 2 | 7-9/10 | Rejected: collapses onto one grade (see below) |
| `google/gemma-4-e4b` | 6.9 GB | 7.9 s | 7/10 | 5/5 strict* | 0 | **2/10** | Rejected: invents source quotes, drops JSON |
| `phi-4-mini-instruct` | 2.2 GB | ~5 s | 8/10 | 4/5 strict* | **3** | 5/10 | Rejected: fabricates credit, unreliable JSON |
| `qwen/qwen3.6-35b-a3b` | 20.4 GB | ~11 s | 9/10 | 5/5 strict* | 1 | 4/10 | Usable but larger and weaker at quoting |
| `qwen/qwen3.8-27b` | 16.1 GB | ~120 s | - | - | - | - | Too slow (measured before reasoning was disabled) |
| `mlx-community/Qwen3.5-4B` | 3.1 GB | 60-80 s | - | - | - | - | Rejected: ignores `reasoning_effort`, reasons forever |

Columns: **Grading** = answers matching their known grade across all ten labelled cases;
**Fabricated** = answers credited with `correct_elements` the student never wrote;
**Grounded** = `source_quote` values found verbatim in the source.

*Screened before the graded set existed, using the weaker "did it mark flatly-wrong answers
incorrect" check. That metric flatters a model that marks everything incorrect - re-run them
with the current script for a comparable number.

Latency and **Grounded** vary run to run (gpt-oss-20b has scored 5/10, 7/10 and 9/10 on
grounding across runs). Treat single-run differences of a point or two as noise; the verdicts
above rest on the large, repeated gaps.

Three findings worth keeping:

1. **Small does not mean worse — it means worse at the *rubric*.** `medgemma-1.5-4b-it` is
   fast, small and quotes sources well, but out of the box it collapses onto a single grade
   (it marked 8 of 10 answers "partial", including two perfect ones). Obedience to the
   marking rubric, not medical knowledge, is the binding constraint for this app.
2. **Benchmark on a quiet machine.** Wall-clock latency is meaningless if the Mac sleeps or
   another inference job runs — a sleep mid-run produced apparent medians of 300 s+ and
   single calls of 2600 s+. Take the median of ≥5 warm calls, model already loaded, nothing
   else running.
3. **Validate prompt changes on held-out guidelines.** Tuning the rubric took gpt-oss-20b
   from 9/10 to a perfect 10/10 on the cases used for tuning — and to 6/8 on unseen
   guidelines, exactly matching the untouched prompt. The gain was overfitting. The prompt
   was left alone as a result.

**Both benchmarked models are offered (`llm/local_tuning.py`)**

The LM Studio tiers are speed/size, not capability:

| Tier | Model | Size | Median | Held-out grading | When to pick it |
|------|-------|------|--------|------------------|-----------------|
| low | `medgemma-1.5-4b-it` | 3.4 GB | 3.6 s | 6/8 | Fastest; fits alongside other apps |
| medium | `openai/gpt-oss-20b` | 12.1 GB | 8-14 s | 6/8 | **Default** — safest failure mode |
| high | `qwen/qwen3.6-35b-a3b` | 20.4 GB | ~11 s | not run | Largest local option |

medgemma only works with two adjustments that **must not** reach other models, so they are
keyed by model id in `llm/local_tuning.py` rather than baked into the shared prompt:

1. **A calibration supplement** appended to `EVALUATION_SYSTEM_PROMPT`. Untuned, medgemma
   marks almost everything "partial" — including perfect answers. Spelling out the rule and
   showing one worked example per grade takes it from 3/10 to 6/10 on the labelled set and
   from 3/8 to 6/8 held out.
2. **A JSON schema** via `response_format`, which removes its parse failures entirely
   (3/8 -> 0/8). `quiz/agent.py` always *offers* `EVALUATION_SCHEMA`; the provider decides
   whether to use it. Do not widen `_NEEDS_STRUCTURED_OUTPUT` without measuring —
   constrained decoding costs `gpt-oss-20b` four grading points.

Hosted providers (Anthropic, Google, Z.ai, OpenAI) accept `response_schema` and ignore it,
and never receive the supplement, so their behaviour is byte-for-byte unchanged.

**Why gpt-oss-20b is still the default.** On held-out guidelines the two models tie at 6/8,
so medgemma's 6x speed advantage is real but buys no accuracy. They fail differently:
gpt-oss-20b's errors are all "marked a correct answer partial" (the student re-reads the
source — harmless), whereas medgemma also over-credits an incomplete answer as "correct",
leaving a knowledge gap the student cannot see. For exam preparation, erring strict is the
safer failure mode.

**What did not work**, so nobody retries it: `temperature: 0` (no effect at all), moving the
rubric out of the system role into the user turn (no effect — Gemma has no native system
turn, but LM Studio's template handles it), and generic `{"type": "json_object"}` mode
(LM Studio rejects it outright with a 400; it requires a full `json_schema`).

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
| Vector DB | **ChromaDB** | Local persistent client, collections per service (`guidelines_<id>`, `personal_<id>`) |
| LLM Integration | Multi-provider abstraction layer | Anthropic (Claude), Google (Gemini), Z.ai (GLM), OpenAI (GPT) — user selects per-task in settings |
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
11. **All runtime paths go through `paths.py`** — never use bare relative `Path("data/...")` calls in backend modules. Always import from `paths`.
12. **`resolve_service_structured_dir(active_service().id)` must be used** in guidelines/medication routers — it prefers user-fetched data over bundled data. `resolve_cmg_structured_dir()` and `CMG_STRUCTURED_DIR` are deprecated ACTAS-only paths.
13. **`KNOWN_TEST_FAILURES.md`** documents 17 frontend + 4 Python pre-existing failures — do not treat as regressions. Fix them as part of dedicated test-repair work, not as part of unrelated PRs.
14. **macOS builds must run sequentially** (arm64 then x64). `build/resources/backend/` is overwritten per build — rename or move the first DMG out of `release/` before starting the next arch.
15. **Windows PYTHONPATH** requires both `backend/Lib` (stdlib) and `backend/Lib/site-packages` (pip packages). macOS uses `backend/lib` only.
16. **Nothing is ACTAS-only any more** — route service names, collection names and citation prefixes through the active `Service`, not hardcoded `"actas"` / `"ACTAS"` strings.
