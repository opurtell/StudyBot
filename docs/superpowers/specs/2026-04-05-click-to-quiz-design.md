# Click-to-Quiz from Dashboard Cards

**Date:** 2026-04-05
**Status:** Approved

## Summary

Allow clicking on the review suggestion card or any KnowledgeHeatmap mastery card on the Dashboard to navigate to the Quiz page and auto-start a topic quiz session for that category.

## Approach

Reuse the existing router-state pattern that the Guidelines page already uses. The Guidelines page navigates to `/quiz` with `{ scope: "section", section: "Cardiac" }` in `location.state`, and Quiz.tsx auto-launches a topic session via `session.startSession({ mode: "topic", topic: state.section })`. The Dashboard cards will produce the same state shape — no changes to Quiz.tsx or the backend are required.

## Changes

### 1. New file: `src/renderer/utils/resolveTopic.ts`

A single exported function that maps mastery category names to `QUIZ_CATEGORIES` section values.

**Signature:** `resolveTopic(categoryName: string): string | null`

**Logic:**
1. Normalise input (trim, lowercase)
2. Exact match against each `QUIZ_CATEGORIES` entry's `display` and `section` fields (case-insensitive)
3. Fallback: prefix/contains match (e.g. "Paediatrics" matches "Paediatric", "Toxicology" matches "Toxicology")
4. Return the matched `section` value, or `null` if no match found

The caller handles the `null` case by navigating to `/quiz` without state, landing the user on the quiz mode selector.

### 2. Modified: `src/renderer/pages/Dashboard.tsx`

- Import `useNavigate` from react-router-dom and `resolveTopic` from the new utility
- Review suggestion card (currently a plain `<div>`): add `cursor-pointer`, hover state, and `onClick` that resolves the topic and navigates to `/quiz` with `{ scope: "section", section: resolvedTopic }`. If resolution fails, navigate to `/quiz` without state (user lands on the mode selector).
- KnowledgeHeatmap: pass new `onCategoryClick` prop that resolves the category and navigates identically.

### 3. Modified: `src/renderer/components/KnowledgeHeatmap.tsx`

- Add optional prop: `onCategoryClick?: (category: string) => void`
- Each category card's outer `<div>`: add `cursor-pointer`, hover state, and `onClick` that calls `onCategoryClick(cat.category)` when the prop is provided

### 4. No changes to Quiz.tsx or backend

The existing `GuidelineRevisionState` handler in Quiz.tsx already handles this state shape and auto-launches topic sessions.

## Hover / Click Styling

Cards gain `cursor-pointer` and a subtle hover effect consistent with the Archival Protocol design system (background shift or border highlight, matching existing interactive elements). The review suggestion card and KnowledgeHeatmap cards share the same hover treatment.

## Error Handling

If `resolveTopic` returns `null` (unrecognised category), the navigation goes to `/quiz` without state, landing the user on the quiz mode selector where they can choose a session type manually.

## Files Summary

| File | Action |
|------|--------|
| `src/renderer/utils/resolveTopic.ts` | New — topic resolution utility |
| `src/renderer/pages/Dashboard.tsx` | Modified — add navigate + onClick handlers |
| `src/renderer/components/KnowledgeHeatmap.tsx` | Modified — add onCategoryClick prop + onClick |
