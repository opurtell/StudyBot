# AT CPG Leaf Guideline Scraper — Design

## Problem

155 structured CPG files (`data/services/at/structured/CPG_*.json`) are stubs with zero content. The existing scraper (`scripts/at_scrape_all.py`) navigated to category pages which only show lists of sub-guidelines, never visiting individual leaf pages that contain actual clinical content.

## Approach

Two-phase Playwright scraper with multi-level qualification coverage.

### Phase 1 — Discovery

For each qualification level (Paramedic, ICP, CPECP, CFP, PACER, DTP):

1. Select the level on the AT CPG site
2. Navigate to each guideline category (Adult, Paediatric, Maternity, Reference Notes, In Field Referrals)
3. Collect all leaf-level items and their URLs (those with `angle-double-right` icon)
4. Deduplicate by URL — skip pages already discovered at a prior level
5. Record the `atp` level for each discovered guideline

### Phase 2 — Scrape

For each discovered leaf page:

1. Navigate directly to the URL
2. Wait for Angular lazy-loading (~2s)
3. Dismiss modals (force-remove `ion-modal` from DOM)
4. Extract structured content: title, section headings, body text, full text
5. Save raw JSON to `data/at/raw/`
6. Map scraped content back to the corresponding `CPG_*.json` in `data/services/at/structured/`, filling in `content_markdown`

### Site Interaction

- Select qualification level on first visit
- Force-remove disclaimer modals (`ion-modal`, `ion-backdrop`)
- ~2s wait per page for Angular lazy-loading
- Handle back-navigation between pages
- Headless Chromium with desktop viewport

### Deduplication

- URLs are the deduplication key
- Each level may show a superset of prior levels
- Only new pages at each level are scraped
- The `atp` field on each structured file is updated to reflect all levels where the guideline appears

### Output

- Raw scraped JSON: `data/at/raw/{slug}.json`
- Updated structured files: `data/services/at/structured/CPG_*.json` with populated `content_markdown`
- Discovery manifest: `data/at/investigation/leaf_urls.json`

### Qualification Levels

Ordered from broadest to most restricted:

1. Paramedic (`p`) — baseline
2. ICP (`icp`) — may show additional ICP-only guidelines
3. CPECP (`cpecp`) — extended care protocols
4. CFP (`cfp`) — Community First Paramedic (note: `-cfp` suffix pages)
5. PACER (`pacer`) — Mental health co-responder
6. DTP (`dtp`) — Direct Treatment Protocol (e.g. cetirizine-dtp, loperamide-dtp)
