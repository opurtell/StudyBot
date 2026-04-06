# Session Start Category Grid

## Problem

The quiz session start screen offers only 4 buttons (Random, Gap-Driven, Cardiac Focus, Trauma Focus). The backend hard-codes 8 categories for random mode but has no medication-specific option and no way to select most categories. Topic-based sessions rely on semantic search rather than metadata filtering, so a "Medications" topic might retrieve non-medication chunks.

## Design

### Frontend Layout

Top section (unchanged): Session Variety toggle + Random Session + Gap-Driven Session buttons.

New section below heading "Focus Sessions": scrollable grid of category buttons. Categories derived from actual data sections in `data/cmgs/structured/`.

Grid categories (16 total):

| CMG Sections (14) | Special (2) |
|---|---|
| Medical | Medications |
| Cardiac | Clinical Skills |
| Trauma | |
| Airway Management | |
| Behavioural | |
| Neurology | |
| Obstetric | |
| Environmental | |
| Toxicology | |
| Respiratory | |
| Palliative Care | |
| HAZMAT | |
| Pain Management | |
| General Care | |

Each grid button calls `startSession({ mode: "topic", topic: "<mapped_name>", randomize })`.

### Category-to-Section Mapping

Frontend display names map to ChromaDB `section` metadata values:

| Display Name | section value | Source |
|---|---|---|
| Medications | Medicine | med/ JSON files |
| Clinical Skills | Clinical Skill | csm/ JSON files |
| All others | Same as display name | CMG JSON files |

The backend `_resolve_mode` function applies a metadata filter `{"section": "<value>"}` when `mode == "topic"`, ensuring only chunks matching that exact section are retrieved.

### Backend Changes

1. **`src/python/quiz/agent.py` — `_resolve_mode`**: When `mode == "topic"`, return `(topic, {"section": topic})` instead of `(topic, None)`. This passes a metadata filter to the retriever.

2. **`src/python/quiz/retriever.py` — `_build_where`**: Already supports arbitrary `base_filters` dict. The `{"section": value}` filter will be passed through as a ChromaDB where clause. No changes needed to the retriever itself — it already handles this via the `base_filters` parameter.

3. **Hard-coded category lists**: The random/gap_driven fallback lists in `_resolve_mode` remain unchanged — they are not part of this feature.

### Frontend Changes

1. **`src/renderer/pages/Quiz.tsx`**: Replace the two hard-coded Cardiac/Trauma buttons (lines 86-91) with a grid of 16 category buttons.

2. **Category list**: Defined as a constant array in the component (or a shared file) with display name + section value pairs. Static list derived from data analysis — no dynamic fetching needed.

3. **Grid styling**: Use existing Tailwind classes consistent with Archival Protocol design system. CSS grid with responsive columns (e.g., `grid-cols-3` on medium screens).

### Files Modified

| File | Change |
|---|---|
| `src/python/quiz/agent.py` | `_resolve_mode`: add metadata filter for topic mode |
| `src/renderer/pages/Quiz.tsx` | Replace Cardiac/Trauma buttons with category grid |

### What Is NOT Changed

- Random and Gap-Driven session modes
- Session variety toggle (Maximum Variety / Strict Relevance)
- Retrieval logic (retriever already supports filters)
- Question generation or evaluation flows
- Session storage or state management
