# CMG Refresh: Wire Backend into Settings UI

Date: 2026-04-05

## Problem

The backend exposes two CMG refresh endpoints that are fully implemented and tested:

- `GET /settings/cmg-refresh` — returns current refresh status
- `POST /settings/cmg-refresh/run` — starts a background refresh

The Settings page Data Management section only renders "Re-run Pipeline" and "Clear Vector Store". There is no way to trigger a CMG refresh or see its status from the app.

## Scope

Wire the existing backend CMG refresh capability into the Settings UI. No backend changes. No new components. Three files are modified.

## Design Decisions

### Polling inside SettingsProvider

The polling logic lives in `SettingsProvider`, consistent with the existing pattern where `rerunPipeline` and `clearVectorStore` are provider-level actions. This makes CMG refresh status available to any consumer of `useSettings()`, not just the Settings page.

Polling interval: 5 seconds while `status === "running"`. Fetches once on mount. Stops polling when the refresh completes or fails. Cleans up the interval on unmount.

### Expanded Data Management section

The CMG refresh controls are added to the existing Data Management section in Settings.tsx, not in a new section. This keeps all data operations grouped together.

## Files Changed

### `src/renderer/types/api.ts`

Add a `CmgRefreshStatus` interface mirroring the backend response from `load_refresh_status()`:

```ts
export interface CmgRefreshStatus {
  status: "idle" | "running" | "succeeded" | "failed";
  is_running: boolean;
  last_started_at: string | null;
  last_completed_at: string | null;
  last_successful_at: string | null;
  trigger: string | null;
  recommended_cadence: string;
  summary: {
    checked_item_count: number;
    new_count: number;
    updated_count: number;
    unchanged_count: number;
    error_count: number;
  } | null;
  last_error: string | null;
}
```

### `src/renderer/providers/SettingsProvider.tsx`

Additions to the provider:

1. **State:** `cmgRefreshStatus: CmgRefreshStatus | null` (initially null), `cmgRefreshLoading: boolean`.
2. **Fetch function:** `fetchCmgStatus()` — calls `GET /settings/cmg-refresh`, updates `cmgRefreshStatus`, sets `cmgRefreshLoading`.
3. **Polling effect:** `useEffect` that calls `fetchCmgStatus()` on mount. If `cmgRefreshStatus?.status === "running"`, sets a 5-second interval to re-fetch. Clears the interval when status changes away from running or on unmount. Uses `useRef` for the interval ID.
4. **Action:** `startCmgRefresh(): Promise<void>` — calls `POST /settings/cmg-refresh/run`. On success, immediately sets `cmgRefreshStatus` to `{ status: "running", is_running: true }` and lets the polling effect take over. On 409 (already running), sets error. On other errors, sets error.
5. **Context interface** gains: `cmgRefreshStatus`, `cmgRefreshLoading`, `startCmgRefresh`.

### `src/renderer/pages/Settings.tsx`

Expand the Data Management section (lines 398-410). Current structure:

```
Data Management
[Re-run Pipeline] [Clear Vector Store]
```

New structure:

```
Data Management
[status line if last_successful_at exists]
  "Last refreshed: <formatted date> · Recommended: <cadence>"
[summary line if cmgRefreshStatus.summary exists]
  "<checked> checked · <new> new · <updated> updated · <errors> errors"
[running indicator if is_running]
  "Refreshing CMGs..." in on-surface-variant mono text
[error notice if last_error is set]
  last_error text in status-critical mono text
[Re-run Pipeline] [Refresh CMGs] [Clear Vector Store]
```

**Refresh CMGs button:** `variant="secondary"`. Disabled when `cmgRefreshStatus?.is_running` is true. Label changes to "Refreshing CMGs..." when running. On click, calls `startCmgRefresh()`.

**Date formatting:** Parse `last_successful_at` (ISO 8601) and format as a short readable date (e.g. "5 Apr 2026"). Use `Date` built-in parsing, no library dependency.

**Error state:** If `cmgRefreshStatus?.last_error` is set and `status === "failed"`, display the error string in `text-status-critical` colour.

## What This Does Not Include

- No toast/notification system for completion (user sees status on the Settings page).
- No automatic/scheduled refresh trigger (the recommended_cadence is display-only).
- No frontend test changes (no existing Settings UI tests to extend).
- No backend changes.
