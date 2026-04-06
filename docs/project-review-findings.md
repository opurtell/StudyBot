# Project review — findings and fix priority

**Review date:** 2026-04-04  
**Scope:** Full-stack Clinical Recall Assistant (FastAPI backend, React/Vite/Electron frontend, pipelines, tests).  
**Verification:** `python3 -m pytest` (166 passed, 10 failed, 16 skipped); `npx vitest run` after `npm install` (65 passed, 1 failed).

---

## Git state

| Item | Status |
|------|--------|
| Uncommitted changes | **None** — working tree clean. Nothing to commit. |
| Branch | **Detached HEAD** (`HEAD` not on a named branch). Normal for a worktree checkout; consider `git switch <branch>` or creating a branch before new work so commits are not orphaned. |

---

## Priority 1 — Correctness / user-facing bugs

### 1.1 Vector store clear path does not match the retriever or pipeline

- **Issue:** `src/python/settings/router.py` defines `_CHROMA_DIR = Path("data/chroma")` and `/settings/vector-store/clear` deletes that directory.
- **Elsewhere:** `src/python/quiz/retriever.py` uses `data/chroma_db` by default. `src/python/pipeline/run.py` and `src/python/pipeline/personal_docs/run.py` use `PROJECT_ROOT / "data" / "chroma_db"`.
- **Impact:** “Clear vector store” in Settings can leave the **actual** Chroma data used by search/quiz **intact**, or clear an empty/unused folder. Users expect a full reset of embedded search data.
- **Fix direction:** Use a single canonical path (e.g. always `data/chroma_db`) everywhere, or derive a shared constant from one module imported by settings, retriever, and pipeline.

### 1.2 Quiz history API: wrong sort order and ignored `offset`

- **Issue:** `Tracker.get_recent_history` in `src/python/quiz/tracker.py` uses `ORDER BY h.id ASC` and only applies `LIMIT`. The router exposes `offset` (`src/python/quiz/router.py` `history(limit, offset)`) but **never passes `offset` into the tracker**.
- **Impact:** “Recent” history shows **oldest** attempts first (misleading label). Pagination via `offset` does nothing.
- **Fix direction:** `ORDER BY h.id DESC` (or `created_at DESC`), add `OFFSET ?` with bound parameter, and pass `offset` from the router.

---

## Priority 2 — CI reliability, onboarding, and test alignment

### 2.1 Missing `config/settings.json` in a fresh clone

- **Issue:** `config/settings.json` is gitignored (expected). `load_config()` in `src/python/llm/factory.py` opens `config/settings.json` with no fallback. Several integration-style tests and any code path that calls `_get_quiz_model()` without mocking fail with `FileNotFoundError` when the file is absent.
- **Existing asset:** `config/settings.example.json` exists and documents the shape.
- **Fix direction:** Document “copy example to `settings.json`” in README/CLAUDE.md (if not already prominent); optionally add pytest `conftest` fixture that copies example to a temp `config/settings.json` or patches `load_config`; optionally make `load_config` resolve paths relative to project root and/or merge defaults when file is missing (careful with secrets).

### 2.2 LLM provider unit tests assert outdated model IDs

- **Failures:** `tests/llm/test_anthropic_provider.py`, `test_google_provider.py`, `test_zai_provider.py` expect older names (e.g. `claude-haiku-4-5`, `gemini-2.0-flash`, `glm-4-flash`) while implementations and `src/python/llm/models.py` defaults use newer IDs (e.g. `claude-haiku-4-5-20251001`, `gemini-2.5-pro`/`gemini-3.x`, `glm-4.7-flash`).
- **Fix direction:** Update test expectations to match current defaults **or** import shared constants from `llm.models` / providers so tests track one source of truth.

### 2.3 Medication router test depends on local structured CMG data

- **Failure:** `tests/quiz/test_medication_router.py::TestMedicationDoses::test_doses_contain_adrenaline` — `load_medications()` returns `[]` when `data/cmgs/structured/med` is empty or has no matching content.
- **Fix direction:** Mark test as integration with data fixture, ship minimal fixture JSON under `tests/`, or mock `load_medications` / `MED_DIR` in the test.

### 2.4 Quiz router tests: `load_config` not mocked

- **Failures:** `tests/quiz/test_router.py` — `generate` / `evaluate` paths call `_get_quiz_model()` → `load_config()` → missing file.
- **Fix direction:** Extend `mock_deps` or conftest to patch `llm.factory.load_config` (or `quiz.router._get_quiz_model`) with a minimal dict matching `SaveSettingsRequest` shape.

---

## Priority 3 — Frontend tests, dependencies, and maintenance

### 3.1 `useApi` “handles fetch errors” test vs retry behaviour

- **Issue:** `src/renderer/hooks/useApi.ts` defaults to `maxRetries = 3` and `retryDelay = 2000`. On HTTP error it retries with **2s** delays. `tests/renderer/useApi.test.tsx` uses `waitFor` without an extended timeout and only mocks **one** failed response; the hook can remain in `loading` for multiple seconds.
- **Fix direction:** Pass `useApi(path, 1, 0)` in that test, or use `waitFor(..., { timeout: 10000 })`, or mock three failed responses.

### 3.2 Google Generative AI Python package deprecation

- **Warning:** `google.generativeai` is deprecated in favour of `google.genai` (`src/python/llm/google_provider.py`).
- **Fix direction:** Plan migration per Google’s migration guide when feasible.

### 3.3 `datetime.utcnow()` deprecation

- **Warning:** `src/python/pipeline/cmg/structurer.py` uses `datetime.utcnow()` (Python 3.12+ deprecation).
- **Fix direction:** Use timezone-aware `datetime.now(datetime.UTC)`.

### 3.4 npm audit

- **Report:** `npm install` reported **18** vulnerabilities (2 low, 5 moderate, 11 high). Not triaged here; run `npm audit` and upgrade or patch as appropriate.

---

## Consistency and architecture notes (non-blocking)

- **CORS:** `src/python/main.py` allows `localhost:5173` and `5174`; Vite defaults to **5173** — aligned for dev.
- **Working directory:** Python paths (`config/`, `data/`) are **relative to the process cwd**. Electron spawns the backend from the app path; CLI runs must start from the repo root. This is typical but worth documenting for contributors.
- **Electron:** `preload.js` exposes an empty `api` object — fine for a placeholder; no IPC surface yet.

---

## Suggested fix order (summary)

1. **Unify Chroma directory** and fix Settings “clear vector store” to target the same path as the retriever/pipeline.
2. **Fix quiz history** query (`DESC`, `OFFSET`) and wire `offset` from the API.
3. **Stabilize tests:** mock `load_config` in quiz router tests; refresh LLM provider expectations; fix medication test data or scope; adjust `useApi` error test for retries/timeouts.
4. **Onboarding:** make `settings.example.json` → `settings.json` copy step explicit; optionally add safe defaults for missing config in dev.
5. **Deprecations and npm audit** as maintenance windows allow.

---

*This document was produced by an automated review pass; re-run tests after changes to confirm.*
