# Clear Mastery & Quiz History — Design Spec

**Date:** 2026-04-09

## Summary

Add a user-facing option to permanently clear all quiz history and reset mastery scores. Surfaced on both the Dashboard (near the Knowledge Heatmap) and the Settings page (in the Indexed Data section).

## Scope

Full wipe: truncate `quiz_history` and `categories` tables in `mastery.db`. Quiz questions stored in the `questions` table are not affected (they are ephemeral session data cleared on startup anyway).

## Backend

### Store method — `quiz/store.py`

Add `clear_mastery_data() -> int` to `QuizStore`:
- Execute `DELETE FROM quiz_history` and `DELETE FROM categories`
- Return the count of deleted history rows

### API endpoint — `quiz/router.py`

Add `POST /quiz/mastery/clear`:
- Calls `store.clear_mastery_data()`
- Returns `{ "status": "ok", "deleted_history": <count> }`
- No request body required

## Frontend

### Provider — `SettingsProvider.tsx`

Add `clearMastery(): Promise<void>`:
- POST to `/quiz/mastery/clear`
- On success, invalidate cached mastery data so `useMastery` re-fetches
- Mirrors the existing `clearVectorStore()` pattern

### Settings page — `Settings.tsx`

Add a "Clear Mastery & Quiz History" button in the Indexed Data management section, grouped with the existing source-type clear buttons. Same styling and confirmation pattern as "Clear All Indexed Data".

### Dashboard — `Dashboard.tsx`

Add a small reset icon/button next to the Knowledge Heatmap section header. When clicked, opens the same confirmation modal.

### Confirmation modal

Reuse `Modal.tsx`. Body text: "This will permanently delete all quiz history and reset mastery scores to zero. This cannot be undone." Two actions: Cancel (default) and Clear Mastery (destructive variant).

### Post-clear refresh

- Dashboard: `useMastery` hook re-fetches automatically after cache invalidation
- Settings: remains on current view; mastery data is refreshed on next navigation to Dashboard

## Files touched

| File | Change |
|------|--------|
| `src/python/quiz/store.py` | Add `clear_mastery_data()` |
| `src/python/quiz/router.py` | Add `POST /quiz/mastery/clear` |
| `src/renderer/providers/SettingsProvider.tsx` | Add `clearMastery()` method |
| `src/renderer/pages/Settings.tsx` | Add clear mastery button |
| `src/renderer/pages/Dashboard.tsx` | Add reset button near heatmap |
