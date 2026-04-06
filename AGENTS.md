# Clinical Recall Assistant — Agent Instructions

This file is the authoritative reference for all agentic workers (Claude Code, subagents, etc.) operating on this codebase. CLAUDE.md should be treated as AGENTS.md and is the **ULTIMATE** guide and information there is the final truth if AGENTS.md and CLAUDE.md conflict.

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

## Key Technical Context

| Concern | Choice |
|---------|--------|
| GUI | Electron 32 + React 19 + Vite 6 |
| Styling | Tailwind CSS 3 (Archival Protocol design tokens, darkMode: "class") |
| Backend | FastAPI on 127.0.0.1:7777 |
| Vector DB | ChromaDB (local PersistentClient) |
| LLM | Multi-provider abstraction (Anthropic, Google, Z.ai) |
| Testing | vitest + @testing-library/react (frontend), pytest + httpx (Python) |
| Language | TypeScript 5 (renderer), Python 3.10+ (backend) |

## Code Style

- Python: PEP 8, type hints on public functions, `snake_case.py`
- TypeScript/React: functional components, named exports, `PascalCase.tsx`
- Data files: `kebab-case`
- Git commits: imperative mood, concise
- Branch naming: `feature/`, `fix/`, `pipeline/`, `ui/`

## Key Gotchas

1. `stitchDesign/product_requirements_document.md` is a placeholder — ignore it.
2. Notability exports have duplicate folder trees (trailing space issue).
3. `.note` files are ZIP archives containing binary plists.
4. NSDate epoch: add `978307200` to convert to Unix timestamp.
5. Medicine dose data is pre-computed lookups, not formulas.
6. OCR quality varies — expect character substitutions.
7. `docs/notabilityNotes/mdDocs/` is intentionally empty (output directory).

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

- Full project guide: `CLAUDE.md`
- Progress tracker: `TODO.md`
- Standalone packaging playbook: `Guides/standalone-packaging-macos-windows.md`
- Design system: `stitchDesign/stitch_remix_of_studybot/clinical_archive/DESIGN.md`
- Acronyms: `acronyms.md`
- Source hierarchy rules: `generalRules.md`
- Pipeline guides: `Guides/`
