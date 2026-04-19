# Ambulance Tasmania CPG Extraction -- Phase 0 Findings

> **Probed:** 2026-04-19
> **Site:** <https://cpg.ambulance.tas.gov.au>
> **Probe script:** `scripts/at_phase0_probe.py` (v3.0.0)
> **Raw data:** `tmp/at-phase0/phase0_findings.json`

---

## 1. Site Architecture

| Property | Value |
|----------|-------|
| Framework | **Angular** (detected `ng-version` attribute) + **Ionic** (`ion-app`, `ion-tabs`, `ion-content`, `ion-modal`) |
| Bundle tool | Webpack (angular.json build, hashed filenames) |
| Base HTML size | ~97--109 KB (SPA shell only) |
| CSS | Hashed per route (e.g. `styles.065c86f46dc3f617.css` for home, `styles.d5d60007df7381c6.css` for `/tabs/guidelines`) |
| PWA | Yes (`apple-mobile-web-app-capable`, `site.webmanifest`) |
| App meta | `AT CPG` |
| Firebase project | `at-cpg` (project ID visible in Firebase installation endpoint) |

### Comparison with ACTAS CMG Site

The AT site is architecturally identical to the ACTAS site (`cmg.ambulance.act.gov.au`):

- Same Angular + Ionic SPA pattern
- Same heavy code-splitting (420+ JS bundles detected)
- Same hashed CSS per route
- Same disclaimer modal on first load
- Same bottom tab navigation (Home, Medicines, Calculators, Checklists)

The key difference is the AT site uses **qualification level selection** as a second modal/gate before showing guideline content.

---

## 2. Content Source and Delivery

### 2.1 No External API

The AT site does **not** call any JSON API endpoints. All API-like paths (`/api/guidelines`, `/api/cpg`, `/api/v1/guidelines`, `/assets/data/guidelines.json`) return the SPA HTML shell (`text/html`, status 200) -- they are catch-all routes served by the Angular SPA.

### 2.2 No Backend Data Fetching (XHR/Fetch)

During the entire probe session, the only XHR/fetch requests were:

1. **Firebase webConfig** -- `https://firebase.googleapis.com/v1alpha/projects/-/apps/1:202475266464:web:69a79581809bd50d6a04c5/webConfig` (app configuration)
2. **Firebase installation** -- `https://firebaseinstallations.googleapis.com/v1/projects/at-cpg/installations` (analytics identity)
3. **SVG fetch** -- `https://cpg.ambulance.tas.gov.au/svg/person-circle.svg` (user icon)

No guideline data, medicine data, or clinical content was fetched via XHR/fetch. This means **all clinical content is embedded in the JS bundles**, exactly like the ACTAS site.

### 2.3 Data in JS Bundles

| Bundle | Size | Content |
|--------|------|---------|
| `main.*.js` | **9.48 MB** | App shell, routing, auth (Cognito + Firebase), qualification levels, CPG number registry (168 unique), medicine names |
| `common.*.js` | **882 KB** | Shared components, dose tables, flowchart references, medicine data (604 name references, 29 CPG numbers), route definitions (95 routes) |
| Lazy chunks | ~418 bundles | Per-guideline content loaded on demand (code-split by Angular router) |

The **main bundle** (9.48 MB) is the primary data source, matching the ACTAS pattern where the main JS bundle contained the full guideline data model.

---

## 3. Authentication Requirements

### 3.1 Public Access

The site is **publicly accessible without authentication**. All guideline content, medicine monographs, and calculators load without signing in.

### 3.2 Auth-Gated Features Only

Authentication (AWS Cognito) is used only for:

- **"My Notes"** -- personal annotation on medicine pages (shows "You must sign in to view your personal notes")
- **"Recent"** and **"Favourites"** tabs in the top navigation
- **"Sign in"** and **"Forgot your password?"** buttons visible in the top-right corner

The `main` bundle confirms Cognito integration (`has_cognito: true`, `has_auth_guard: true`), but the AuthGuard is applied only to specific routes (likely `/auth`, `/edit`), not to content pages.

### 3.3 Disclaimer Modal

A mandatory disclaimer modal appears on first load. It must be dismissed by clicking "OK" before content becomes interactive. The text reads:

> "Ambulance Tasmania's Clinical Practice Guidelines and Clinical Field Protocols are expressly intended for use by Ambulance Tasmania staff when performing duties and delivering ambulance services for, and on behalf of, Ambulance Tasmania..."

### 3.4 Level Selector

After dismissing the disclaimer, a **qualification level selector modal** appears with options:

- Community Paramedic/Extended Care Paramedic
- PACER
- Volunteer Ambulance Officer
- **Paramedic** (default active)
- Intensive Care Paramedic

This maps directly to the qualification model defined in `Guides/scope-of-practice-at.md`.

---

## 4. Per-Guideline Request Pattern

When navigating to a specific guideline page:

1. Browser requests the URL (e.g. `/tabs/guidelines/adult-patient-guidelines/cardiac-arrest`)
2. Server returns the SPA shell (same HTML for all routes)
3. Angular router matches the URL path and loads the corresponding lazy JS chunk
4. The JS chunk contains the guideline content as embedded data (text, dose tables, flowcharts)
5. Angular renders the content in the Ionic `<ion-content>` element

**No network request is made for the actual guideline data** -- it is already in the JS bundle loaded by the router.

---

## 5. Data Format Analysis

### 5.1 Text Content

Text content (indications, contraindications, pharmacology, special notes) is rendered as **HTML within Ionic components**. The Adrenaline medicine page shows structured sections:

- Common Trade Names
- Presentation
- Pharmacology (with alpha/beta receptor effects)
- Metabolism
- Primary Emergency Indication (with cross-references to CPG codes)
- Contraindications
- Precautions
- Route of Administration
- Interactions
- Side Effects
- Pregnancy Category
- Breastfeeding Category
- Special Notes
- Dose Recommendations (structured text with steps)

The text content is **not in JSON model form** -- it appears to be pre-compiled HTML or template strings within the JS bundles.

### 5.2 Dose Tables

The Adrenaline page shows dose information as **structured step-by-step text**, not as interactive lookup tables:

- Adult bolus dosing (dilution instructions)
- Adult infusion (hard max 100 microg/min, dilution recipe)
- Paediatric infusion (hard max 1 microg/kg/min, double-dilution steps)
- Paediatric bolus dosing (dilution steps)

Unlike the ACTAS site which had pre-computed weight-band lookup tables, the AT site presents dosing as **narrative instructions**. This means:

- No calculator-style lookup tables to extract
- Dose data must be parsed from structured text
- The "Medicine Calculator" tool in the Calculators tab may contain the actual dose computation logic

### 5.3 Flowcharts

The `common` bundle contains `has_flowchart_refs: true` and the route definitions include a `flowchart` route. The AT CPG site likely stores flowcharts as:

- **SVG images** or **embedded diagrams** within the JS bundles (same pattern as ACTAS)
- A dedicated `flowchart` route suggests flowcharts may be separate pages
- Vision LLM analysis of screenshots may be needed if flowcharts are raster images

### 5.4 Calculators

The Calculators tab contains four tools:

1. **Medicine Calculator** -- likely the dose lookup by weight/indication
2. **NEWS2 Score** -- National Early Warning Score
3. **CEWT Score** -- Children's Early Warning Tool
4. **Palliative Care Medication Calculator**

These are likely implemented as JavaScript logic within the bundles, not as separate API endpoints.

---

## 6. URL Patterns

### 6.1 Navigation Structure

```
/                                    -> Home (level selector + category buttons)
/tabs/guidelines                     -> Guidelines home (same as /)
/tabs/guidelines/adult-patient-guidelines           -> Adult guideline categories
/tabs/guidelines/adult-patient-guidelines/{slug}    -> Sub-guideline list
/tabs/guidelines/adult-patient-guidelines/{slug}/{sub-slug}  -> Individual guideline
/tabs/medicines                      -> Medicine list
/tabs/medicines/page/{medicine-name} -> Individual medicine monograph
/tabs/calculators                    -> Calculator list
/tabs/calculators/{calculator-slug}  -> Individual calculator
/tabs/checklists                     -> Checklist list
```

### 6.2 CPG Numbering Scheme

The AT CPG uses a structured numbering system:

| Prefix | Category | Example Range |
|--------|----------|---------------|
| `A0` | Adult Patient Guidelines | A0001, A0101--A0112, A0201--A0203, A0300--A0307, A0401--A0411, A0501, A0601--A0604, A0701--A0713, A0801--A0809, A0901--A0902 |
| `M` | Obstetrics | M001--M010 |
| `P` | Paediatric Patient Guidelines | P0201, P0401, P0601, P0602, P0704, P0710 |
| `D` | Drug/Medicine monographs | D002--D047 |
| `E` | Reference Notes / Environment | E002, E003, E006, E008, E009 |

Sub-guidelines use a hyphenated suffix (e.g. `A0201-1` for Medical Cardiac Arrest, `A0201-2` for Traumatic Cardiac Arrest).

### 6.3 Adult Guideline Categories (Confirmed)

| Category | CPG Range | Sub-items |
|----------|-----------|-----------|
| Assessment | A0101--A0112 | 12 items |
| Mental Health | A0106 | 1 item |
| Cardiac Arrest | A0201--A0203 | 5 sub-guidelines |
| Airway Management | A0300--A0307 | 8 items |
| Cardiac | A0401--A0411 | 11 items |
| Pain Relief | A0501 | 1 item |
| Respiratory | A0601--A0604 | 4 items |
| Medical | A0701--A0712 | 12 items |
| Trauma | A0801--A0809 | 9 items |
| Environment | A0901--A0902 | 2 items |
| Obstetrics | M001--M010 | 10 items |

### 6.4 Medicine Formulary (38 medicines confirmed)

| Medicine | CPG Code |
|----------|----------|
| Adenosine | D002 |
| Adrenaline | D003 |
| Amiodarone | D004 |
| Aspirin (Acetylsalicylic Acid) | D005 |
| Atropine | D006 |
| Ceftriaxone | D007 |
| Clopidogrel | D037 |
| Dexamethasone | D008 |
| Diazepam | D035 |
| Droperidol | D036 |
| Enoxaparin | D038 |
| Ergometrine | D009 |
| Fentanyl | D010 |
| Frusemide | D011 |
| Glucagon | D012 |
| Glucose 5% | D013 |
| Glucose 10% | D014 |
| Glucose Paste | D015 |
| Glyceryl Trinitrate (GTN) | D016 |
| Heparin | D039 |
| Ibuprofen | D041 |
| Ipratropium Bromide (Atrovent) | D017 |
| Ketamine | D018 |
| Lignocaine Hydrochloride | D019 |
| Magnesium Sulphate | D020 |
| Methoxyflurane | D021 |
| Metoclopramide | D022 |
| Midazolam | D023 |
| Morphine | D024 |
| Naloxone | D025 |
| Normal Saline | D026 |
| Ondansetron | D028 |
| Oxygen | D029 |
| Paracetamol | D030 |
| Prochlorperazine | D031 |
| Salbutamol | D032 |
| Sodium Bicarbonate 8.4% | D033 |
| Tenecteplase | D040 |
| Oxytocin | D047 |
| Tranexamic Acid | D042 |

---

## 7. Scope-of-Practice Matrix

The qualification level selector on the home page provides the scope-of-practice hierarchy:

1. **Volunteer Ambulance Officer** -- first-responder scope
2. **Paramedic** -- full ambulance paramedic scope (default)
3. **Intensive Care Paramedic** -- extended critical care
4. **PACER** -- specialised programme
5. **Community Paramedic / Extended Care Paramedic** -- community health

The level selector is a modal (not a separate URL). Selecting a level may filter which guidelines/medicines are visible, though this needs confirmation during extraction.

**No separate scope-of-practice matrix URL was found.** The matrix is embedded in the app's level selector logic.

---

## 8. Checklists and Tools

From the route analysis of the `common` bundle:

| Route | Type |
|-------|------|
| `medicine-calculator` | Calculator |
| `news-two` | Calculator |
| `cewt-score` | Calculator |
| `palliative-care-medication-calculator` | Calculator |
| `clinical-handover` | Checklist |
| `act-fast-tool` | Tool |
| `stemi-referral-script` | Checklist |
| `reperfusion-checklist` | Checklist |
| `cardiac-arrest-and-rosc-checklist` | Checklist |
| `virca-assessment-tool` | Tool |
| `cold-intubation-checklist` | Checklist |
| `sedation-checklist` | Checklist |
| `community-paramedic-internal-referral` | Form |
| `flowchart` | Flowchart viewer |
| `wallace-rules-of-nine` | Reference tool |
| `lund-and-browder` | Reference tool |

---

## 9. Version History

The Adrenaline medicine page shows a "Version history" section:

| Version | Date | Details |
|---------|------|---------|
| 1.0.8.1 | 16 December 2025 | Content update |
| 1.0.7.12 | 28 July 2025 | Updated information |

This confirms the site is actively maintained (last content update December 2025 as of the April 2026 probe).

---

## 10. Recommendations for Phases 1--4

### Phase 1: JS Bundle Extraction (Recommended)

Given the architectural similarity to the ACTAS site, the same extraction strategy should work:

1. **Download the main JS bundle** (`main.*.js`, ~9.5 MB) -- contains all CPG numbers, medicine names, qualification levels, route definitions
2. **Download the common JS bundle** (`common.*.js`, ~882 KB) -- contains shared data, dose table logic, flowchart references, calculator routes
3. **Download lazy-loaded chunks** (418+ bundles) -- each contains the actual guideline content for a specific CPG
4. **Parse the bundles** for structured data using the same regex/AST approach as the ACTAS extraction framework
5. **Key advantage**: The CPG numbering system (A0101, D003, etc.) provides a natural primary key for each guideline/medicine

### Phase 2: Content Rendering (Playwright)

For content that cannot be cleanly extracted from JS bundles:

1. Use Playwright to navigate to each guideline URL
2. Dismiss the disclaimer modal (click "OK")
3. Dismiss the level selector modal (force-remove `ion-modal` elements from DOM)
4. Extract the rendered text from `ion-content`
5. Capture screenshots for flowcharts (vision LLM fallback)

### Phase 3: Medicine Extraction

The medicine pages have rich structured data:

1. Navigate to each medicine page (`/tabs/medicines/page/{name}`)
2. Extract all sections (Trade Names, Presentation, Pharmacology, Indications, Contraindications, Dosing)
3. Cross-reference with the "Medicine Calculator" logic for dose computation rules
4. The dose format is narrative (step-by-step dilution instructions), not lookup tables

### Phase 4: Qualification-Level Filtering

1. Test whether selecting different qualification levels changes visible content
2. If filtering occurs, extract content at each level (VAO, Paramedic, ICP, PACER, CP/ECP)
3. Store per-level visibility metadata with each guideline/medicine

---

## 11. Blockers and Risks

### No Critical Blockers

The site is publicly accessible, has no anti-scraping measures, and serves all content without authentication. The only minor blocker is the modal overlay management (disclaimer + level selector), which the probe script already handles.

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| JS bundle hash changes on deploy | Medium | Re-probe to get current bundle URLs before each extraction run |
| Content changes between probe and extraction | Low | Version history is visible per medicine; use version numbers for change detection |
| Flowcharts are raster images | Medium | Use vision LLM to extract flowchart logic from screenshots |
| Qualification-level filtering changes visible content | Medium | Probe at each level during Phase 1 to determine scope |
| Bundle size (420+ chunks) makes full extraction slow | Low | Parallelise chunk downloads; most content is in `main` and `common` |

### Australian English Note

The site uses Australian English throughout (e.g. "metres", "microgram", "paediatric", "oesophagus", "haemorrhage"), matching our app's language requirements. No translation needed.

---

## 12. Scope-of-Practice URL Update

The `Guides/scope-of-practice-at.md` file has a TBD citation for the scope-of-practice matrix URL. Based on the probe findings:

- **There is no separate scope-of-practice matrix URL.** The scope-of-practice information is embedded in the app's qualification level selector modal, not published as a standalone page.
- The authoritative source is the AT CPG site itself: <https://cpg.ambulance.tas.gov.au>
- The level names visible in the selector match the qualification model in `scope-of-practice-at.md`

**Recommendation:** Update the TBD URL to cite the CPG site root (`https://cpg.ambulance.tas.gov.au`) and note that the scope matrix is app-embedded, not a separate document.

---

*Phase 0 probe complete. Findings committed alongside probe script for reproducibility.*
