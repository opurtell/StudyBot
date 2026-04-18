# Continuous Quiz & Exit Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the 10-question progress bar, fix "Skip" to advance to the next question, and add an explicit "End Session" button to the question phase.

**Architecture:** All changes are confined to a single React page component (`Quiz.tsx`) and its test file (`Quiz.test.tsx`). No backend or hook changes are required — `session.nextQuestion()` already handles advancing to the next question, and sessions are already unbounded.

**Tech Stack:** React 19, TypeScript 5, Vitest + @testing-library/react + @testing-library/user-event

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `src/renderer/pages/Quiz.tsx` | Modify | Remove `ProgressBar` import + 3 usages; add Q counter to question-phase header; remove footer question label; rename Skip → End Session; add Skip button calling `nextQuestion()` |
| `tests/renderer/Quiz.test.tsx` | Modify | Add tests for Skip-advances, End-Session-exits, Q-counter presence, no ProgressBar |

---

### Task 1: Write failing tests for the new behaviour

**Files:**
- Modify: `tests/renderer/Quiz.test.tsx`

These tests must be written **before** touching `Quiz.tsx`. They will fail because the current implementation has no "End Session" button in the question phase and Skip exits rather than advancing.

- [ ] **Step 1: Add the four new test cases**

Append inside the existing `describe("Quiz page", () => { ... })` block in `tests/renderer/Quiz.test.tsx`, after the last existing `it(...)`:

```tsx
  it("Skip button advances to the next question without exiting", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument()
    );
    expect(screen.getAllByText("Question 1").length).toBeGreaterThanOrEqual(1);

    await user.click(screen.getByRole("button", { name: /^skip$/i }));

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument()
    );
    expect(screen.getAllByText("Question 2").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Archive Home")).not.toBeInTheDocument();
  });

  it("End Session button exits to the dashboard from the question phase", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /end session/i }));

    await waitFor(() => expect(screen.getByText("Archive Home")).toBeInTheDocument());
  });

  it("shows a Q counter in the question-phase header", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument()
    );

    expect(screen.getByText(/Q 1/)).toBeInTheDocument();
  });

  it("does not render a ProgressBar during an active session", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument()
    );

    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the new tests and confirm they all fail**

```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot
npx vitest run tests/renderer/Quiz.test.tsx 2>&1 | tail -40
```

Expected: 4 new tests FAIL. Existing tests pass. If any existing test fails unexpectedly, investigate before continuing.

---

### Task 2: Remove ProgressBar from Quiz.tsx

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx`

- [ ] **Step 1: Remove the ProgressBar import**

In `Quiz.tsx`, delete line:
```tsx
import ProgressBar from "../components/ProgressBar";
```

- [ ] **Step 2: Remove ProgressBar from the loading phase**

Find the loading-phase render block (currently `if (session.phase === "loading")`). It starts with:
```tsx
    return (
      <div className="min-h-screen flex flex-col">
        <ProgressBar percent={(session.questionCount / 10) * 100} />
```

Remove the `<ProgressBar ... />` line.

- [ ] **Step 3: Remove ProgressBar from the feedback phase**

Find the feedback-phase render block (currently `if (session.phase === "feedback" && ...)`). It starts with:
```tsx
    return (
      <div className="min-h-screen flex flex-col">
        <ProgressBar percent={(session.questionCount / 10) * 100} />
```

Remove the `<ProgressBar ... />` line.

- [ ] **Step 4: Remove ProgressBar from the question phase**

Find the final return block (question phase). It starts with:
```tsx
  return (
    <div className="min-h-screen flex flex-col">
      <ProgressBar percent={(session.questionCount / 10) * 100} />
```

Remove the `<ProgressBar ... />` line.

- [ ] **Step 5: Run the "does not render a ProgressBar" test**

```bash
npx vitest run tests/renderer/Quiz.test.tsx --reporter=verbose 2>&1 | grep -E "✓|✗|FAIL|PASS|progressbar"
```

Expected: the "does not render a ProgressBar" test now passes. The other 3 new tests still fail.

---

### Task 3: Add Q counter to the question-phase header and remove the footer label

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx`

- [ ] **Step 1: Update the header row to include the Q counter**

In the question phase's final `return` block, find the header row:
```tsx
        <div className="flex items-center justify-between mb-8">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Session {session.sessionId?.slice(-4)}
          </span>
          <QuizTimer running={timerRunning} onTick={session.setElapsedSeconds} />
        </div>
```

Replace with:
```tsx
        <div className="flex items-center justify-between mb-8">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Session {session.sessionId?.slice(-4)} · Q {session.questionCount}
          </span>
          <QuizTimer running={timerRunning} onTick={session.setElapsedSeconds} />
        </div>
```

- [ ] **Step 2: Remove the bottom footer question label**

Find and delete the entire footer div at the bottom of the question phase:
```tsx
        <div className="flex items-center justify-between mt-12 pt-4 border-t border-outline-variant/10">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Question {session.questionCount}
          </span>
        </div>
```

- [ ] **Step 3: Run the Q counter test**

```bash
npx vitest run tests/renderer/Quiz.test.tsx --reporter=verbose 2>&1 | grep -E "✓|✗|counter|header"
```

Expected: the "shows a Q counter" test now passes.

---

### Task 4: Fix Skip and add End Session button

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx`

- [ ] **Step 1: Rename Skip → End Session and add new Skip button**

In the question phase action row, find the right-side button group:
```tsx
              <div className="flex items-center gap-3">
                <Button onClick={handleExit} variant="tertiary" aria-keyshortcuts="Escape">
                  Skip
                  <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={false}
                  aria-keyshortcuts="Enter Meta+Enter Control+Enter"
                >
                  Submit Answer
                  <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Enter / ⌘/Ctrl+Enter</span>
                </Button>
              </div>
```

Replace with:
```tsx
              <div className="flex items-center gap-3">
                <Button onClick={handleExit} variant="tertiary" aria-keyshortcuts="Escape">
                  End Session
                  <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
                </Button>
                <Button onClick={() => session.nextQuestion()} variant="tertiary">
                  Skip
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={false}
                  aria-keyshortcuts="Enter Meta+Enter Control+Enter"
                >
                  Submit Answer
                  <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Enter / ⌘/Ctrl+Enter</span>
                </Button>
              </div>
```

- [ ] **Step 2: Run all new tests**

```bash
npx vitest run tests/renderer/Quiz.test.tsx --reporter=verbose 2>&1 | tail -30
```

Expected: all 4 new tests pass.

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
npx vitest run tests/renderer/Quiz.test.tsx 2>&1 | tail -20
```

Expected: all tests pass. If the existing "submits with ctrl+enter from outside the textarea" test fails (it focused the old Skip button by name — it now finds the new Skip button, which is fine), verify the test logic is still correct.

Note: `KNOWN_TEST_FAILURES.md` documents 17 pre-existing frontend failures. Do not treat those as regressions introduced by this change.

---

### Task 5: Commit

- [ ] **Step 1: Stage and commit**

```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot
git add src/renderer/pages/Quiz.tsx tests/renderer/Quiz.test.tsx
git commit -m "feat: continuous quiz with skip and end session buttons"
```

Expected: commit succeeds.

- [ ] **Step 2: Verify clean state**

```bash
git status
```

Expected: `nothing to commit, working tree clean`
