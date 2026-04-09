# Quiz Difficulty Selection — Design Spec

**Date:** 2026-04-09
**Status:** Approved

## Summary

Add a difficulty picker (Easy / Medium / Hard) to the quiz start screen so users can control question complexity. The backend plumbing already exists — difficulty is accepted, stored, and passed to the LLM prompt. This feature wires it up end-to-end by adding a UI selector and giving the LLM clear instructions per difficulty level.

## Changes

### 1. Frontend — Quiz start screen (`Quiz.tsx`)

- New state: `const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium")`
- New pill toggle group placed between the existing "Session Variety Mode" toggle and the mode button grid
- Styled identically to the variety toggle (archival protocol: small label, two-tone pills)
- Three options: Easy / Medium / Hard — Medium active by default
- Every `session.startSession()` call includes `difficulty` in its params
- Keyboard shortcut `D` (idle phase only) cycles through easy → medium → hard → easy

### 2. Backend — Difficulty-aware prompt (`agent.py`)

Append a difficulty-specific instruction block to `GENERATION_SYSTEM_PROMPT` based on the `difficulty` parameter:

- **Easy:** "Ask straightforward recall questions — single-fact definitions, drug names, basic indications. The answer should be 1-2 sentences maximum."
- **Medium:** No additional instructions (current behaviour).
- **Hard:** "Ask multi-step scenario questions requiring integration of 2+ clinical concepts. Include patient context (age, vitals, presentation). Expect detailed structured answers covering assessment, treatment rationale, and dose calculations where relevant."

The appendix is appended dynamically after the base system prompt string, keeping the base prompt unchanged.

### 3. No changes required

- `useQuizSession` hook — `StartSessionRequest` already includes optional `difficulty`
- Backend router — `StartSessionRequest.difficulty` already accepted with default "medium"
- Backend store — already persists difficulty per session
- Types — `difficulty` already typed as `"easy" | "medium" | "hard"` in `api.ts`

## Keyboard shortcuts

| Key | Phase | Action |
|-----|-------|--------|
| `D` | idle | Cycle difficulty: easy → medium → hard → easy |

Existing 1-7 and `V` shortcuts unchanged.

## Scope exclusions

- No retrieval parameter changes (prompt-only differentiation)
- No difficulty persistence across sessions (always defaults to Medium)
- No changes to evaluation/scoring logic
