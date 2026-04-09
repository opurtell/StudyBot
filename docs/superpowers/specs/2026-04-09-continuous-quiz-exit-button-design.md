# Continuous Quiz & Exit Button — Design Spec

**Date:** 2026-04-09  
**Status:** Approved

---

## Problem

The quiz progress bar fills to 100% at question 10, giving the false impression the session ends there. The "Skip" button in the question phase calls `handleExit()` which ends the session entirely — misleading, since users expect "Skip" to skip the question. There is no visible "End Session" button in the question phase; users must press Esc.

---

## Goals

1. Make the quiz feel continuous with no implied cap.
2. Fix "Skip" to skip the current question and advance to the next.
3. Add an explicit "End Session" button in the question phase.

---

## Out of Scope

- Backend changes — the quiz session API already supports unlimited questions per session.
- Changes to the feedback phase — "End Session" already exists there.
- Changes to the idle or error phases.
- Skipping a question (calling `nextQuestion()` without a prior `submitAnswer`) leaves the generated question without an evaluation record in the store. This is acceptable — the backend creates no broken state from an unanswered question; it simply has no evaluation entry for it.

---

## Design

### 1. Remove ProgressBar

Remove `<ProgressBar>` from all three render blocks in `Quiz.tsx` (loading, question/submitting, feedback). The `ProgressBar` import can also be removed. The component file itself is left in place.

### 2. Question Counter in Header

**Question phase header row** (currently `[Session {id}] · [Timer]`):  
Change to `[Session {id} · Q {n}] · [Timer]` — append ` · Q {n}` to the session ID label on the left.

**Loading phase:** No change to the loading label. The text "Generating question..." is set directly in `useQuizSession.ts` (not as a fallback in `Quiz.tsx`), so changing it would require a separate file. It is acceptable as-is.

**Feedback phase:** Already shows `Question {n} — {category}`. No change.

**Bottom footer row** (question phase): Remove the `"Question {session.questionCount}"` label — it is redundant now that the counter is in the header.

### 3. Question Phase — Action Row

**Current right-side layout:** `Skip (tertiary, Esc hint)` · `Submit Answer (primary)`

**New right-side layout:** `End Session (tertiary, Esc hint)` · `Skip (tertiary)` · `Submit Answer (primary)`

Specific changes:
- Rename the existing "Skip" button to **"End Session"**. It already calls `handleExit()` — no logic change. The `Esc` keyboard hint label stays on this button since `Esc` remains mapped to `handleExit()`.
- Add a new **"Skip"** button (tertiary, no keyboard hint) that calls `session.nextQuestion()`.

The `Reveal Reference` button on the left is unchanged.

### 4. Keyboard Shortcuts

No changes. `Esc` stays mapped to `handleExit()`. No new shortcut for Skip.

---

## Files Changed

| File | Change |
|------|--------|
| `src/renderer/pages/Quiz.tsx` | Remove `ProgressBar` import and usages; update header with Q counter; update loading label; remove footer question label; rename Skip → End Session; add new Skip button calling `nextQuestion()` |

No other files require changes.

---

## Testing

- Answer more than 10 questions — confirm the Q counter increments past Q 10 with no visual glitch or cap.
- Click **Skip** in the question phase — confirm it advances to the next question without exiting.
- Click **End Session** in the question phase — confirm it exits to the dashboard.
- Press **Esc** in the question phase — confirm it exits (existing behaviour preserved).
- Confirm the loading state shows "Generating question..." (unchanged).
