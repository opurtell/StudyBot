# Clinical Recall Assistant — Agent Instructions

**CLAUDE.md is the definitive project guide.** This file (AGENTS.md) is a concise quick-reference for agents. If anything here conflicts with CLAUDE.md, **CLAUDE.md wins.**

## Project Identity

A desktop study tool for an ACT Ambulance Service (ACTAS) paramedic. The app quizzes the user on clinical knowledge drawn from ACTAS Clinical Management Guidelines (CMGs) and personal study notes. Design language: "The Archival Protocol."

## Rules of Engagement

1. **Do not call external LLM APIs** to assist in building the project. Use Claude Code subagents and tools only. API keys are consumed at app runtime by quiz/pipeline features.
2. **Source Hierarchy is strict:** CMGs > REFdocs > CPDdocs > Notability Notes. Never fabricate information. Maintain `InfoERRORS.md` for user-flagged errors.
3. **Australian English** everywhere (colour, haemorrhage, adrenaline not epinephrine, ambulance paramedic not EMT).
4. **Tone:** Straightforward, concise, clear expert. Not casual, not chatty.
5. **Never modify originals** in `docs/notabilityNotes/noteDocs/` or `docs/personalDocs/`.
6. **No comments in code** unless explicitly requested.
7. **Do not commit** unless the user explicitly asks.
8. **Packaging work must update** `Guides/standalone-packaging-macos-windows.md` whenever standalone build decisions, runtime path assumptions, bundled assets, signing steps, release workflow, or packaging lessons change.

## Fresh Clone Setup

Before running end-to-end, create the local runtime config:

```bash
cp config/settings.example.json config/settings.json
```

`config/settings.json` is gitignored — API keys, active provider, and model selections go there. The backend falls back to `settings.example.json` when `settings.json` is missing, but the copy is required for real local config changes to persist.

## Key Technical Context

| Concern | Choice |
|---------|--------|
| GUI | Electron 32 + React 19 + Vite 6 |
| Styling | Tailwind CSS 3 (Archival Protocol design tokens, darkMode: "class") |
| Backend | FastAPI on 127.0.0.1:7777 |
| Vector DB | ChromaDB (local PersistentClient) |
| LLM | Multi-provider abstraction (Anthropic, Google, Z.ai/Zhipu) |
| State | SQLite for quiz history + user prefs |
| Testing | vitest + @testing-library/react (frontend), pytest + httpx (Python) |
| Language | TypeScript 5 (renderer), Python 3.10+ (backend) |

## Code Style

- Python: PEP 8, type hints on public functions, `snake_case.py`
- TypeScript/React: functional components, named exports, `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Data files: `kebab-case`
- Git commits: imperative mood, concise
- Branch naming: `feature/`, `fix/`, `pipeline/`, `ui/`

## Error Handling

- **Pipeline:** Log errors per-file and continue processing (don't fail the whole batch).
- **Quiz agent:** If retrieval fails, tell the user honestly rather than fabricating.
- **OCR cleaning:** Flag uncertain corrections with `[REVIEW_REQUIRED: ...]`.

## Key Design Decisions (Archival Protocol)

- **Fonts:** Newsreader (serif headlines) + Space Grotesk (sans body) + IBM Plex Mono (data)
- **Primary colour:** `#2D5A54` (dark archival teal)
- **Highlight accent:** `#DAE058` (yellow-green)
- **Surface base:** `#FBF9F3` (warm parchment)
- **"No-Line" Rule:** No 1px borders. Use background colour shifts, whitespace, ghost borders (≤15% opacity).
- **Elevation:** No heavy drop shadows. Surface-container tier shifts for depth.
- **Cards:** No divider lines between list items.
- **Full spec:** `stitchDesign/stitch_remix_of_studybot/clinical_archive/DESIGN.md`

## Data Pipeline Summary

Three pipelines feed a unified ChromaDB instance. Each chunk carries `source_type`, `source_file`, `category`, and `last_modified` metadata.

| Pipeline | Source | Key Detail |
|----------|--------|------------|
| CMG Extraction | `cmg.ambulance.act.gov.au` (SPA JS bundles) | Extract raw JSON from ~10MB main bundle, not HTML. Medicine doses are pre-computed lookup tables, not formulas. |
| Notability Notes | 476 `.note` files (ZIP archives with binary plists) | OCR text from `HandwritingIndex/index.plist`. Clean with LLM + clinical dictionary. |
| REF/CPD Docs | `docs/REFdocs/` (2 files), `docs/CPDdocs/` (9 files) | Already Markdown — chunk and ingest directly. |

See CLAUDE.md for full pipeline architecture, chunking parameters, and metadata schema.

## Key Gotchas

1. `stitchDesign/product_requirements_document.md` is a placeholder — ignore it.
2. Notability exports have duplicate folder trees (trailing space issue).
3. `.note` files are ZIP archives containing binary plists.
4. NSDate epoch: add `978307200` to convert to Unix timestamp.
5. Medicine dose data is pre-computed lookups, not formulas.
6. OCR quality varies — expect character substitutions (`8` for `g`, `1` for `l`, `rn` for `m`).
7. `docs/notabilityNotes/mdDocs/` is intentionally empty (output directory).
8. Route matching needs number normalization — "12 Lead ECG" maps to selector `twelve-lead-ecg-monitoring`, not `12-lead-ecg-monitoring`.
9. Phantom medicine keywords removed — entinox, tetracaine, tranexamic acid, clopidogrel, ticagrelor, diazepam, furosemide, rocuronium, promethazine, sodium chloride are NOT in the ACTAS formulary.

## What to Run

- **Lint/typecheck:** `npx tsc --noEmit`
- **Python tests:** `PYTHONPATH=src/python python3 -m pytest tests/ -v`
- **Frontend tests:** `npx vitest run`
- **Quiz backend tests:** `PYTHONPATH=src/python python3 -m pytest tests/quiz/ -v`
- **CMG dose accuracy:** `PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_dose_accuracy.py -v`

## Backend API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check |
| `POST /quiz/session/start` | Start quiz session (random, gap_driven, topic) |
| `POST /quiz/question/generate` | Generate a quiz question |
| `POST /quiz/question/evaluate` | Evaluate user answer |
| `GET /quiz/mastery` | Category mastery breakdown |
| `GET /quiz/streak` | Current streak + accuracy |
| `GET /quiz/history` | Recent quiz attempts |
| `GET /medication/doses` | Medication dose reference (from structured CMG data) |
| `GET /guidelines` | List all CMGs, medicine monographs, clinical skills (type/section filters) |
| `GET /guidelines/{id}` | Single guideline detail with markdown content |
| `GET /search?q=...` | Vector search across ChromaDB collections |
| `GET /settings` | Current settings config |
| `PUT /settings` | Update settings |

## Reference Documents

- **Definitive project guide:** `CLAUDE.md`
- Progress tracker: `TODO.md`
- Standalone packaging playbook: `Guides/standalone-packaging-macos-windows.md`
- Design system: `stitchDesign/stitch_remix_of_studybot/clinical_archive/DESIGN.md`
- Acronyms: `acronyms.md`
- Source hierarchy rules: `generalRules.md`
- Pipeline guides: `Guides/`
