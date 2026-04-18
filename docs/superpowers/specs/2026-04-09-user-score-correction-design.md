# User Score Correction

**Date:** 2026-04-09
**Status:** Approved

## Problem

The quiz LLM sometimes misjudges answers — marking clinically correct responses as incorrect, or vice versa. The user currently has no way to override the model's score, which means mastery data becomes inaccurate when the model is wrong.

## Solution

Add a self-scoring correction mechanism to the Feedback page. The user can override the model's score with a single click. The corrected score replaces the model's score in the database, and mastery recalculates automatically.

## Scope

- Active quiz session only — correction buttons appear on the Feedback screen and disappear once the user navigates away
- Score replacement — the user's correction overwrites the model's original score; no audit trail of the original
- No history view correction — only available during the active feedback screen

## Backend Changes

### New endpoint: `POST /quiz/question/correct`

Request body:
```json
{
  "question_id": "string",
  "corrected_score": "correct" | "partial" | "incorrect"
}
```

Response:
```json
{
  "status": "ok",
  "corrected_score": "correct"
}
```

Errors:
- 404 if no `quiz_history` row exists for that `question_id`

### New method: `Tracker.correct_answer(question_id, corrected_score)`

Updates the most recent `quiz_history` row for the given `question_id`:

```sql
UPDATE quiz_history
SET score = ?
WHERE id = (
  SELECT MAX(id) FROM quiz_history
  WHERE question_id = ?
)
```

Thread-safe via the existing `_lock`.

No schema changes — operates on the existing `score` column.

## Frontend Changes

### New type: `CorrectScoreRequest`

Added to `src/renderer/types/api.ts`:

```typescript
export interface CorrectScoreRequest {
  question_id: string;
  corrected_score: "correct" | "partial" | "incorrect";
}
```

### Updated type: `FeedbackNavigationState`

Gains a `questionId: string` field so the Feedback page knows which question to correct. The quiz session already has this value available at evaluation time.

### New component section on `Feedback.tsx`

A `UserCorrection` section placed between `FeedbackSplitView` and the navigation buttons.

**Behaviour:**
- Shows the model's original score as a label (e.g. "Model scored: Partial")
- Displays correction buttons based on the model's original score:
  - Model said **correct** → "I was Incorrect"
  - Model said **partial** → "I was Correct" + "I was Incorrect"
  - Model said **incorrect** → "I was Correct"
  - Model said **null** (reveal reference) → "I was Correct" + "I was Partial" + "I was Incorrect"
- On click: calls `POST /quiz/question/correct`, then hides the buttons and shows a confirmation message ("Score corrected to: Correct")
- If the API call fails, show an inline error and keep the buttons visible

**Styling:** Follows the Archival Protocol — `tertiary` variant buttons, muted tone, no flashy colours. Confirmation text uses `font-mono text-[10px]` matching the existing model ID line.

### API call

Uses `fetch` to `POST /quiz/question/correct` with the `CorrectScoreRequest` body. No new hook needed — a simple async call in the component is sufficient.

## Files Changed

| File | Change |
|------|--------|
| `src/python/quiz/tracker.py` | Add `correct_answer()` method |
| `src/python/quiz/router.py` | Add `CorrectScoreRequest` model + `/question/correct` endpoint |
| `src/renderer/types/api.ts` | Add `CorrectScoreRequest` type + `questionId` to `FeedbackNavigationState` |
| `src/renderer/pages/Feedback.tsx` | Add correction buttons + API call |
| `src/renderer/hooks/useQuizSession.ts` | Pass `questionId` in feedback navigation state |

## What Stays the Same

- `quiz_history` schema — no new columns or tables
- Mastery calculation — queries `score` directly, so corrected values are picked up automatically
- Streak and accuracy endpoints — reflect the corrected score with no code changes
- All other quiz flows — generate, evaluate, session management unchanged
