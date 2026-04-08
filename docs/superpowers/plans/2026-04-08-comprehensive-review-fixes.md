# Comprehensive Review — Remaining Issues Plan

**Date:** 2026-04-08
**Status:** Issues documented; fixes applied for high-severity items.

---

## Issues Fixed in This Review

### Test Fixes
1. **28 frontend test failures → 0** — Added `BackgroundProcessProvider` to all test wrappers that render components using `useBackgroundProcesses()`. Updated `testUtils.tsx`, `Sidebar.test.tsx`, `Dashboard.test.tsx`, `AppShell.test.tsx`, `Settings.test.tsx`.
2. **Library cleaning feed never displayed** — TypeScript type `cleaningFeed` (camelCase) didn't match API response `cleaning_feed` (snake_case). Fixed `api.ts` type and `Library.tsx` to use `cleaning_feed`.

### Security Fixes
3. **Path traversal in upload endpoint** (`upload/router.py`) — `file.filename` was used unsanitised in file paths. Added validation to reject filenames containing `..`, `/`, or `\\`.
4. **Electron sandbox not explicit** (`electron/main.js`) — Added `sandbox: true` to `webPreferences` for defense-in-depth.
5. **Production file:// URL construction** (`electron/main.js`) — Changed from string concatenation to `url.pathToFileURL()` for Windows path compatibility.
6. **SQLite thread safety** (`quiz/tracker.py`) — Added `threading.Lock()` around all database operations to prevent concurrent access issues from FastAPI's async thread pool.
7. **`_rebuild_status` race condition** (`settings/router.py`) — Added `_rebuild_lock` to serialise read/write access to the rebuild status dict.

---

## Remaining Issues (Require Separate Plans)

### HIGH — Build & Packaging

#### 1. Windows PYTHONPATH mismatch in production
**File:** `src/electron/main.js:128-131`
**Problem:** Production PYTHONPATH points to `backend/lib` but the Windows packaging script installs packages to `backend/Lib/site-packages/`. Windows builds will fail to find `fastapi`, `uvicorn`, `chromadb`, etc.
**Fix:** Add Windows-specific PYTHONPATH that includes `Lib/site-packages`. Detect `process.platform === "win32"` and adjust the path array.

#### 2. Missing CMG data in CI release builds
**Files:** `.gitignore:24` (gitignores `data/cmgs/`), `electron-builder.yml:15-18` (references `data/cmgs/structured`)
**Problem:** `data/cmgs/` is gitignored so `actions/checkout` in CI won't have it. The release workflow has no step to generate CMG structured JSON before building. The ChromaDB pre-build in `package-backend.sh` will produce an empty index.
**Fix:** Either (a) commit `data/cmgs/structured/*.json` to the repo, (b) add a CI step that runs the CMG extraction pipeline, or (c) download a pre-built CMG dataset as a CI artifact.

### MEDIUM — Build & Packaging

#### 3. No code signing configured
**File:** `electron-builder.yml`
**Problem:** No `identity`, `hardenedRuntime`, `certificateFile`, or `publisherName` configured. Both macOS and Windows builds will show security warnings (Gatekeeper / SmartScreen).
**Fix:** Configure signing credentials as CI secrets and reference them in `electron-builder.yml`.

#### 4. No macOS hardenedRuntime
**File:** `electron-builder.yml`
**Problem:** Without hardened runtime, macOS Gatekeeper may block the app even with ad-hoc signing.
**Fix:** Add `hardenedRuntime: true` to the `mac` section.

#### 5. Playwright in runtime dependencies
**File:** `pyproject.toml:14`
**Problem:** Playwright is a scraping-only dependency but listed in main `dependencies`. It gets installed into the standalone backend payload, adding unnecessary size.
**Fix:** Move Playwright to an optional dependency group (e.g. `[project.optional-dependencies] scraping`).

### MEDIUM — Code Quality

#### 6. Quiz router test state pollution
**File:** `tests/quiz/test_router.py`
**Problem:** Tests pass in isolation but fail when run after other test modules due to shared module-level state (the FastAPI app singleton accumulates state from prior test files).
**Fix:** Use a fixture that creates a fresh `FastAPI` app instance per test module, or add cleanup fixtures that reset module-level caches between tests.

#### 7. In-memory question/session store
**File:** `src/python/quiz/store.py`
**Problem:** Questions and sessions are stored in module-level dicts. All data is lost on backend restart, which happens every time the Electron app restarts. In-progress quiz sessions are lost.
**Fix:** Persist to SQLite alongside the mastery tracker, or accept as intentional design (ephemeral sessions).

#### 8. Generic exception handler leaks stack traces
**File:** `src/python/main.py:74-80`
**Problem:** `generic_error_handler` returns `str(exc)` which may include file paths, SQL queries, or other internal details. In a localhost app this is low risk but bad practice.
**Fix:** Return a generic error message in production, log the full exception server-side only.

### LOW — Code Quality

#### 9. ZaiProvider has no specific error categorisation
**File:** `src/python/llm/zai_provider.py:20-21`
**Problem:** All exceptions are caught as `ErrorCategory.UNKNOWN` — rate limit and auth errors from ZhipuAI aren't properly categorised.
**Fix:** Parse ZhipuAI error responses to detect rate limit (429) and auth (401) errors, similar to GoogleProvider.

#### 10. Quiz store lacks size limits
**File:** `src/python/quiz/store.py`
**Problem:** `_questions` and `_sessions` dicts grow unboundedly. Over a long session, memory usage increases without cleanup.
**Fix:** Add periodic cleanup of old sessions (e.g., evict sessions older than 24 hours).
