# Renderer API Client Centralisation Implementation Plan

> **For agentic workers:** Execute this plan in order. Keep changes staged, preserve any user edits already in flight, and verify each step before moving on.

**Goal:** Consolidate renderer-to-backend requests behind one central client so fetch gating, timeout handling, retries, and error mapping are consistent across hooks and pages.

**Architecture:** `src/renderer/lib/apiClient.ts` becomes the only transport boundary for localhost HTTP calls. Hooks stop re-implementing request state rules and instead consume typed client helpers plus shared error metadata.

**Tech Stack:** React 19 / TypeScript 5 / Electron 32 renderer / FastAPI backend / vitest

---

### Task 1: Lock the shared client contract

**Files:**
- Review: `src/renderer/lib/apiClient.ts`
- Review: `src/renderer/types/backend.ts`
- Review: `src/renderer/types/electron.d.ts`

- [ ] Confirm the client remains the single request entry point for renderer HTTP work.
- [ ] Define the stable request surface: `apiGet`, `apiPost`, `apiPut`, `apiDelete`, request options, timeout override, retry count, and abort signal passthrough.
- [ ] Define the stable error surface: category, message, status, and whether the error is retryable.
- [ ] Confirm backend gating behaviour: wait for preload backend readiness before issuing HTTP requests, surface `backend-starting` and `backend-unavailable` explicitly.
- [ ] Confirm non-goals for this phase: no caching layer, no query library migration, no backend API schema changes.

**Acceptance criteria:**
- [ ] One written contract exists for request options and error categories.
- [ ] Gating, timeout, and retry semantics are clear before hook refactors begin.

---

### Task 2: Harden `apiClient` behaviour around one policy

**Files:**
- Modify: `src/renderer/lib/apiClient.ts`

- [ ] Add or confirm one internal `request` path used by all verbs.
- [ ] Ensure timeout cancellation and caller-provided abort signals work together without leaking listeners.
- [ ] Ensure retries occur only for startup, connection, and timeout failures.
- [ ] Ensure 4xx responses map to `invalid-request` and 5xx responses map to `server-error`.
- [ ] Ensure empty and non-JSON responses are handled safely.
- [ ] Expose any helper needed by hooks, such as an `isApiClientError` guard or retryability metadata, only if it removes duplicate hook logic.

**Acceptance criteria:**
- [ ] Every renderer HTTP verb goes through the same timeout, gating, and error mapping path.
- [ ] Browser-native `Failed to fetch` errors no longer escape directly to hooks.

---

### Task 3: Refactor `useApi` onto the shared client contract

**Files:**
- Modify: `src/renderer/hooks/useApi.ts`
- Review: `src/renderer/pages/Library.tsx`
- Review: `src/renderer/pages/Guidelines.tsx`
- Review: `src/renderer/pages/Medication.tsx`
- Review: `src/renderer/hooks/useHistory.ts`

- [ ] Remove unused retry-delay plumbing and any duplicated retry assumptions inside the hook.
- [ ] Keep the hook focused on request lifecycle state: `data`, `loading`, `error`, `refetch`.
- [ ] Decide whether `error` remains a string or should expose the structured `ApiClientError` alongside a displayable message.
- [ ] Add mount-safety or abort handling so unmounted components do not update state after request completion.
- [ ] Verify existing pages using `useApi` keep their current behaviour with the new contract.

**Acceptance criteria:**
- [ ] `useApi` delegates transport behaviour to `apiClient` instead of carrying its own policy.
- [ ] Hook consumers do not need to understand fetch timeout or backend boot details.

---

### Task 4: Refactor `useSettings` to remove duplicated request handling

**Files:**
- Modify: `src/renderer/hooks/useSettings.ts`
- Review: `src/renderer/pages/Settings.tsx`
- Review: `src/renderer/pages/Guidelines.tsx`
- Review: `src/renderer/pages/Medication.tsx`

- [ ] Move settings load, model-registry load, save, model save, pipeline rerun, and vector-store clear flows onto the central client contract.
- [ ] Remove ad hoc mounted-flag and repeated `try/catch` patterns where a shared helper or abort-based approach is clearer.
- [ ] Decide whether secondary loads such as `/settings/models` should fail silently, expose a non-blocking warning, or share the main hook error state.
- [ ] Keep state split clear: initial loading, saving settings, saving models, and action-trigger failures.
- [ ] Preserve current consumer API unless a stricter contract materially improves correctness.

**Acceptance criteria:**
- [ ] `useSettings` no longer duplicates transport policy already owned by `apiClient`.
- [ ] Settings screens surface consistent, specific errors for load and save paths.

---

### Task 5: Align the remaining renderer callers with the same policy

**Files:**
- Review/Modify as needed: `src/renderer/hooks/useBlacklist.ts`
- Review/Modify as needed: `src/renderer/hooks/useMastery.ts`
- Review/Modify as needed: `src/renderer/hooks/useQuizSession.ts`
- Review/Modify as needed: `src/renderer/components/SearchBar.tsx`

- [ ] Verify these callers already rely on `apiClient` correctly after the contract is finalised.
- [ ] Remove any caller-specific mapping that recreates client error categories or retry rules.
- [ ] Standardise user-facing fallback messages where the same backend state should read the same across screens.
- [ ] Capture any follow-up work that belongs to caching/providers rather than this transport phase.

**Acceptance criteria:**
- [ ] Renderer HTTP access has one practical policy, not just one helper module.
- [ ] Remaining duplication is documented if intentionally deferred.

---

### Task 6: Add focused test coverage for the transport layer and hook integration

**Files:**
- Add/Modify: `tests/renderer/*`

- [ ] Add unit coverage for `apiClient` request success, timeout, backend-starting, backend-unavailable, invalid-request, and server-error paths.
- [ ] Add coverage for retry boundaries so 4xx responses do not retry and startup/timeout failures do.
- [ ] Add hook coverage for `useApi` state transitions and refetch.
- [ ] Add hook coverage for `useSettings` initial load and at least one save failure path.
- [ ] Use mocked `window.api.backend.waitForReady` and mocked `fetch` so tests stay deterministic.

**Acceptance criteria:**
- [ ] The central client contract is test-backed.
- [ ] Refactors in hooks cannot silently reintroduce generic fetch failures.

---

### Task 7: Verify and document rollout boundaries

**Files:**
- Update: `TODO.md`
- Update if needed: `Guides/loading-reliability-checklist.md`
- Update if needed: `Guides/loading-reliability-implementation-plan.md`

- [ ] Mark this phase as the transport-standardisation slice of the larger loading-reliability work.
- [ ] Record any deferred follow-ups, especially renderer caching/provider work.
- [ ] Run the targeted renderer test suite and `npx tsc --noEmit`.
- [ ] Note any behavioural changes that page owners need to expect.

**Acceptance criteria:**
- [ ] The repo contains an implementation plan, a design spec, and a tracking reference for this phase.
- [ ] Verification steps are explicit before implementation starts.
