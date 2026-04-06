# Clinical Guidelines Page — Design Spec

Date: 2026-04-04

## Summary

A new page at `/guidelines` that lets the user browse, read, and quiz themselves on all structured clinical content: CMGs, Medicine monographs, and Clinical Skills/Procedures (CSMs). The page serves as both a reference viewer and a quiz launchpad.

## Terminology

- Use **"guideline"** everywhere — not "protocol". This reflects ACTAS terminology where guidelines are semi-flexible rather than rigid protocols.
- Sidebar label: **"Clinical Guidelines"**
- Route: `/guidelines`

## Page Layout

The page uses `StandardLayout` (AppShell with sidebar + search bar). Three zones:

### 1. Filter Bar (sticky below search bar)

- **Type filter chips** (using `Tag` component): `All | CMG | Medication | Clinical Skill`
- **Section dropdown**: "All Sections" / Cardiac / Neurology / Trauma / etc.
- **Result count** in marginalia style (`font-mono text-[10px] on-surface-variant`): e.g. "47 guidelines"

### 2. Card Grid (grouped by section)

- Cards grouped under section category headings
- Each heading: `font-headline` serif, left-aligned, `on-surface-variant`
- Groups only render if they contain matching guidelines after filtering
- CSS grid: 3 columns desktop, 2 columns tablet
- Fixed category order: Cardiac, Respiratory, Airway Management, Neurology, Trauma, Medical, Pain Management, Toxicology, Environmental, Obstetric, Behavioural, HAZMAT, Palliative Care, General Care, Other

### 3. Side Panel (overlay, slides from right)

- Fixed width: ~40% viewport, min 480px
- Semi-transparent backdrop over card grid
- Contains: header, scrollable content, sticky footer

## Guideline Card

Each card uses the existing `Card` component pattern (surface-container-lowest, no borders, hover background shift):

- **Top left**: CMG number in `font-mono text-[10px]` marginalia (e.g. "CMG 23")
- **Top right**: Type tag via `Tag` component, colour-coded:
  - CMG → `primary` (dark archival ink)
  - Medication → `tertiary_fixed` (highlighter)
  - Clinical Skill → `on-surface-variant` (muted)
- **Title**: Guideline name in `font-headline` serif, single line, truncated
- **Bottom row**: `MasteryIndicator` dot (reuses Dashboard component) + section label in `font-label text-[10px]` uppercase tracking

Fixed height, uniform width. Click opens side panel. No hover state beyond standard background shift.

## Side Panel Detail View

### Header (sticky top)

- Close button (X icon, top right)
- Type tag + CMG number in marginalia style
- Guideline title in `font-headline text-xl` serif
- Section label underneath

### Content (scrollable)

- Renders `content_markdown` as formatted HTML
- `####` sub-section headers: `font-headline` serif
- Body text: `font-body` Space Grotesk
- Lists: hanging indent style (ruled-notebook margin rule)
- Dose tables (from `dose_lookup`): minimal styled table within the panel

### Footer (sticky bottom)

- "Start Revision" button (primary style, full width)
- On click: inline scope picker appears above the button with three options:
  - **This Guideline** — quiz scoped to just this CMG/med/CSM
  - **This Section** — quiz scoped to the section category
  - **All Guidelines** — quiz across everything
- Selecting a scope navigates to `/quiz` (FocusLayout) with route state: `{ scope, guidelineId, section }`

## Backend Endpoints

New router: `src/python/guidelines/router.py`, mounted at `/guidelines` prefix.

### `GET /guidelines`

Returns array of guideline summaries (not full content):

```json
[
  {
    "id": "CMG_23_Stroke",
    "cmg_number": "23",
    "title": "Stroke",
    "section": "Neurology",
    "source_type": "cmg",
    "mastery_score": 0.72
  }
]
```

Query params: `?type=cmg&section=Cardiac`
Reads from `data/cmgs/structured/` JSON files.

### `GET /guidelines/{id}`

Returns full `CMGGuideline` object including `content_markdown`, `dose_lookup`, `flowchart`.
ID matches filename stem (e.g. `CMG_23_Stroke`).

## Data Flow & State

### Frontend hooks

- `useGuidelines(type?, section?)` — calls `GET /guidelines` with filters. Uses `useApi` pattern.
- `useGuideline(id)` — calls `GET /guidelines/{id}`. Fires on card click (side panel opens).

### Page state (local)

- `selectedType`: "all" | "cmg" | "med" | "csm"
- `selectedSection`: string | null
- `selectedGuidelineId`: string | null (null = panel closed)
- `scopePickerOpen`: boolean

### Grouping logic

- Client-side grouping by `section` field
- Empty groups hidden
- Fixed category order as listed above

### Quiz launch flow

1. User clicks "Start Revision" → `scopePickerOpen = true`
2. User selects scope → navigate to `/quiz` with route state `{ scope, guidelineId, section }`
3. Existing `Quiz` page consumes scope state to configure the session

## Navigation Changes

- Sidebar: rename "Clinical Protocols" → "Clinical Guidelines", update path from `/quiz` → `/guidelines`
- `App.tsx`: add `/guidelines` route pointing to new `Guidelines` page component (use `StandardLayout`)
- "Start Revision" button in sidebar remains pointing to `/quiz`

## Design Rules (Archival Protocol)

- No `1px solid` borders — use background shifts, whitespace, ghost borders at max 15% opacity
- Surface hierarchy: `surface` (base) → `surface-container-low` (groupings) → `surface-container-lowest` (cards)
- Typography: Newsreader serif for headlines/titles, Space Grotesk sans-serif for body/labels
- Accent: `primary` (#2D5A54) for authority actions, `tertiary_fixed` (#dae058) for highlights
- Elevation: ambient diffuse shadow only, no Material shadows
- Cards: no dividers, hover = shift to white background, no scale
