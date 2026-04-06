# Renderer API Client Centralisation

## Problem

Renderer-side backend access has been partially centralised into `src/renderer/lib/apiClient.ts`, but the transport contract is still underspecified at the hook boundary. `useApi` and `useSettings` continue to carry duplicated lifecycle and error-handling logic, and the next phase needs a clear contract before further refactors start.

The risk is not only code duplication. If hooks keep shaping transport rules independently, the app drifts back toward inconsistent timeout behaviour, inconsistent backend-startup handling, and inconsistent user-facing errors.

## Scope

This phase standardises renderer transport behaviour only.

Included:
- one renderer HTTP client contract
- backend readiness gating before HTTP requests
- request timeout handling
- retry policy for startup/connection/timeout failures only
- stable error categories and displayable messages
- hook integration for `useApi` and `useSettings`
- focused renderer tests for the client and the refactored hooks

Not included:
- renderer-side caching or stale-while-refresh data retention
- React Query or other query-library adoption
- backend endpoint changes
- UI redesign of loading or error surfaces
- persistence changes

## Current State

### Shared client

`src/renderer/lib/apiClient.ts` already provides verb helpers and some important infrastructure:
- localhost base URL
- preload-backed backend readiness gating
- timeout cancellation
- limited retry behaviour
- category-based `ApiClientError`

This is the correct centre of gravity. The next phase should harden its contract rather than replace it.

### `useApi`

`src/renderer/hooks/useApi.ts` still adds transport-adjacent behaviour that should be minimised:
- legacy `maxRetries` parameter at the hook layer
- unused retry-delay parameter
- string-only error output
- no explicit abort handling for unmount/refetch races

### `useSettings`

`src/renderer/hooks/useSettings.ts` duplicates request handling patterns across multiple flows:
- separate `try/catch` blocks for each request
- mounted-flag lifecycle protection
- silent failure for model registry load
- one shared `error` string used by several unrelated actions

The hook is doing more transport work than it should.

## Design

### Central contract

`apiClient` remains the only renderer module allowed to call `fetch` for backend HTTP requests.

The client contract consists of:
- `apiGet<T>(path, options)`
- `apiPost<T>(path, body, options)`
- `apiPut<T>(path, body, options)`
- `apiDelete<T>(path, options)`
- shared `ApiRequestOptions`
- shared `ApiClientError`

`ApiRequestOptions` should support:
- `headers`
- `body` where relevant
- `timeoutMs`
- `retries`
- `signal`

The client owns:
- path normalisation
- JSON body/header handling
- backend readiness gating
- timeout wiring
- fetch execution
- response parsing
- response-to-error mapping
- retry decisions

### Error model

The renderer uses a stable transport error taxonomy:
- `backend-starting`
- `backend-unavailable`
- `timeout`
- `invalid-request`
- `server-error`

Each thrown `ApiClientError` should contain:
- `category`
- `message`
- optional `status`

Inference from the current code: a boolean retryability signal would also be useful at the client boundary, but only if a hook or component genuinely needs it. Otherwise retry logic stays internal to the client.

### Retry policy

Retries should occur only when the failure is plausibly transient in a local desktop app:
- backend still starting
- backend unavailable because the local service is not yet reachable
- request timed out

Retries should not occur for:
- 4xx validation or request errors
- 5xx server errors after the backend has responded
- caller-triggered aborts

### Abort behaviour

The client must compose timeout aborts and caller-provided abort signals safely.

Required behaviour:
- caller abort propagates immediately
- timeout abort maps to `timeout`
- caller abort does not get remapped to a transport error
- signal listeners are removed in all code paths

Hooks that perform auto-loads should use aborts instead of mounted flags where practical. That keeps cancellation aligned with the transport layer.

### Hook integration

#### `useApi`

`useApi` should be a light lifecycle wrapper around `apiGet`.

Responsibilities:
- trigger load on mount and when dependencies change
- manage `data`, `loading`, `error`
- expose `refetch`
- avoid stale state updates after unmount or superseded fetches

Non-responsibilities:
- implementing its own retry policy
- categorising transport failures
- owning timeout defaults

Open choice:
- keep returning `error: string | null` for compatibility, or return both `error` and `errorDetail`/`apiError` if pages would benefit from category-aware UI later.

Recommended choice for this phase: preserve the existing public shape where possible and add structured error exposure only if the current refactor needs it immediately.

#### `useSettings`

`useSettings` should stay a domain hook, but its transport rules should come from `apiClient`.

Responsibilities:
- orchestrate initial settings and model-registry loads
- expose saving state separately from initial loading state
- update local hook state after successful saves
- surface failures with consistent messages

Recommended handling for `/settings/models` load failure:
- keep the main settings page usable
- do not fail the entire hook initialisation
- capture the failure in a controlled, explicit way rather than a silent catch if practical

## Implementation Boundaries

Files expected in scope:
- `src/renderer/lib/apiClient.ts`
- `src/renderer/hooks/useApi.ts`
- `src/renderer/hooks/useSettings.ts`
- `src/renderer/hooks/useBlacklist.ts`
- `src/renderer/hooks/useMastery.ts`
- `src/renderer/hooks/useQuizSession.ts`
- `src/renderer/components/SearchBar.tsx`
- `tests/renderer/*`

Files intentionally out of scope for this phase:
- renderer caching/provider infrastructure
- backend routers and service code
- persistence and pipeline code

## Test Strategy

Minimum coverage for this phase:
- `apiClient` success path
- `apiClient` timeout path
- `apiClient` backend-starting path
- `apiClient` backend-unavailable path
- `apiClient` 4xx mapping to `invalid-request`
- `apiClient` 5xx mapping to `server-error`
- retry/no-retry boundaries
- `useApi` initial load and refetch behaviour
- `useSettings` initial load behaviour
- `useSettings` save failure behaviour

Use deterministic mocks for:
- `window.api.backend.waitForReady`
- `fetch`
- timers where timeout behaviour is exercised

## Acceptance Criteria

- All renderer HTTP requests continue to route through `src/renderer/lib/apiClient.ts`.
- `useApi` and `useSettings` stop owning independent transport policy.
- Timeout, startup gating, and error mapping are consistent across hooks.
- Generic browser fetch errors no longer leak directly into normal renderer flows.
- The central transport contract is covered by renderer tests.

## Deferred Follow-Up

After this phase lands, the next logical phase is renderer-side data caching and shared providers. That work should build on this client contract rather than being mixed into it.
