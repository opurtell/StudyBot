# Quiz Start Two-Tier Grid — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two stacked main session buttons with a 5-button top-tier grid, adding Clinical Guidelines, Medication Guidelines, and Clinical Skills as broad-start options.

**Architecture:** New `clinical_guidelines` mode in the backend picks a random clinical topic as the semantic query but filters ChromaDB results to only the 15 clinical guideline sections. Frontend reorganises existing buttons into a 5-column top grid + unchanged Focus Sessions grid below.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Tailwind (frontend), ChromaDB ($in where filter)

---

### Task 1: Add `clinical_guidelines` mode to backend

**Files:**
- Modify: `src/python/quiz/agent.py:177-210`
- Create: `tests/quiz/test_agent_resolve_mode.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/quiz/test_agent_resolve_mode.py
from unittest.mock import MagicMock

import pytest

from quiz.agent import _resolve_mode
from quiz.tracker import Tracker


@pytest.fixture
def tracker():
    return MagicMock(spec=Tracker)


class TestResolveMode:
    def test_topic_mode_returns_section_filter(self, tracker):
        query, filters = _resolve_mode("topic", "Cardiac", tracker)
        assert query == "Cardiac"
        assert filters == {"section": "Cardiac"}

    def test_topic_mode_raises_without_topic(self, tracker):
        with pytest.raises(ValueError, match="Topic mode requires a topic"):
            _resolve_mode("topic", None, tracker)

    def test_gap_driven_uses_weak_category(self, tracker):
        tracker.get_weak_categories.return_value = ["Trauma"]
        query, filters = _resolve_mode("gap_driven", None, tracker)
        assert query == "Trauma"
        assert filters is None

    def test_gap_driven_falls_back_random(self, tracker):
        tracker.get_weak_categories.return_value = []
        query, filters = _resolve_mode("gap_driven", None, tracker)
        assert query in ["Cardiac", "Trauma", "Respiratory"]
        assert filters is None

    def test_random_mode_returns_query_no_filter(self, tracker):
        query, filters = _resolve_mode("random", None, tracker)
        assert isinstance(query, str)
        assert len(query) > 0
        assert filters is None

    def test_clinical_guidelines_returns_query_and_in_filter(self, tracker):
        expected_sections = {
            "Cardiac", "Trauma", "Medical", "Respiratory", "Airway Management",
            "Paediatric", "Obstetric", "Neurology", "Behavioural", "Toxicology",
            "Environmental", "Pain Management", "Palliative Care", "HAZMAT",
            "General Care",
        }
        query, filters = _resolve_mode("clinical_guidelines", None, tracker)
        assert query in expected_sections
        assert filters is not None
        assert filters == {"section": {"$in": sorted(expected_sections)}}

    def test_unknown_mode_raises(self, tracker):
        with pytest.raises(ValueError, match="Unknown mode"):
            _resolve_mode("nonexistent", None, tracker)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_agent_resolve_mode.py -v`
Expected: FAIL — `ValueError: Unknown mode: clinical_guidelines`

- [ ] **Step 3: Write minimal implementation**

In `src/python/quiz/agent.py`, add a new `elif` branch in `_resolve_mode` before the `else` clause (after the `random` branch, before line 209):

```python
    elif mode == "clinical_guidelines":
        clinical_sections = sorted([
            "Cardiac", "Trauma", "Medical", "Respiratory", "Airway Management",
            "Paediatric", "Obstetric", "Neurology", "Behavioural", "Toxicology",
            "Environmental", "Pain Management", "Palliative Care", "HAZMAT",
            "General Care",
        ])
        query = random.choice(clinical_sections)
        return query, {"section": {"$in": clinical_sections}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_agent_resolve_mode.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run full backend test suite**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/ -v`
Expected: All tests PASS (new + existing)

- [ ] **Step 6: Commit**

```bash
git add src/python/quiz/agent.py tests/quiz/test_agent_resolve_mode.py
git commit -m "feat: add clinical_guidelines quiz mode with section filter"
```

---

### Task 2: Verify retriever handles `$in` filter correctly

**Files:**
- Modify: `src/python/quiz/retriever.py:88-94` (no functional change, just verify)
- Create: `tests/quiz/test_retriever_filters.py`

- [ ] **Step 1: Write a test confirming the retriever passes `$in` filters through to ChromaDB**

```python
# tests/quiz/test_retriever_filters.py
from unittest.mock import MagicMock, patch

from quiz.retriever import Retriever


def test_build_where_passes_in_filter_to_cmgs():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client)

    filters = {"section": {"$in": ["Cardiac", "Trauma"]}}
    where = retriever._build_where(filters, exclude=None, collection="cmgs")

    assert where == {"section": {"$in": ["Cardiac", "Trauma"]}}
```

- [ ] **Step 2: Run test**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_retriever_filters.py -v`
Expected: PASS — the `_build_where` method already passes filter values through as-is for the CMGs collection (line 94: `conditions.append({key: value})`).

- [ ] **Step 3: Commit**

```bash
git add tests/quiz/test_retriever_filters.py
git commit -m "test: verify retriever passes $in filter to ChromaDB"
```

---

### Task 3: Update frontend types

**Files:**
- Modify: `src/renderer/types/api.ts:22-23`

- [ ] **Step 1: Widen the `mode` type to include the new mode**

Change line 23 from:
```typescript
  mode: "topic" | "gap_driven" | "random";
```
to:
```typescript
  mode: "topic" | "gap_driven" | "random" | "clinical_guidelines";
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/renderer/types/api.ts
git commit -m "feat: add clinical_guidelines to StartSessionRequest mode type"
```

---

### Task 4: Restructure the quiz start screen UI

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx:79-207` (shortcuts + idle screen)

- [ ] **Step 1: Add keyboard shortcuts 3, 4, 5 for the new buttons**

In the `useQuizShortcuts` array (after the shortcut with key `"2"`, around line 93), add three new shortcuts:

```typescript
    {
      key: "3",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "clinical_guidelines", randomize });
      },
    },
    {
      key: "4",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "topic", topic: "Medicine", randomize });
      },
    },
    {
      key: "5",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "topic", topic: "Clinical Skill", randomize });
      },
    },
```

- [ ] **Step 2: Replace the two-button stack with a 5-button top-tier grid**

Replace the `<div className="flex flex-col gap-3 max-w-xs mx-auto pt-4">` block (lines 189–207) with:

```tsx
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 max-w-2xl mx-auto pt-4">
            <Button
              onClick={() => session.startSession({ mode: "random", randomize })}
              aria-keyshortcuts="1"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Random
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">1</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "gap_driven", randomize })}
              variant="secondary"
              aria-keyshortcuts="2"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Gap-Driven
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">2</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "clinical_guidelines", randomize })}
              variant="secondary"
              aria-keyshortcuts="3"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Clinical Guidelines
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">3</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "topic", topic: "Medicine", randomize })}
              variant="secondary"
              aria-keyshortcuts="4"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Medication Guidelines
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">4</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "topic", topic: "Clinical Skill", randomize })}
              variant="secondary"
              aria-keyshortcuts="5"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Clinical Skills
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">5</span>
            </Button>
          </div>
```

- [ ] **Step 3: Verify TypeScript compiles and frontend tests pass**

Run: `npx tsc --noEmit && npx vitest run`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/renderer/pages/Quiz.tsx
git commit -m "feat: two-tier quiz start grid with 5 top-level session options"
```

---

### Task 5: Add backend session-start test for clinical_guidelines mode

**Files:**
- Modify: `tests/quiz/test_router.py:63-89`

- [ ] **Step 1: Add test to existing TestSessionStart class**

Append to the `TestSessionStart` class in `tests/quiz/test_router.py`:

```python
    def test_start_clinical_guidelines_session_returns_200(self, client):
        response = client.post(
            "/quiz/session/start",
            json={
                "mode": "clinical_guidelines",
                "topic": None,
                "difficulty": "medium",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "clinical_guidelines"
```

- [ ] **Step 2: Run quiz tests**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/quiz/test_router.py
git commit -m "test: add clinical_guidelines session start integration test"
```
