# CMG Refresh Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing backend CMG refresh endpoints into the Settings page so users can trigger a refresh and see its status.

**Architecture:** Three-file frontend-only change. Add a TypeScript type, extend the SettingsProvider with status polling and a start action, and expand the Settings page Data Management section to display status and a trigger button.

**Tech Stack:** React 19, TypeScript 5, Tailwind CSS 3, existing apiClient helpers

**Spec:** `docs/superpowers/specs/2026-04-05-cmg-refresh-settings-ui-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/renderer/types/api.ts` | Modify | Add `CmgRefreshStatus` interface |
| `src/renderer/providers/SettingsProvider.tsx` | Modify | Add polling, state, and `startCmgRefresh` action |
| `src/renderer/pages/Settings.tsx` | Modify | Expand Data Management section with status display and Refresh CMGs button |

---

### Task 1: Add CmgRefreshStatus type

**Files:**
- Modify: `src/renderer/types/api.ts` (append after line 170)

- [ ] **Step 1: Add the interface to api.ts**

After the closing `}` of `LibraryStatusResponse` (line 170), append:

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

- [ ] **Step 2: Run typecheck**

Run: `npx tsc --noEmit`
Expected: PASS (no consumers yet, type-only addition)

- [ ] **Step 3: Commit**

```bash
git add src/renderer/types/api.ts
git commit -m "feat: add CmgRefreshStatus type for settings UI"
```

---

### Task 2: Extend SettingsProvider with CMG refresh state and polling

**Files:**
- Modify: `src/renderer/providers/SettingsProvider.tsx`

- [ ] **Step 1: Add import for CmgRefreshStatus**

In the import block at line 12, change:

```ts
import type { ModelRegistry, SettingsConfig } from "../types/api";
```

to:

```ts
import type { CmgRefreshStatus, ModelRegistry, SettingsConfig } from "../types/api";
```

- [ ] **Step 2: Extend the context interface**

In `SettingsContextValue` (lines 14-27), add three new members after `clearVectorStore`:

```ts
  cmgRefreshStatus: CmgRefreshStatus | null;
  cmgRefreshLoading: boolean;
  startCmgRefresh: () => Promise<void>;
```

- [ ] **Step 3: Add state and ref declarations**

After line 38 (`const [actionError, setActionError] = useState<string | null>(null);`), add:

```ts
  const [cmgRefreshStatus, setCmgRefreshStatus] = useState<CmgRefreshStatus | null>(null);
  const [cmgRefreshLoading, setCmgRefreshLoading] = useState(false);
  const cmgPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

Also add `useRef` to the React import on line 1 — change:

```ts
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
```

to:

```ts
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
```

- [ ] **Step 4: Add the fetch and polling effect**

After the `clearVectorStore` callback (after line 105), add:

```ts
  const fetchCmgStatus = useCallback(async () => {
    try {
      const data = await apiGet<CmgRefreshStatus>("/settings/cmg-refresh");
      setCmgRefreshStatus(data);
    } catch {
      setCmgRefreshLoading(false);
    }
  }, []);

  useEffect(() => {
    setCmgRefreshLoading(true);
    fetchCmgStatus().finally(() => setCmgRefreshLoading(false));

    return () => {
      if (cmgPollRef.current !== null) {
        clearInterval(cmgPollRef.current);
        cmgPollRef.current = null;
      }
    };
  }, [fetchCmgStatus]);

  useEffect(() => {
    if (cmgRefreshStatus?.is_running) {
      if (cmgPollRef.current !== null) return;
      cmgPollRef.current = setInterval(() => {
        fetchCmgStatus();
      }, 5000);
    } else {
      if (cmgPollRef.current !== null) {
        clearInterval(cmgPollRef.current);
        cmgPollRef.current = null;
      }
    }
  }, [cmgRefreshStatus?.is_running, fetchCmgStatus]);
```

- [ ] **Step 5: Add the startCmgRefresh callback**

After the polling effect, add:

```ts
  const startCmgRefresh = useCallback(async () => {
    setActionError(null);
    try {
      await apiPost("/settings/cmg-refresh/run");
      setCmgRefreshStatus((prev) =>
        prev ? { ...prev, status: "running", is_running: true } : prev
      );
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Failed to start CMG refresh"));
    }
  }, []);
```

- [ ] **Step 6: Add new fields to the useMemo value**

In the `useMemo` block (lines 112-141), add to the returned object after `clearVectorStore`:

```ts
      cmgRefreshStatus,
      cmgRefreshLoading,
      startCmgRefresh,
```

And add to the dependency array:

```ts
      cmgRefreshStatus,
      cmgRefreshLoading,
      startCmgRefresh,
```

- [ ] **Step 7: Run typecheck**

Run: `npx tsc --noEmit`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/renderer/providers/SettingsProvider.tsx
git commit -m "feat: add CMG refresh state and polling to SettingsProvider"
```

---

### Task 3: Expand Settings Data Management section

**Files:**
- Modify: `src/renderer/pages/Settings.tsx`

- [ ] **Step 1: Destructure new fields from useSettings**

In the destructuring block (lines 64-76), add after `clearVectorStore`:

```ts
    cmgRefreshStatus,
    cmgRefreshLoading,
    startCmgRefresh,
```

- [ ] **Step 2: Replace the Data Management section**

Replace lines 398-410 (the entire Data Management section) with:

```tsx
      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Data Management
        </h3>
        {cmgRefreshStatus?.last_successful_at && (
          <p className="font-mono text-[10px] text-on-surface-variant">
            Last refreshed: {new Date(cmgRefreshStatus.last_successful_at).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })} · Recommended: {cmgRefreshStatus.recommended_cadence}
          </p>
        )}
        {cmgRefreshStatus?.summary && (
          <p className="font-mono text-[10px] text-on-surface-variant">
            {cmgRefreshStatus.summary.checked_item_count} checked · {cmgRefreshStatus.summary.new_count} new · {cmgRefreshStatus.summary.updated_count} updated · {cmgRefreshStatus.summary.error_count} errors
          </p>
        )}
        {cmgRefreshStatus?.is_running && (
          <p className="font-mono text-[10px] text-on-surface-variant">
            Refreshing CMGs...
          </p>
        )}
        {cmgRefreshStatus?.status === "failed" && cmgRefreshStatus.last_error && (
          <p className="font-mono text-[10px] text-status-critical">
            {cmgRefreshStatus.last_error}
          </p>
        )}
        <div className="flex gap-4">
          <Button variant="secondary" onClick={rerunPipeline}>
            Re-run Pipeline
          </Button>
          <Button
            variant="secondary"
            onClick={startCmgRefresh}
            disabled={cmgRefreshStatus?.is_running ?? cmgRefreshLoading}
          >
            {cmgRefreshStatus?.is_running ? "Refreshing CMGs..." : "Refresh CMGs"}
          </Button>
          <Button variant="tertiary" onClick={clearVectorStore}>
            Clear Vector Store
          </Button>
        </div>
      </section>
```

- [ ] **Step 3: Run typecheck**

Run: `npx tsc --noEmit`
Expected: PASS

- [ ] **Step 4: Run frontend tests**

Run: `npx vitest run`
Expected: PASS (no existing Settings tests should break)

- [ ] **Step 5: Commit**

```bash
git add src/renderer/pages/Settings.tsx
git commit -m "feat: wire CMG refresh into Settings Data Management section"
```

---

## Self-Review

**Spec coverage:**
- CmgRefreshStatus type: Task 1 — covers spec section "Types"
- Provider polling + startCmgRefresh: Task 2 — covers "SettingsProvider changes"
- Settings UI with status, summary, error, button: Task 3 — covers "Settings.tsx Data Management section"
- Date formatting (en-AU locale): Task 3 — covers spec's "short readable date" requirement
- Error via existing actionError pattern: Task 2 step 5 — consistent with rerunPipeline/clearVectorStore

**Placeholder scan:** No TBD, TODO, or vague instructions. Every step has exact code.

**Type consistency:** `CmgRefreshStatus` is defined in Task 1, imported in Task 2, consumed via context in Task 3. Property names (`is_running`, `last_successful_at`, `recommended_cadence`, `summary`, `last_error`, `status`) match across all tasks.
