# Loading Reliability Checklist

## Goal

Eliminate inconsistent page loads, reduce or remove `Failed to fetch` errors during normal app use, and make saved data feel immediate across app restarts.

## Outcome Targets

- No normal cold start should show `Failed to fetch` while the backend is still booting.
- Dashboard, Guidelines, Medication, and Settings should reuse cached data instead of blank reloading on each visit.
- User progress should remain persistent and cheap to load.
- Read-heavy CMG data should be indexed or cached so page loads do not repeatedly scan the filesystem.
- Errors should be specific: backend starting, backend unavailable, timeout, validation error, or server error.

## Phase 1: Stabilise Backend Startup

- [x] Add backend lifecycle state in Electron main process: `starting`, `ready`, `error`, `stopped`.
- [x] Stop relying on route-level fetches to discover whether the backend is available.
- [x] Expose backend status to the renderer via preload IPC.
- [x] Add renderer boot gating so page-level hooks do not run before backend readiness is known.
- [x] Add a startup shell or loading screen that explains the app is preparing local clinical data services.
- [x] Add a dedicated backend-start failure state with retry guidance.

Acceptance criteria:

- [x] Cold start does not produce page-level `Failed to fetch` errors during normal backend boot.
- [x] Renderer does not mount data-fetching views until backend readiness has been resolved.
- [x] Backend start failures show one clear app-level error state.

## Phase 2: Centralise All Renderer Requests

- [x] Create one shared API client for the renderer.
- [x] Route all existing direct `fetch` usage through that shared client.
- [x] Add request timeout handling.
- [x] Retry only on connection/startup failures, not on validation or normal 4xx responses.
- [x] Map all errors into stable app-facing categories.
- [x] Remove hook-specific retry loops that duplicate behaviour.

Target files:

- [x] [src/renderer/hooks/useApi.ts](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/hooks/useApi.ts)
- [x] [src/renderer/hooks/useSettings.ts](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/hooks/useSettings.ts)
- [x] [src/renderer/hooks/useMastery.ts](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/hooks/useMastery.ts)
- [x] [src/renderer/hooks/useQuizSession.ts](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/hooks/useQuizSession.ts)
- [x] [src/renderer/hooks/useBlacklist.ts](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/hooks/useBlacklist.ts)
- [x] [src/renderer/components/SearchBar.tsx](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/components/SearchBar.tsx)

Acceptance criteria:

- [x] All renderer calls to the local backend use one code path.
- [x] Error handling is consistent across pages.
- [x] Connection problems surface as backend-state errors rather than generic `Failed to fetch`.

## Phase 3: Add Renderer-Side Caching

- [x] Add shared query caching or a central data store for read-mostly data.
- [x] Cache settings and model registry.
- [x] Cache mastery, streak, and recent history.
- [x] Cache guideline summaries and medication list.
- [x] Cache guideline detail by id.
- [x] Deduplicate concurrent requests for the same resource.
- [x] Keep previous data visible during background refresh.
- [x] Persist safe, non-sensitive caches across app restarts where useful.
- [x] Move settings into an app-level provider so they are loaded once and reused.

Acceptance criteria:

- [x] Revisiting Dashboard, Guidelines, Medication, and Settings does not blank the screen while refetching.
- [x] Duplicate calls for the same resource are eliminated or materially reduced.
- [x] Cached data can render immediately on repeat visits.

## Phase 4: Add Backend Caching

- [x] Cache guideline summaries in Python instead of rescanning all CMG JSON files per request.
- [x] Cache guideline detail by id in memory.
- [x] Cache medication display payloads in memory.
- [x] Cache settings/model reads where useful.
- [x] Add cache invalidation when CMG refresh or pipeline rerun completes.

Target files:

- [x] [src/python/guidelines/router.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/guidelines/router.py)
- [x] [src/python/medication/router.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/medication/router.py)
- [x] [src/python/settings/router.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/settings/router.py)

Acceptance criteria:

- [x] `/guidelines` and `/medication/doses` become fast after first load.
- [x] Repeated requests do not reread and reparse every file.
- [x] Refresh operations invalidate stale cached content correctly.

## Phase 5: Precompute Local Indexes

- [x] Add a compact `guidelines-index.json` generation step to the CMG pipeline.
- [x] Include list-page fields only: id, title, section, source_type, cmg_number, is_icp_only, and lookup path or key.
- [x] Add `medications-index.json` or equivalent precomputed medication payload.
- [x] Add a persisted dashboard snapshot for quick cold-start rendering.
- [x] Keep raw CMG JSON as source of truth and treat indexes as optimisation artefacts.

Acceptance criteria:

- [x] Guideline list page no longer requires scanning all structured CMG files on each load.
- [x] Medication page can load from one compact precomputed dataset.
- [x] Indexes are regenerated whenever source data changes.

## Phase 6: Improve Persistence Model

- [ ] Keep SQLite as the persistence layer for quiz progress, history, mastery, and blacklist.
- [ ] Decide whether active quiz session state should survive restart.
- [ ] If session resume is required, persist active session/question data.
- [ ] Separate sensitive settings from non-sensitive UI cache data.
- [ ] Persist last-known dashboard snapshot for immediate first paint if useful.

Target files:

- [ ] [src/python/quiz/tracker.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/quiz/tracker.py)
- [ ] [src/python/quiz/store.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/quiz/store.py)
- [ ] [config/settings.json](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/config/settings.json)

Acceptance criteria:

- [ ] User progress always survives app restarts.
- [ ] Any chosen session-resume behaviour is explicit and tested.
- [ ] Sensitive secrets are not copied into renderer-side cache storage.

## Phase 7: Improve Page Loading UX

- [x] Replace full-page blocking spinners with controlled skeletons or stale-data rendering.
- [x] Distinguish first load from background refresh.
- [x] Keep previous data rendered during refresh.
- [x] Add a global shell-level backend status indicator.
- [x] Ensure empty-data states are distinct from error states.

Target pages:

- [x] [src/renderer/pages/Dashboard.tsx](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/pages/Dashboard.tsx)
- [x] [src/renderer/pages/Guidelines.tsx](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/pages/Guidelines.tsx)
- [x] [src/renderer/pages/Medication.tsx](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/pages/Medication.tsx)
- [x] [src/renderer/pages/Settings.tsx](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/pages/Settings.tsx)
- [x] [src/renderer/components/AppShell.tsx](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/components/AppShell.tsx)

Acceptance criteria:

- [x] Page revisits feel immediate or near-immediate.
- [x] Background refresh does not cause visible content loss.
- [x] Error states are concise and actionable.

## Phase 8: Harden Search and Quiz Flows

- [x] Keep Python backend for retrieval, LLM-backed quiz actions, and search.
- [x] Warm retriever and tracker after backend startup if cold-first-request latency is noticeable.
- [x] Add clearer loading states for question generation and answer evaluation.
- [x] Add backend-death detection after initial startup.
- [x] Pause or disable new quiz/search actions if backend becomes unavailable.

Target files:

- [x] [src/python/quiz/router.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/quiz/router.py)
- [x] [src/python/search/router.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/search/router.py)
- [x] [src/python/quiz/retriever.py](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python/quiz/retriever.py)
- [x] [src/renderer/hooks/useQuizSession.ts](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer/hooks/useQuizSession.ts)

Acceptance criteria:

- [x] First quiz/search interaction after launch is consistent.
- [x] Slow generation/evaluation states are communicated clearly.
- [x] Backend loss after startup is handled gracefully.

## Phase 9: Optional IPC Migration for Read-Only Local Data

- [ ] Decide whether to move read-only local data access from HTTP to Electron IPC.
- [ ] Prioritise IPC for settings read, mastery/history read, guideline summaries, medication list, and possibly guideline detail.
- [ ] Keep search, quiz generation, evaluation, and pipeline actions on the Python backend unless there is a strong reason to change them.
- [ ] Implement this only after caching and startup gating are complete.

Acceptance criteria:

- [ ] Read-only local data no longer depends on localhost HTTP if IPC migration is chosen.
- [ ] Dynamic backend logic remains stable and unchanged where appropriate.

## Phase 10: Logging, Diagnostics, and Observability

- [x] Add structured logging for Python process spawn, health timing, and backend-ready transition.
- [x] Add development-only request timing and cache hit/miss logging in the renderer.
- [x] Add a lightweight diagnostic view or dev overlay if needed.
- [x] Record cache age or last refresh time for key cached datasets.

Acceptance criteria:

- [x] Startup or loading regressions can be traced to backend readiness, cache misses, or slow file reads.
- [x] Developers can tell why a page was slow or unavailable.

## Phase 11: Test Coverage

- [x] Add renderer tests for backend-ready gating.
- [x] Add renderer tests for stale-data rendering during refresh.
- [x] Add renderer tests for centralised error mapping.
- [x] Add backend tests for guideline and medication cache behaviour.
- [x] Add backend tests for cache invalidation after refresh jobs.
- [x] Add persistence tests for mastery/history/blacklist survival across restarts.
- [x] Add integration-style coverage for slow backend startup.

Target test areas:

- [x] [tests/renderer](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/tests/renderer)
- [x] [tests/python](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/tests/python)
- [x] [tests/quiz](/Users/oscarpurtell/claudeCode/studyBot/StudyBot/tests/quiz)

Acceptance criteria:

- [x] Startup-related `Failed to fetch` regressions are covered by tests.
- [x] Cache invalidation logic is verified.
- [x] Persistence behaviour is verified.

## Recommended Delivery Order

- [x] Phase 1: backend readiness and startup shell
- [x] Phase 2: one renderer API client
- [x] Phase 3: renderer caching and shared providers
- [x] Phase 4: backend caching
- [x] Phase 5: precomputed indexes
- [x] Phase 7: UX refinement for loading and error states
- [x] Phase 8: search and quiz resilience
- [x] Phase 10: observability
- [x] Phase 11: broadened testing
- [ ] Phase 6 and Phase 9 as needed based on scope decisions

## Highest-Value Subset

If only the most valuable fixes are implemented first:

- [x] Gate renderer requests on backend readiness.
- [x] Centralise all renderer requests.
- [x] Cache settings, mastery, history, guideline summaries, and medications in the renderer.
- [x] Cache guideline and medication data in the backend.

Expected result:

- [x] Major reduction in `Failed to fetch` errors.
- [x] Faster and more consistent route transitions.
- [x] Better cold-start experience without a full rewrite.
