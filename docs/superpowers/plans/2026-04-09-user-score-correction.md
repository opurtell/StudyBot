# User Score Correction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users override the model's quiz evaluation score from the Feedback page, replacing the stored score so mastery data stays accurate.

**Architecture:** One new backend endpoint (`POST /quiz/question/correct`) updates the `quiz_history` row in-place via a new `Tracker.correct_answer()` method. The frontend adds correction buttons to `Feedback.tsx` that call this endpoint, then show a confirmation message.

**Tech Stack:** Python/FastAPI (backend), TypeScript/React (frontend), SQLite (persistence)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/python/quiz/tracker.py` | Modify | Add `correct_answer()` method |
| `tests/quiz/test_tracker.py` | Modify | Add tests for `correct_answer()` |
| `src/python/quiz/router.py` | Modify | Add `CorrectScoreRequest` model + `/question/correct` endpoint |
| `src/renderer/types/api.ts` | Modify | Add `CorrectScoreRequest` type + `questionId` to `FeedbackNavigationState` |
| `src/renderer/pages/Quiz.tsx` | Modify | Pass `questionId` in feedback navigation state |
| `src/renderer/pages/Feedback.tsx` | Modify | Add correction buttons + API call |

---

### Task 1: Add `Tracker.correct_answer()` method with tests

**Files:**
- Modify: `src/python/quiz/tracker.py:44-75`
- Modify: `tests/quiz/test_tracker.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/quiz/test_tracker.py`:

```python
def test_correct_answer_updates_score(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 10.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    mastery = tracker.get_mastery()
    assert mastery[0].correct == 1
    assert mastery[0].incorrect == 0


def test_correct_answer_updates_mastery_percent(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    mastery = tracker.get_mastery()
    assert mastery[0].mastery_percent == pytest.approx(75.0)


def test_correct_answer_no_history_row(tracker):
    """Correcting a question with no history should not raise."""
    tracker.correct_answer("nonexistent", "correct")
    # No crash, no rows created
    assert tracker.get_mastery() == []


def test_correct_answer_updates_latest_only(tracker):
    """If the same question_id appears twice, only the latest row is corrected."""
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 10.0, "CMG 14")
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 15.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    history = tracker.get_recent_history(limit=10)
    # Two rows: latest corrected to "correct", earlier still "incorrect"
    assert history[0].score == "correct"
    assert history[1].score == "incorrect"


def test_correct_answer_updates_streak(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    assert tracker.get_streak() == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/quiz/test_tracker.py::test_correct_answer_updates_score tests/quiz/test_tracker.py::test_correct_answer_updates_mastery_percent tests/quiz/test_tracker.py::test_correct_answer_no_history_row tests/quiz/test_tracker.py::test_correct_answer_updates_latest_only tests/quiz/test_tracker.py::test_correct_answer_updates_streak -v`
Expected: FAIL — `Tracker` has no `correct_answer` method.

- [ ] **Step 3: Implement `correct_answer()`**

Add this method to the `Tracker` class in `src/python/quiz/tracker.py`, after the existing `record_answer` method (after line 75):

```python
    def correct_answer(self, question_id: str, corrected_score: str) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE quiz_history
                   SET score = ?
                   WHERE id = (
                       SELECT MAX(id) FROM quiz_history
                       WHERE question_id = ?
                   )""",
                (corrected_score, question_id),
            )
            self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/quiz/test_tracker.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/python/quiz/tracker.py tests/quiz/test_tracker.py
git commit -m "feat: add Tracker.correct_answer() for user score correction"
```

---

### Task 2: Add `/quiz/question/correct` endpoint

**Files:**
- Modify: `src/python/quiz/router.py:81-88`

- [ ] **Step 1: Add the request model and endpoint**

In `src/python/quiz/router.py`, add a new request model after the existing `BlacklistRequest` (after line 88):

```python
class CorrectScoreRequest(BaseModel):
    question_id: str
    corrected_score: str  # "correct" | "partial" | "incorrect"
```

Then add the endpoint after the `/question/evaluate` endpoint (after line 188):

```python
@router.post("/question/correct")
def correct_score(req: CorrectScoreRequest) -> dict:
    if req.corrected_score not in ("correct", "partial", "incorrect"):
        raise HTTPException(status_code=422, detail="corrected_score must be one of: correct, partial, incorrect")
    tracker = _get_tracker()
    tracker.correct_answer(req.question_id, req.corrected_score)
    return {"status": "ok", "corrected_score": req.corrected_score}
```

- [ ] **Step 2: Verify the endpoint starts without errors**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -c "from quiz.router import router; print('OK')"`
Expected: prints `OK`

- [ ] **Step 3: Commit**

```bash
git add src/python/quiz/router.py
git commit -m "feat: add POST /quiz/question/correct endpoint"
```

---

### Task 3: Add `CorrectScoreRequest` type and `questionId` to `FeedbackNavigationState`

**Files:**
- Modify: `src/renderer/types/api.ts`

- [ ] **Step 1: Add the type and update `FeedbackNavigationState`**

In `src/renderer/types/api.ts`, add this interface after `EvaluateResponse` (after line 62):

```typescript
export interface CorrectScoreRequest {
  question_id: string;
  corrected_score: "correct" | "partial" | "incorrect";
}
```

Then update `FeedbackNavigationState` (lines 73-82) to include `questionId`:

```typescript
export interface FeedbackNavigationState {
  questionText: string;
  userAnswer: string;
  evaluation: EvaluateResponse;
  elapsedSeconds: number;
  category: string;
  questionType: string;
  sessionId: string | null;
  questionCount: number;
  questionId: string;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx tsc --noEmit --project src/renderer/tsconfig.json 2>&1 | head -30`
Expected: May show errors in files that construct `FeedbackNavigationState` without `questionId` — that's expected, fixed in Task 4.

- [ ] **Step 3: Commit**

```bash
git add src/renderer/types/api.ts
git commit -m "feat: add CorrectScoreRequest type and questionId to FeedbackNavigationState"
```

---

### Task 4: Pass `questionId` in feedback navigation state from Quiz page

**Files:**
- Modify: `src/renderer/pages/Quiz.tsx:87-103`

- [ ] **Step 1: Add `questionId` to the navigation state**

In `src/renderer/pages/Quiz.tsx`, update the `handleViewFullAnalysis` function's `navigate` call (around line 92) to include `questionId`:

```typescript
    navigate("/feedback", {
      state: {
        questionText: session.question.question_text,
        userAnswer: answer,
        evaluation: session.evaluation,
        elapsedSeconds: session.elapsedSeconds,
        category: session.question.category,
        questionType: session.question.question_type,
        sessionId: session.sessionId,
        questionCount: session.questionCount,
        questionId: session.question.question_id,
      }
    });
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx tsc --noEmit --project src/renderer/tsconfig.json 2>&1 | head -30`
Expected: Fewer errors than Task 3 — `Quiz.tsx` should now compile cleanly.

- [ ] **Step 3: Commit**

```bash
git add src/renderer/pages/Quiz.tsx
git commit -m "feat: pass questionId in feedback navigation state"
```

---

### Task 5: Add correction buttons to Feedback page

**Files:**
- Modify: `src/renderer/pages/Feedback.tsx`

- [ ] **Step 1: Add correction UI to the Feedback page**

Replace the entire content of `src/renderer/pages/Feedback.tsx` with:

```tsx
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { FeedbackNavigationState } from "../types/api";
import { useQuizShortcuts } from "../hooks/useQuizShortcuts";
import FeedbackSplitView from "../components/FeedbackSplitView";
import GroundTruth from "../components/GroundTruth";
import ResponseTimeMetrics from "../components/ResponseTimeMetrics";
import Button from "../components/Button";
import SourceFootnotes from "../components/SourceFootnotes";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:7777";

type Score = "correct" | "partial" | "incorrect";

function getCorrectionOptions(modelScore: Score | null): Score[] {
  if (modelScore === "correct") return ["incorrect"];
  if (modelScore === "partial") return ["correct", "incorrect"];
  if (modelScore === "incorrect") return ["correct"];
  // null = reveal reference — user can pick any score
  return ["correct", "partial", "incorrect"];
}

const SCORE_LABELS: Record<Score, string> = {
  correct: "I was Correct",
  partial: "I was Partially Correct",
  incorrect: "I was Incorrect",
};

export default function Feedback() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as FeedbackNavigationState | null;

  const [correcting, setCorrecting] = useState(false);
  const [correctedTo, setCorrectedTo] = useState<Score | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  useQuizShortcuts([
    {
      key: "Escape",
      action: () => navigate("/"),
      allowInEditable: true,
    },
    {
      key: "ArrowRight",
      meta: true,
      action: () => {
        if (state?.sessionId) {
          navigate("/quiz", { state: { action: "continue" as const, sessionId: state.sessionId, questionCount: state.questionCount } });
        } else {
          navigate("/");
        }
      },
    },
  ]);

  if (!state?.evaluation) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-8">
        <h2 className="font-headline text-headline-md text-on-surface-variant">
          No evaluation data available
        </h2>
        <Button
          onClick={() => navigate("/")}
          variant="tertiary"
          className="mt-4"
          aria-keyshortcuts="Escape Meta+ArrowRight Control+ArrowRight"
        >
          Return to Dashboard
          <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
        </Button>
      </div>
    );
  }

  const modelScore = state.evaluation.score as Score | null;
  const correctionOptions = getCorrectionOptions(modelScore);

  async function handleCorrect(newScore: Score) {
    if (!state?.questionId) return;
    setCorrecting(true);
    setCorrectionError(null);
    try {
      const res = await fetch(`${API_BASE}/quiz/question/correct`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: state.questionId,
          corrected_score: newScore,
        }),
      });
      if (!res.ok) {
        throw new Error(`Correction failed (${res.status})`);
      }
      setCorrectedTo(newScore);
    } catch (err) {
      setCorrectionError(err instanceof Error ? err.message : "Correction failed");
    } finally {
      setCorrecting(false);
    }
  }

  return (
    <div className="min-h-screen">
      <div className="px-8 py-12 max-w-7xl mx-auto">
        <div className="border-l-4 border-primary pl-8 py-2 mb-8">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Quiz Review
          </span>
          <h2 className="font-headline text-display-lg text-primary italic">
            Answer Feedback
          </h2>
        </div>

        <GroundTruth
          quote={state.evaluation.source_quote}
          citation={state.evaluation.source_citation}
        />

        <ResponseTimeMetrics elapsedSeconds={state.elapsedSeconds} />

        <div className="mt-8">
          <FeedbackSplitView
            userAnswer={state.userAnswer}
            evaluation={state.evaluation}
          />
        </div>

        <div className="mt-6">
          <SourceFootnotes citations={[state.evaluation.source_citation]} />
          <p className="font-mono text-[10px] text-on-surface-variant/50 mt-3">
            Model: {state.evaluation.model_id}
          </p>
        </div>

        {/* User correction section */}
        <div className="mt-6">
          {correctedTo ? (
            <p className="font-mono text-[10px] text-primary">
              Score corrected to: {correctedTo}
            </p>
          ) : (
            <>
              <p className="font-mono text-[10px] text-on-surface-variant mb-2">
                Model scored: {modelScore ?? "self-graded"}
              </p>
              <div className="flex items-center gap-3">
                {correctionOptions.map((opt) => (
                  <Button
                    key={opt}
                    onClick={() => handleCorrect(opt)}
                    variant="tertiary"
                    disabled={correcting}
                  >
                    {SCORE_LABELS[opt]}
                  </Button>
                ))}
              </div>
              {correctionError && (
                <p className="font-mono text-[10px] text-error mt-2">
                  {correctionError}
                </p>
              )}
            </>
          )}
        </div>

        <div className="mt-8 flex items-center gap-4">
          <Button
            onClick={() => navigate("/")}
            variant="secondary"
            aria-keyshortcuts="Escape"
          >
            Return to Dashboard
            <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
          </Button>
          {state?.sessionId && (
            <Button
              onClick={() =>
                navigate("/quiz", {
                  state: { action: "continue" as const, sessionId: state.sessionId, questionCount: state.questionCount },
                })
              }
              aria-keyshortcuts="Meta+ArrowRight Control+ArrowRight"
            >
              Continue Quiz
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">⌘/Ctrl+→</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx tsc --noEmit --project src/renderer/tsconfig.json 2>&1 | head -30`
Expected: No errors related to `Feedback.tsx`, `Quiz.tsx`, or `api.ts`.

- [ ] **Step 3: Commit**

```bash
git add src/renderer/pages/Feedback.tsx
git commit -m "feat: add user score correction buttons to Feedback page"
```

---

### Task 6: Verify end-to-end

- [ ] **Step 1: Run Python tests**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/quiz/test_tracker.py -v`
Expected: All PASS.

- [ ] **Step 2: Run TypeScript check**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && npx tsc --noEmit --project src/renderer/tsconfig.json`
Expected: Clean — no errors.

- [ ] **Step 3: Manual smoke test**

Start the app and run through a quiz:
1. Start a quiz session
2. Answer a question
3. On the Feedback page, verify the correction buttons appear based on the model's score
4. Click a correction button
5. Verify the confirmation message appears and buttons disappear
6. Check `/quiz/mastery` endpoint to confirm the score was updated
