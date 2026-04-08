# Known Test Failures

**Date:** 2026-04-06 (post repo migration)

## Summary

| Suite | Total | Pass | Fail | Skip |
|-------|-------|------|------|------|
| Frontend (vitest) | 125 tests / 29 files | 108 | 17 | 0 |
| Python (pytest) | 257 tests | 242 | 4 | 17 |

---

## Frontend Failures (17)

All 17 failures are in `tests/renderer/` and fall into two categories:

### 1. Stale text matcher — app renamed (6 tests)

Tests look for `Clinical Registry` but the Sidebar component now renders `Study Assistant` / `Clinical Recall`.

| Test file | Test name |
|-----------|-----------|
| `App.test.tsx` | `App > renders the sidebar with app title` |
| `AppShell.test.tsx` | `AppShell > renders the sidebar` |
| `Sidebar.test.tsx` | `Sidebar > renders the app title` |
| `Sidebar.test.tsx` | `Sidebar > renders the version label` |
| `Sidebar.test.tsx` | `Sidebar > renders the settings link` |
| `Feedback.test.tsx` | `Feedback page shortcuts > returns to quiz with ctrl+arrowleft` |

**Fix:** Update test assertions to match current text (`Study Assistant`, `Clinical Recall`).

### 2. Component mock / provider issues (11 tests)

Tests fail because wrapped components (Quiz, Feedback, ResourceCache) don't render expected content. Likely caused by stale mocks or missing provider wrappers after component refactors.

| Test file | Test name |
|-----------|-----------|
| `Quiz.test.tsx` | `Quiz page > renders session setup initially` |
| `Quiz.test.tsx` | `Quiz page > starts a random session with the 1 shortcut` |
| `Quiz.test.tsx` | `Quiz page > submits with ctrl+enter from outside the textarea` |
| `Quiz.test.tsx` | `Quiz page > opens full analysis with ctrl+shift+a from inline feedback` |
| `Quiz.test.tsx` | `Quiz page > advances to the next question with ctrl+arrowright from inline feedback` |
| `QuizQuestion.test.tsx` | `QuizQuestion > renders question badge and text` |
| `FeedbackSplitView.test.tsx` | `FeedbackSplitView > renders practitioner response section` |
| `FeedbackSplitView.test.tsx` | `FeedbackSplitView > renders AI analysis section` |
| `ResourceCacheProvider.test.tsx` | `ResourceCacheProvider persistence > hydrates safe persisted cache entries on first render` |
| `focusMode.test.tsx` | `Focus mode routing > renders sidebar on dashboard route` |
| `focusMode.test.tsx` | `Focus mode routing > hides sidebar on quiz route` |

**Fix:** Update mocks and provider wrappers to match current component interfaces.

---

## Python Failures (4)

### 1. Stale mock target — `NOTABILITY_DIR` removed (2 tests)

| Test file | Test name |
|-----------|-----------|
| `test_sources_router.py` | `test_get_sources_returns_repository_cards` |
| `test_sources_router.py` | `test_get_sources_handles_missing_directories` |

**Error:** `AttributeError: module 'sources.router' has no attribute 'NOTABILITY_DIR'`

The `NOTABILITY_DIR` constant was removed from `src/python/sources/router.py` but the tests still monkeypatch it. Remove the `NOTABILITY_DIR` mock line from both tests.

### 2. Stale mock target — `capture_all_assets` removed (2 tests)

| Test file | Test name |
|-----------|-----------|
| `test_cmg_refresh.py` | `test_run_refresh_persists_success_status_and_history` |
| `test_cmg_refresh.py` | `test_run_refresh_preserves_last_successful_time_on_failure` |

**Error:** `AttributeError: module 'pipeline.cmg.refresh' has no attribute 'capture_all_assets'`

The `capture_all_assets` function was removed from the refresh module during standalone packaging refactoring, but the tests still monkeypatch it. Update tests to match current module exports.

---

## Notes

- `tests/quiz/test_router.py` (11 tests) failed when run as part of the full suite but **pass in isolation**. This is a test isolation issue (shared state between test modules), not a real failure.
- All failures are pre-existing — none were introduced by the repo migration.
