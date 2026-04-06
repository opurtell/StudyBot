# Loading Reliability Implementation Plan

## Purpose

This plan turns the loading-consistency work into an execution sequence with concrete responsibilities, files, risks, and acceptance criteria. It is written to support staged implementation without a large rewrite.

## Problem Summary

The app currently uses a local FastAPI backend as the single bridge between the renderer and local data. That is a valid architecture, but the current implementation has four weaknesses:

1. The renderer issues page-level requests before the backend is reliably ready.
2. Requests are spread across many hooks and components with inconsistent retry and error behaviour.
3. Read-heavy local data is repeatedly loaded from disk and reparsed instead of being cached or indexed.
4. The UI often treats refreshes as first load, causing blank or fragile page states.

## Core Principles

- The backend is local infrastructure, not an unreliable internet dependency.
- Page loads should be gated by app readiness, not by independent route failures.
- Persisted data should be surfaced quickly using cache-first rendering where safe.
- The renderer should have one request policy.
- Raw CMG data remains the source of truth, but indexed artefacts can be added for speed.

## Workstream A: Backend Lifecycle Control

### Objective

Make backend startup a first-class Electron responsibility so the renderer never guesses whether Python is ready.

### Implementation steps

1. Extend [src/electron/main.js](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/electron/main.js) with a backend status state machine.
2. Capture:
   - python spawn success/failure
   - health-check attempts
   - ready transition time
   - backend exit after ready
3. Add IPC handlers or events in Electron main for:
   - get current backend status
   - subscribe to backend status updates
4. Expose these handlers through [src/electron/preload.js](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/electron/preload.js).
5. Add a renderer bootstrap provider that blocks route-level data loading until backend readiness has been resolved.

### Files

- [src/electron/main.js](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/electron/main.js)
- [src/electron/preload.js](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/electron/preload.js)
- [src/renderer/App.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/App.tsx)

### Risks

- If status changes are not well defined, the renderer may still race against backend boot.
- If the preload API is too thin, later request centralisation will need another round of refactor.

### Acceptance criteria

- Cold start shows one controlled app state until backend is `ready` or `error`.
- No route attempts data fetch while backend state is still `starting`.
- Backend failure after launch is visible to the renderer.

## Workstream B: Shared Request Client

### Objective

Remove inconsistent request behaviour and stop leaking raw `fetch` details into page hooks.

### Implementation steps

1. Create a shared client module under the renderer, for example `src/renderer/lib/apiClient.ts`.
2. Add:
   - typed `get`, `post`, `put`, `delete`
   - backend-ready gating
   - timeout control
   - abort signal support
   - retry policy only for connection/startup failures
   - structured error objects
3. Replace direct `fetch` usage in:
   - [src/renderer/hooks/useApi.ts](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useApi.ts)
   - [src/renderer/hooks/useSettings.ts](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useSettings.ts)
   - [src/renderer/hooks/useMastery.ts](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useMastery.ts)
   - [src/renderer/hooks/useQuizSession.ts](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useQuizSession.ts)
   - [src/renderer/hooks/useBlacklist.ts](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useBlacklist.ts)
   - [src/renderer/components/SearchBar.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/components/SearchBar.tsx)
4. Standardise displayable error categories:
   - backend starting
   - backend unavailable
   - timed out
   - invalid request
   - server error

### Risks

- Changing all request paths at once can create regressions if not covered by tests.
- If retries are too aggressive, page latency will stay inconsistent.

### Acceptance criteria

- All local backend calls use the shared client.
- A connection failure is never shown as a generic browser error.
- Request retries behave consistently across pages.

## Workstream C: Renderer Data Cache and Providers

### Objective

Make route transitions fast and predictable by reusing data instead of discarding it every mount.

### Implementation steps

1. Add a cache strategy for read-mostly resources.
2. Introduce one or more app-level providers:
   - backend status provider
   - settings provider
   - optional query cache provider
3. Cache:
   - settings
   - model registry
   - mastery
   - streak
   - history
   - guideline summaries
   - medication list
   - guideline detail by id
4. Keep stale data visible during refresh.
5. Persist only safe caches across app restarts.

### Candidate files

- [src/renderer/App.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/App.tsx)
- [src/renderer/pages/Dashboard.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Dashboard.tsx)
- [src/renderer/pages/Guidelines.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Guidelines.tsx)
- [src/renderer/pages/Medication.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Medication.tsx)
- [src/renderer/pages/Settings.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Settings.tsx)

### Risks

- Persisting too much renderer-side state can create stale-data bugs if invalidation is weak.
- Sensitive settings must not be copied into casual browser storage.

### Acceptance criteria

- Returning to a previously opened page feels immediate.
- Refresh does not remove already-rendered content.
- Duplicate requests for the same dataset are deduplicated.
- Status: implemented with `ResourceCacheProvider`, `SettingsProvider`, stale-while-refresh page states on Dashboard, Guidelines, Medication, and Settings, and persisted non-sensitive cache hydration for dashboard, guideline, medication, and model-registry reads.

## Workstream D: Backend Read Caches

### Objective

Avoid repeated filesystem scans and markdown parsing for local data that changes rarely.

### Implementation steps

1. In [src/python/guidelines/router.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/guidelines/router.py), build:
   - cached list of guideline summaries
   - `id -> detail` lookup index or `id -> path` index
2. In [src/python/medication/router.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/medication/router.py), cache the medication payload after first build.
3. In [src/python/settings/router.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/settings/router.py), consider lightweight caching of stable reads.
4. Add explicit cache invalidation hooks after:
   - CMG refresh completion
   - pipeline rerun
   - any action that changes underlying structured data

### Risks

- Cache invalidation bugs can hide updated clinical data.
- Overcaching the wrong layer can duplicate memory usage without much gain.

### Acceptance criteria

- `/guidelines` does not rescan all JSON files on each request.
- `/medication/doses` does not rebuild the medication payload every request.
- Cache clear paths are explicit and testable.
- Status: implemented with router-level caches plus explicit invalidation from settings and CMG refresh paths, including cached settings and model-registry reads.

## Workstream E: Precomputed Index Artefacts

### Objective

Shift repeated read/parse work into the pipeline so the app reads compact prebuilt indexes.

### Implementation steps

1. Extend the CMG pipeline to output `guidelines-index.json`.
2. Keep the index list-oriented and small.
3. Add `medications-index.json` or equivalent precomputed medication payload.
4. Generate a dashboard snapshot path for quick cold-start rendering.
5. Document index ownership and rebuild rules.

### Candidate files

- [src/python/pipeline/cmg/orchestrator.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/orchestrator.py)
- [src/python/pipeline/cmg/structurer.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/structurer.py)
- [src/python/pipeline/cmg/refresh.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/refresh.py)

### Risks

- Pipeline complexity increases slightly.
- Index generation must stay in sync with structured schema changes.

### Acceptance criteria

- Guideline list data comes from one compact artefact.
- Medication display data comes from one compact artefact or one cached payload.
- Rebuilds occur automatically when source content changes.
- Status: implemented in the CMG structurer via `guidelines-index.json` and `medications-index.json`, with quick dashboard cold-start rendering provided by the persisted renderer dashboard snapshot.

## Workstream F: Persistence Review

### Objective

Use the right persistence layer for each category of data and make restart behaviour explicit.

### Implementation steps

1. Keep [src/python/quiz/tracker.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/quiz/tracker.py) as the authoritative progress store.
2. Review whether [src/python/quiz/store.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/quiz/store.py) should remain in-memory only.
3. If resumable quiz sessions are required:
   - persist active session config
   - persist current question payload
   - decide resume expiry rules
4. Keep secrets in backend-owned storage, not renderer caches.
5. Persist non-sensitive last-known page snapshots where they improve perceived speed.

### Risks

- Session persistence may add complexity if quiz generation semantics assume short-lived in-memory state.
- Mixing secret and non-secret persistence carelessly creates unnecessary exposure.

### Acceptance criteria

- Progress survives restart.
- Session-resume behaviour, if added, is deterministic and documented.
- Non-sensitive cached content can speed cold starts.

## Workstream G: Page UX Refinement

### Objective

Make loading states intentional instead of blank or fragile.

### Implementation steps

1. Replace full blocking spinners with:
   - startup shell
   - skeletons on first page load
   - stale-data rendering during refresh
2. Add explicit page states:
   - first load
   - refreshing
   - empty
   - backend unavailable
   - server error
3. Add a subtle backend status indicator in [src/renderer/components/AppShell.tsx](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/components/AppShell.tsx).
4. Ensure pages do not erase previous content just because a background refresh began.

### Risks

- If state modelling is weak, pages may show stale content without clear refresh cues.
- Distinct empty and error states must remain easy to understand when cached content is present.

### Acceptance criteria

- Page transitions are stable.
- Refreshes are visually calm.
- Error states tell the user what actually happened.
- Status: largely implemented on Dashboard, Guidelines, Medication, Settings, and AppShell; remaining refinement is mostly around sharper empty-state and error-state distinctions.

## Workstream H: Search and Quiz Resilience

### Objective

Improve consistency for the flows that genuinely need backend logic and may involve heavier work.

### Implementation steps

1. Warm [src/python/quiz/retriever.py](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/quiz/retriever.py) and tracker on backend-ready if needed.
2. Add clearer loading and timeout handling in [src/renderer/hooks/useQuizSession.ts](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useQuizSession.ts).
3. Distinguish:
   - generating question
   - evaluating answer
   - backend unavailable
   - provider or server error
4. Detect backend death after initial readiness and disable new actions safely.

### Risks

- Warmup can slightly increase startup time if done too early.
- Search and quiz flows are more complex than simple read endpoints and need more careful error mapping.

### Acceptance criteria

- First real quiz/search action after startup is more reliable.
- Slow operations show a clear state instead of a generic failure.
- Status: partially implemented with quiz generation/evaluation state labels and renderer-side disablement when backend availability drops; retriever or tracker warm-up remains open.

## Workstream I: Optional IPC Migration

### Objective

Remove localhost HTTP for simple local reads if the team decides the complexity is worth it.

### Implementation steps

1. After startup gating and caching are complete, evaluate remaining HTTP pain points.
2. If worthwhile, move read-only local data access to Electron IPC:
   - settings read
   - mastery/history read
   - guideline summaries
   - medication list
   - possibly guideline detail
3. Keep Python HTTP for:
   - quiz generation
   - answer evaluation
   - search
   - pipeline jobs
   - refresh jobs

### Risks

- Hybrid IPC and HTTP data access adds architecture complexity.
- The win may be modest if caching has already solved most user-facing latency.

### Acceptance criteria

- IPC migration is justified by measurable reliability or latency gains.
- Dynamic backend workflows remain stable.

## Workstream J: Observability and Testing

### Objective

Make future regressions diagnosable and prevent this class of issue from returning.

### Implementation steps

1. Add backend startup timing logs in Electron main.
2. Add development-only request timing and cache hit/miss logs in the renderer.
3. Add or extend tests for:
   - backend readiness gating
   - shared request error mapping
   - stale-data rendering
   - backend cache behaviour
   - cache invalidation
   - persistence survival across restart
4. Add at least one slow-start integration scenario.

### Candidate test paths

- [tests/renderer](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/tests/renderer)
- [tests/python](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/tests/python)
- [tests/quiz](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/tests/quiz)

### Acceptance criteria

- Slow-backend startup no longer causes unhandled page-level fetch errors.
- Cache invalidation behaviour is covered.
- Persistence expectations are covered.
- Status: completed with app-level slow-start renderer coverage and tracker restart-persistence tests for mastery, history, and blacklist.

## Delivery Sequence

### Stage 1: Reliability Foundation

1. Backend lifecycle state in Electron
2. Preload bridge for backend status
3. Renderer startup gating
4. Shared request client

Result:

- Most startup `Failed to fetch` issues should disappear.

### Stage 2: Perceived Speed

1. Renderer cache/providers
2. Backend in-memory caches
3. Page stale-data rendering

Result:

- Route revisits feel fast and stable.

### Stage 3: Structural Optimisation

1. Precomputed indexes
2. Persistence review for resumable sessions
3. Search/quiz resilience improvements

Result:

- Lower steady-state load cost and more predictable first-request performance.

### Stage 4: Optional Architecture Tightening

1. Selective IPC migration for read-only local data
2. Expanded diagnostics and tests

Result:

- Further reduction in dependency on localhost HTTP where it provides little value.

## Decision Notes

### What should definitely stay on the backend

- ChromaDB retrieval
- Search
- Quiz generation
- Answer evaluation
- Pipeline jobs
- CMG refresh orchestration

### What can be moved to IPC later if useful

- Settings read
- Mastery/history read
- Guideline summaries
- Medication list
- Possibly guideline detail

### What should remain persistent

- Quiz history
- Mastery source data
- Blacklist
- User settings
- Model registry
- Optional last-known dashboard snapshot

## Recommended Starting Scope

If implementation needs to start with the smallest valuable slice, begin with:

1. Electron backend status and renderer gating
2. Shared request client
3. Settings/mastery/history/guidelines/medication renderer cache
4. Backend cache for guidelines and medication payload

That sequence should deliver the largest improvement in consistency without forcing an immediate architectural rewrite.
