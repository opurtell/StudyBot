# Quiz Start: Two-Tier Option Grid

## Problem

The quiz start screen currently has two stacked main session buttons (Random, Gap-Driven) and a flat 3-column grid of 17 topic buttons. Users want faster access to the three broad content categories: Clinical Guidelines, Medication Guidelines, and Clinical Skills — without scrolling through specific topics.

## Design

### Two-tier layout

Replace the current vertical stack of 2 main buttons with a **top tier of 5 large buttons** in a responsive grid, followed by the existing **Focus Sessions grid** of 17 specific topic buttons.

**Top tier (5 buttons):**

| Label | Backend payload | Shortcut |
|---|---|---|
| Random Session | `{ mode: "random", randomize }` | `1` |
| Gap-Driven Session | `{ mode: "gap_driven", randomize }` | `2` |
| Clinical Guidelines | `{ mode: "clinical_guidelines", randomize }` | `3` |
| Medication Guidelines | `{ mode: "topic", topic: "Medicine", randomize }` | `4` |
| Clinical Skills | `{ mode: "topic", topic: "Clinical Skill", randomize }` | `5` |

- Layout: 5 columns on wide screens, wrapping to 3+2 or 2 rows on narrow screens.
- Style: Same `Button` component (primary for Random, secondary for the rest) used for the current main session buttons.
- Keyboard shortcuts 1–5 for direct access.

**Focus Sessions (unchanged):**

- Label: "Focus Sessions"
- 3-column grid of 17 topic buttons with current `font-label text-[10px]` styling.
- All 17 buttons and their `section` values remain the same.

**Session Variety Mode toggle:**

- Stays above the top tier in its current position.

### Category mapping

- **Clinical Guidelines**: Cardiac, Trauma, Medical, Respiratory, Airway Management, Paediatrics, Obstetric, Neurology, Behavioural, Toxicology, Environmental, Pain Management, Palliative Care, HAZMAT, General Care
- **Medication Guidelines**: Medications (section: "Medicine")
- **Clinical Skills**: Clinical Skills (section: "Clinical Skill")

## Backend changes

### New mode: `clinical_guidelines`

In `src/python/quiz/agent.py` `_resolve_mode()`, add a new branch:

```python
elif mode == "clinical_guidelines":
    clinical_sections = [
        "Cardiac", "Trauma", "Medical", "Respiratory", "Airway Management",
        "Paediatric", "Obstetric", "Neurology", "Behavioural", "Toxicology",
        "Environmental", "Pain Management", "Palliative Care", "HAZMAT",
        "General Care",
    ]
    query = random.choice(clinical_sections)
    return query, {"section": {"$in": clinical_sections}}
```

This picks a random clinical topic as the semantic query, but constrains ChromaDB results to only the 15 clinical guideline sections — excluding Medicine and Clinical Skill.

**Note:** Requires verifying that ChromaDB's `where` filter supports `$in` operator. If not, the section filter should be omitted (fall back to no filter) and the broad query alone will naturally lean toward clinical content.

### Router

`SessionConfig` and `StartSessionRequest` already accept `mode: str`, so no schema change needed. The router passes `mode` through to `_resolve_mode()`.

## Frontend changes

### `src/renderer/pages/Quiz.tsx`

1. Replace the `<div className="flex flex-col gap-3 max-w-xs mx-auto pt-4">` block (lines 189–207, the two main session buttons) with a 5-button grid.
2. Add keyboard shortcuts 3, 4, 5 for the three new buttons.
3. No changes to the Focus Sessions grid or Session Variety toggle.

### `src/renderer/types/api.ts`

No changes — `StartSessionRequest.mode` is already typed as `string`-ish (actually a union, but the backend accepts any string).

## Files to modify

| File | Change |
|---|---|
| `src/renderer/pages/Quiz.tsx` | Replace 2-button stack with 5-button top-tier grid, add shortcuts 3–5 |
| `src/python/quiz/agent.py` | Add `clinical_guidelines` mode to `_resolve_mode()` |
