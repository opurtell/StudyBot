# Session Start Category Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two hard-coded Cardiac/Trauma focus buttons with a scrollable grid of 16 categories (14 CMG sections + Medications + Clinical Skills), backed by metadata-filtered retrieval.

**Architecture:** Backend `_resolve_mode` returns a `{"section": topic}` filter dict for topic mode, which the retriever already supports. Frontend gets a static category grid replacing the old buttons.

**Tech Stack:** Python 3.10+ / FastAPI (backend), React 19 / TypeScript / Tailwind CSS 3 (frontend), pytest + vitest

---

### Task 1: Add metadata filter to `_resolve_mode` for topic mode

**Files:**
- Modify: `src/python/quiz/agent.py:173-179`

- [ ] **Step 1: Write the failing test**

Add to `tests/quiz/test_agent.py` in the `TestGenerateQuestion` class:

```python
def test_topic_mode_passes_section_filter_to_retriever(self):
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()

    mock_retriever.retrieve.return_value = _make_chunks()
    mock_llm.complete.return_value = json.dumps(
        {
            "question_text": "Test?",
            "question_type": "recall",
            "source_citation": "CMG 14",
            "category": "Cardiac",
        }
    )

    generate_question(
        mode="topic",
        topic="Cardiac",
        llm=mock_llm,
        retriever=mock_retriever,
        tracker=mock_tracker,
    )
    call_kwargs = mock_retriever.retrieve.call_args.kwargs
    assert call_kwargs["filters"] == {"section": "Cardiac"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_agent.py::TestGenerateQuestion::test_topic_mode_passes_section_filter_to_retriever -v`
Expected: FAIL — `filters` kwarg will be `None`, not `{"section": "Cardiac"}`

- [ ] **Step 3: Write minimal implementation**

In `src/python/quiz/agent.py`, change `_resolve_mode` line 179 from:

```python
        return topic, None
```

to:

```python
        return topic, {"section": topic}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_agent.py::TestGenerateQuestion::test_topic_mode_passes_section_filter_to_retriever -v`
Expected: PASS

- [ ] **Step 5: Run full agent test suite**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_agent.py -v`
Expected: All tests pass

---

### Task 2: Add seeded Medicine chunks to test conftest

**Files:**
- Modify: `tests/quiz/conftest.py`

- [ ] **Step 1: Add medicine chunk to seeded_chroma fixture**

In `tests/quiz/conftest.py`, after the existing `cmgs.add(...)` call, add a medicine chunk to the `cmg_guidelines` collection:

```python
    cmgs.add(
        ids=["med_1"],
        documents=[
            "Adrenaline (epinephrine) 1:10 000. Indication: cardiac arrest. Dose: 1 mg IV/IO every 3-5 minutes.",
        ],
        metadatas=[
            {
                "source_type": "cmg",
                "source_file": "CMG_03_Adrenaline.json",
                "cmg_number": "03",
                "section": "Medicine",
                "chunk_type": "dosage",
                "last_modified": "2024-01-01",
            },
        ],
    )
```

- [ ] **Step 2: Run existing retriever tests to verify nothing broke**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_retriever.py -v`
Expected: All tests pass

---

### Task 3: Add retriever test for section metadata filter

**Files:**
- Modify: `tests/quiz/test_retriever.py`

- [ ] **Step 1: Write the test**

Add to `tests/quiz/test_retriever.py`:

```python
def test_retrieve_with_section_filter(retriever):
    results = retriever.retrieve("adrenaline", n=5, filters={"section": "Cardiac"})
    assert len(results) > 0
    for r in results:
        assert r.category == "Cardiac"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_retriever.py::test_retrieve_with_section_filter -v`
Expected: PASS — retriever already passes `base_filters` through to ChromaDB

- [ ] **Step 3: Add test for Medicine section filter**

```python
def test_retrieve_medicine_section_filter(retriever):
    results = retriever.retrieve("adrenaline dose", n=5, filters={"section": "Medicine"})
    assert len(results) > 0
    for r in results:
        assert r.category == "Medicine"
```

- [ ] **Step 4: Run test**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_retriever.py::test_retrieve_medicine_section_filter -v`
Expected: PASS

---

### Task 4: Add topic session start test with section filter

**Files:**
- Modify: `tests/quiz/test_router.py`

- [ ] **Step 1: Write the test**

Add to `tests/quiz/test_router.py` in `TestSessionStart`:

```python
def test_start_topic_session_returns_200(self, client):
    response = client.post(
        "/quiz/session/start",
        json={
            "mode": "topic",
            "topic": "Medicine",
            "difficulty": "medium",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "topic"
```

- [ ] **Step 2: Run test**

Run: `PYTHONPATH=src/python python3 -m pytest tests/quiz/test_router.py::TestSessionStart::test_start_topic_session_returns_200 -v`
Expected: PASS

---

### Task 5: Replace Cardiac/Trauma buttons with category grid on frontend

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx:79-95`

- [ ] **Step 1: Add category constant and replace button section**

Replace lines 79-95 in `src/renderer/pages/Quiz.tsx`. The new code adds a `QUIZ_CATEGORIES` constant and renders a grid of focus session buttons:

```tsx
const QUIZ_CATEGORIES = [
  { display: "Cardiac", section: "Cardiac" },
  { display: "Trauma", section: "Trauma" },
  { display: "Medical", section: "Medical" },
  { display: "Respiratory", section: "Respiratory" },
  { display: "Airway Management", section: "Airway Management" },
  { display: "Paediatrics", section: "Paediatric" },
  { display: "Obstetric", section: "Obstetric" },
  { display: "Neurology", section: "Neurology" },
  { display: "Behavioural", section: "Behavioural" },
  { display: "Toxicology", section: "Toxicology" },
  { display: "Environmental", section: "Environmental" },
  { display: "Pain Management", section: "Pain Management" },
  { display: "Palliative Care", section: "Palliative Care" },
  { display: "HAZMAT", section: "HAZMAT" },
  { display: "General Care", section: "General Care" },
  { display: "Medications", section: "Medicine" },
  { display: "Clinical Skills", section: "Clinical Skill" },
];
```

Then replace the button section (lines 79-95) with:

```tsx
          <div className="flex flex-col gap-3 max-w-xs mx-auto pt-4">
            <Button onClick={() => session.startSession({ mode: "random", randomize })}>
              Random Session
            </Button>
            <Button onClick={() => session.startSession({ mode: "gap_driven", randomize })} variant="secondary">
              Gap-Driven Session
            </Button>
          </div>

          <div className="pt-8">
            <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">
              Focus Sessions
            </span>
            <div className="grid grid-cols-3 gap-2 pt-3 max-w-sm mx-auto">
              {QUIZ_CATEGORIES.map((cat) => (
                <button
                  key={cat.section}
                  onClick={() => session.startSession({ mode: "topic", topic: cat.section, randomize })}
                  className="px-3 py-2 font-label text-[10px] uppercase tracking-wider transition-colors border border-outline-variant/20 bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest hover:text-primary"
                >
                  {cat.display}
                </button>
              ))}
            </div>
          </div>

          <div className="pt-6 max-w-xs mx-auto">
            <Button onClick={handleExit} variant="tertiary">
              Return to Archive
            </Button>
          </div>
```

- [ ] **Step 2: Run TypeScript type check**

Run: `npx tsc --noEmit`
Expected: No new errors related to Quiz.tsx

---

### Task 6: Verify end-to-end with existing tests

- [ ] **Step 1: Run full Python test suite**

Run: `PYTHONPATH=src/python python3 -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run TypeScript type check**

Run: `npx tsc --noEmit`
Expected: No new errors
