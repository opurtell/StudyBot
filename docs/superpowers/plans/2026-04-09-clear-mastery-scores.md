# Clear Mastery Scores — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-facing option to permanently clear all quiz history and reset mastery scores, surfaced on both Dashboard and Settings.

**Architecture:** One new `Tracker.clear_mastery_data()` method, one new `POST /quiz/mastery/clear` endpoint, a `clearMastery()` method on `SettingsProvider`, and confirmation-driven buttons on Dashboard and Settings.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Tailwind (frontend), SQLite (data), vitest/pytest (tests)

---

### Task 1: Add `clear_mastery_data()` to Tracker

**Files:**
- Modify: `src/python/quiz/tracker.py:42` (after `_init_schema`)
- Test: `tests/quiz/test_tracker.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/quiz/test_tracker.py`:

```python
def test_clear_mastery_data_removes_history_and_categories(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "recall", "incorrect", 30.0, "CMG 7")
    assert len(tracker.get_mastery()) == 2
    assert len(tracker.get_recent_history(limit=10)) == 2

    deleted = tracker.clear_mastery_data()

    assert deleted == 2
    assert tracker.get_mastery() == []
    assert tracker.get_recent_history(limit=10) == []
    assert tracker.get_streak() == 0
    assert tracker.get_accuracy() == 0.0


def test_clear_mastery_data_preserves_blacklist(tracker):
    tracker.add_to_blacklist("Paediatrics")
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.clear_mastery_data()
    assert tracker.get_blacklist() == ["Paediatrics"]


def test_clear_mastery_data_empty_db(tracker):
    deleted = tracker.clear_mastery_data()
    assert deleted == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/python && python -m pytest tests/quiz/test_tracker.py::test_clear_mastery_data_removes_history_and_categories tests/quiz/test_tracker.py::test_clear_mastery_data_preserves_blacklist tests/quiz/test_tracker.py::test_clear_mastery_data_empty_db -v`
Expected: FAIL — `AttributeError: 'Tracker' object has no attribute 'clear_mastery_data'`

- [ ] **Step 3: Implement `clear_mastery_data()`**

Add after `_init_schema()` in `src/python/quiz/tracker.py` (after line 42):

```python
    def clear_mastery_data(self) -> int:
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM quiz_history").fetchone()[0]
            self._conn.execute("DELETE FROM quiz_history")
            self._conn.execute("DELETE FROM categories")
            self._conn.commit()
        return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/python && python -m pytest tests/quiz/test_tracker.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/quiz/tracker.py tests/quiz/test_tracker.py
git commit -m "feat: add Tracker.clear_mastery_data() to wipe quiz history"
```

---

### Task 2: Add `POST /quiz/mastery/clear` endpoint

**Files:**
- Modify: `src/python/quiz/router.py:245` (after last endpoint)
- Test: `tests/quiz/test_router.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/quiz/test_router.py`:

```python
def test_clear_mastery(client):
    # Seed some mastery data via the quiz flow
    client.post("/quiz/session/start", json={"mode": "random"})
    # Record directly via tracker since the full quiz flow needs LLM
    from quiz.tracker import Tracker
    tracker = Tracker()
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")

    response = client.post("/quiz/mastery/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["deleted_history"] >= 1

    # Verify mastery is empty
    mastery = client.get("/quiz/mastery")
    assert mastery.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/python && python -m pytest tests/quiz/test_router.py::test_clear_mastery -v`
Expected: FAIL — 404 or `AttributeError`

- [ ] **Step 3: Implement the endpoint**

Add after the last endpoint in `src/python/quiz/router.py` (after line 245):

```python
@router.post("/mastery/clear")
def clear_mastery() -> dict:
    tracker = _get_tracker()
    deleted = tracker.clear_mastery_data()
    return {"status": "ok", "deleted_history": deleted}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/python && python -m pytest tests/quiz/test_router.py::test_clear_mastery -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/quiz/router.py tests/quiz/test_router.py
git commit -m "feat: add POST /quiz/mastery/clear endpoint"
```

---

### Task 3: Add `clearMastery()` to SettingsProvider

**Files:**
- Modify: `src/renderer/providers/SettingsProvider.tsx`

- [ ] **Step 1: Add `clearMastery` to the interface**

In `src/renderer/providers/SettingsProvider.tsx`, add to `SettingsContextValue` interface (after `clearSourceType` on line 28):

```typescript
  clearMastery: () => Promise<void>;
```

- [ ] **Step 2: Implement the callback**

Add after `clearSourceType` callback (after line 141):

```typescript
  const clearMastery = useCallback(async () => {
    setActionError(null);
    try {
      await apiPost("/quiz/mastery/clear");
      store.invalidate("/quiz/dashboard-mastery");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Failed to clear mastery data"));
    }
  }, [store]);
```

- [ ] **Step 3: Add to the context value**

In the `value` object (around line 268), add `clearMastery`:

```typescript
      clearMastery,
```

And in the `useMemo` dependency array (around line 291), add `clearMastery`.

- [ ] **Step 4: Commit**

```bash
git add src/renderer/providers/SettingsProvider.tsx
git commit -m "feat: add clearMastery() to SettingsProvider with cache invalidation"
```

---

### Task 4: Add "Clear Mastery & Quiz History" button to Settings

**Files:**
- Modify: `src/renderer/pages/Settings.tsx`

- [ ] **Step 1: Add imports and state**

At the top of `Settings.tsx`, add `Modal` to imports (after the `Button` import):

```typescript
import Modal from "../components/Modal";
```

Add state inside the `Settings` function (after existing `useState` declarations, around line 103):

```typescript
  const [showClearMastery, setShowClearMastery] = useState(false);
```

Destructure `clearMastery` from `useSettings()` (add it to the existing destructuring on line 64).

- [ ] **Step 2: Add the button and modal**

In the Indexed Data section, add a new row after the "Personal Notes" row (after line 508), before the nuclear clear:

```tsx
          {/* Mastery data row */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-label text-label-sm text-on-surface">Mastery &amp; Quiz History</span>
              <span className="font-mono text-[10px] text-on-surface-variant ml-2">
                Quiz scores and progress tracking
              </span>
            </div>
            <Button variant="tertiary" onClick={() => setShowClearMastery(true)}>
              Clear
            </Button>
          </div>
```

Add the confirmation modal before the closing `</div>` of the root element (before the final `</div>` around line 528):

```tsx
      <Modal isOpen={showClearMastery} onClose={() => setShowClearMastery(false)}>
        <div className="space-y-4">
          <h3 className="font-headline text-title-lg text-primary">
            Clear Mastery &amp; Quiz History
          </h3>
          <p className="font-body text-body-sm text-on-surface-variant">
            This will permanently delete all quiz history and reset mastery scores to zero. This cannot be undone.
          </p>
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" onClick={() => setShowClearMastery(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                await clearMastery();
                setShowClearMastery(false);
              }}
            >
              Clear Mastery
            </Button>
          </div>
        </div>
      </Modal>
```

- [ ] **Step 3: Commit**

```bash
git add src/renderer/pages/Settings.tsx
git commit -m "feat: add Clear Mastery & Quiz History button to Settings"
```

---

### Task 5: Add reset button to Dashboard near Knowledge Heatmap

**Files:**
- Modify: `src/renderer/pages/Dashboard.tsx`

- [ ] **Step 1: Add imports and state**

Add `Modal` and `useSettings` to imports in `Dashboard.tsx`:

```typescript
import Modal from "../components/Modal";
import { useSettings } from "../hooks/useSettings";
```

Add `useState` import (it should already be available via React, but confirm):

Add inside the `Dashboard` function (after the existing hooks, around line 17):

```typescript
  const { clearMastery } = useSettings();
  const [showClearMastery, setShowClearMastery] = useState(false);
```

Note: `useState` needs to be added to the React import. Check the current import — if it's not there, add it:

```typescript
import { useState } from "react";
```

- [ ] **Step 2: Add the reset icon button**

Replace the "Knowledge Heatmap" heading block (lines 117-120):

```tsx
          <div className="flex items-center justify-between">
            <h3 className="font-label text-label-sm text-on-surface-variant">
              Knowledge Heatmap
            </h3>
            <button
              onClick={() => setShowClearMastery(true)}
              className="p-1 text-on-surface-variant hover:text-primary transition-colors"
              title="Reset mastery scores"
            >
              <span className="material-symbols-outlined text-sm">restart_alt</span>
            </button>
          </div>
```

- [ ] **Step 3: Add the confirmation modal**

Before the closing `</div>` of the root return (before the very last `</div>` around line 164):

```tsx
      <Modal isOpen={showClearMastery} onClose={() => setShowClearMastery(false)}>
        <div className="space-y-4">
          <h3 className="font-headline text-title-lg text-primary">
            Clear Mastery &amp; Quiz History
          </h3>
          <p className="font-body text-body-sm text-on-surface-variant">
            This will permanently delete all quiz history and reset mastery scores to zero. This cannot be undone.
          </p>
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" onClick={() => setShowClearMastery(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                await clearMastery();
                setShowClearMastery(false);
                refetch();
                refetchHistory();
              }}
            >
              Clear Mastery
            </Button>
          </div>
        </div>
      </Modal>
```

- [ ] **Step 4: Commit**

```bash
git add src/renderer/pages/Dashboard.tsx
git commit -m "feat: add reset mastery button to Dashboard heatmap section"
```
