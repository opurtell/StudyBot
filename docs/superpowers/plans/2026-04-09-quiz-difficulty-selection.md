# Quiz Difficulty Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Easy / Medium / Hard difficulty picker to the quiz start screen that adjusts question complexity via LLM prompt instructions.

**Architecture:** The backend already accepts and stores difficulty. We add a UI toggle on the quiz idle screen, wire it through to `startSession()`, and enhance the generation prompt with difficulty-specific instructions.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 3, Python/FastAPI, pytest, vitest

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `src/python/quiz/agent.py:12-32,100` | Add difficulty-specific prompt instructions |
| Modify | `src/renderer/pages/Quiz.tsx:33,226-254,256-326` | Add difficulty state + UI toggle + pass to startSession |
| Modify | `tests/quiz/test_agent.py` | Test difficulty prompt injection |
| Modify | `tests/renderer/Quiz.test.tsx` | Test difficulty UI toggle |

---

### Task 1: Add difficulty-specific prompt instructions to backend

**Files:**
- Modify: `src/python/quiz/agent.py:12-32,100`
- Modify: `tests/quiz/test_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/quiz/test_agent.py` inside `TestGenerateQuestion`:

```python
def test_difficulty_easy_adds_easy_instructions(self):
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
        difficulty="easy",
        llm=mock_llm,
        retriever=mock_retriever,
        tracker=mock_tracker,
    )

    call_args = mock_llm.complete.call_args[0][0]
    user_msg = [m for m in call_args if m["role"] == "user"][0]["content"]
    assert "straightforward recall" in user_msg
    assert "single-fact" in user_msg

def test_difficulty_hard_adds_hard_instructions(self):
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
        difficulty="hard",
        llm=mock_llm,
        retriever=mock_retriever,
        tracker=mock_tracker,
    )

    call_args = mock_llm.complete.call_args[0][0]
    user_msg = [m for m in call_args if m["role"] == "user"][0]["content"]
    assert "multi-step scenario" in user_msg
    assert "2+ clinical concepts" in user_msg

def test_difficulty_medium_adds_no_extra_instructions(self):
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
        difficulty="medium",
        llm=mock_llm,
        retriever=mock_retriever,
        tracker=mock_tracker,
    )

    call_args = mock_llm.complete.call_args[0][0]
    user_msg = [m for m in call_args if m["role"] == "user"][0]["content"]
    assert "straightforward recall" not in user_msg
    assert "multi-step scenario" not in user_msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/quiz/test_agent.py::TestGenerateQuestion::test_difficulty_easy_adds_easy_instructions tests/quiz/test_agent.py::TestGenerateQuestion::test_difficulty_hard_adds_hard_instructions tests/quiz/test_agent.py::TestGenerateQuestion::test_difficulty_medium_adds_no_extra_instructions -v`
Expected: FAIL — the current `user_content` only appends `"Difficulty: {difficulty}"`, not the instruction strings.

- [ ] **Step 3: Write minimal implementation**

In `src/python/quiz/agent.py`, add the difficulty instructions map after the prompt constants (after line 51):

```python
DIFFICULTY_INSTRUCTIONS = {
    "easy": (
        "Difficulty adjustment: Ask straightforward recall questions — "
        "single-fact definitions, drug names, basic indications. "
        "The answer should be 1-2 sentences maximum."
    ),
    "medium": "",
    "hard": (
        "Difficulty adjustment: Ask multi-step scenario questions requiring "
        "integration of 2+ clinical concepts. Include patient context "
        "(age, vitals, presentation). Expect detailed structured answers "
        "covering assessment, treatment rationale, and dose calculations "
        "where relevant."
    ),
}
```

Then modify the `user_content` construction in `generate_question` (around line 100). Replace:

```python
    user_content = f"Source material:\n\n{source_text}\n\nDifficulty: {difficulty}"
```

With:

```python
    user_content = f"Source material:\n\n{source_text}\n\nDifficulty: {difficulty}"
    difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, "")
    if difficulty_instruction:
        user_content += f"\n\n{difficulty_instruction}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/quiz/test_agent.py::TestGenerateQuestion::test_difficulty_easy_adds_easy_instructions tests/quiz/test_agent.py::TestGenerateQuestion::test_difficulty_hard_adds_hard_instructions tests/quiz/test_agent.py::TestGenerateQuestion::test_difficulty_medium_adds_no_extra_instructions -v`
Expected: PASS

- [ ] **Step 5: Run full quiz test suite**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/quiz/ -v`
Expected: All existing tests still pass (difficulty default is "medium" which now appends empty string).

- [ ] **Step 6: Commit**

```bash
git add src/python/quiz/agent.py tests/quiz/test_agent.py
git commit -m "feat: add difficulty-specific prompt instructions to question generation"
```

---

### Task 2: Add difficulty toggle UI to quiz start screen

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx:33,226-254`
- Modify: `tests/renderer/Quiz.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `tests/renderer/Quiz.test.tsx` inside the `describe("Quiz page")` block:

```tsx
it("renders a difficulty selector with Easy, Medium, Hard options", async () => {
  renderQuizFlow();
  expect(await screen.findByText("Start Quiz")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /easy/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /medium/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /hard/i })).toBeInTheDocument();
});

it("defaults difficulty to Medium", async () => {
  renderQuizFlow();
  expect(await screen.findByText("Start Quiz")).toBeInTheDocument();
  const mediumBtn = screen.getByRole("button", { name: /^medium$/i });
  expect(mediumBtn).toHaveClass("bg-primary");
});

it("cycles difficulty with the D shortcut", async () => {
  const user = userEvent.setup();
  renderQuizFlow();
  expect(await screen.findByText("Start Quiz")).toBeInTheDocument();

  const mediumBtn = screen.getByRole("button", { name: /^medium$/i });
  expect(mediumBtn).toHaveClass("bg-primary");

  await user.keyboard("d");
  const hardBtn = screen.getByRole("button", { name: /^hard$/i });
  expect(hardBtn).toHaveClass("bg-primary");

  await user.keyboard("d");
  const easyBtn = screen.getByRole("button", { name: /^easy$/i });
  expect(easyBtn).toHaveClass("bg-primary");
});

it("sends selected difficulty when starting a session", async () => {
  const user = userEvent.setup();
  renderQuizFlow();
  expect(await screen.findByText("Start Quiz")).toBeInTheDocument();

  await user.keyboard("d");
  await user.keyboard("d"); // now Easy

  const fetchSpy = vi.mocked(global.fetch);
  await user.keyboard("1");

  await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());

  const startCall = fetchSpy.mock.calls.find(
    (call) => (call[0] as string).includes("/session/start")
  );
  expect(startCall).toBeDefined();
  const body = JSON.parse(startCall![1]!.body as string);
  expect(body.difficulty).toBe("easy");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx vitest run tests/renderer/Quiz.test.tsx -v`
Expected: FAIL — no difficulty selector rendered.

- [ ] **Step 3: Write minimal implementation**

In `src/renderer/pages/Quiz.tsx`:

1. Add state after the existing `randomize` state (around line 33):

```tsx
const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
```

2. Add the difficulty toggle section in the idle screen JSX, between the "Session Variety Mode" div (after line 254) and the mode button grid (line 256). Insert:

```tsx
<div className="space-y-3">
  <div className="space-y-1">
    <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">
      Question Difficulty
    </span>
    <p className="font-mono text-[10px] text-on-surface-variant/80">
      `D` cycles difficulty
    </p>
  </div>
  <div className="flex gap-2 justify-center">
    {(["easy", "medium", "hard"] as const).map((level) => (
      <button
        key={level}
        onClick={() => setDifficulty(level)}
        className={`px-4 py-2 font-label text-[10px] uppercase tracking-wider transition-colors border border-outline-variant/20 ${
          difficulty === level
            ? "bg-primary text-on-primary border-primary"
            : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
        }`}
      >
        {level.charAt(0).toUpperCase() + level.slice(1)}
      </button>
    ))}
  </div>
</div>
```

3. Add `difficulty` to every `startSession()` call. There are 7 mode buttons and 1 focus session grid. Each `{ mode: ..., randomize }` needs `difficulty` added. Example for the Random button:

```tsx
onClick={() => session.startSession({ mode: "random", randomize, difficulty })}
```

Apply the same pattern to all other `startSession` calls in the idle screen (Gap-Driven, Clinical Guidelines, Medication Guidelines, Clinical Skills, Pharmacology, Pathophysiology, and the focus session category buttons).

4. Add the `D` keyboard shortcut in the `useQuizShortcuts` array (after the existing `v` shortcut around line 163):

```tsx
{
  key: "d",
  enabled: session.phase === "idle",
  action: () =>
    setDifficulty((current) =>
      current === "easy" ? "medium" : current === "medium" ? "hard" : "easy"
    ),
},
```

5. Pass `difficulty` in the guideline revision `startSession` calls (around lines 54-56):

```tsx
if (state.scope === "all") {
  session.startSession({ mode: "clinical_guidelines", randomize, difficulty });
} else if (state.section) {
  session.startSession({ mode: "topic", topic: state.section, randomize, difficulty });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx vitest run tests/renderer/Quiz.test.tsx -v`
Expected: PASS

- [ ] **Step 5: Run full renderer test suite**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx vitest run tests/renderer/ -v`
Expected: All tests pass. (Consult `KNOWN_TEST_FAILURES.md` for pre-existing failures — 17 frontend failures are documented there and should not be treated as regressions.)

- [ ] **Step 6: Commit**

```bash
git add src/renderer/pages/Quiz.tsx tests/renderer/Quiz.test.tsx
git commit -m "feat: add difficulty selector to quiz start screen"
```

---

### Task 3: Final verification

- [ ] **Step 1: Run full Python test suite**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/ -v --ignore=tests/renderer`
Expected: All pass (4 known failures in `KNOWN_TEST_FAILURES.md` excluded).

- [ ] **Step 2: Run full renderer test suite**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx vitest run -v`
Expected: Pass (known failures per `KNOWN_TEST_FAILURES.md` excluded).

- [ ] **Step 3: Verify manually in dev mode**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npm run dev`
- Confirm difficulty toggle appears between "Session Variety Mode" and the mode buttons
- Confirm Medium is active by default
- Confirm `D` cycles through Easy → Medium → Hard → Easy
- Confirm starting a session with Easy selected generates a simpler recall-style question
- Confirm starting a session with Hard selected generates a multi-step scenario question
