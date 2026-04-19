# Multi-Ambulance-Service Support — Design Spec

**Date:** 2026-04-19
**Status:** Draft (pending spec review + user approval)
**Scope:** Add support for multiple Australian ambulance services to the Clinical Recall Assistant. First new service: Ambulance Tasmania (AT). Design is extensible so additional services (NSWA, AV, SAAS, QAS, SAJ, WAA, NTA) can be added with the minimum possible code changes.

---

## 1. Goals and non-goals

### Goals

- Allow the app to be configured for any registered Australian ambulance service, so the user is quizzed only on that service's guidelines (and only on personal material they've opted in to share across services).
- Provide a clean extension point so adding a new service is additive, not a refactor.
- Scrape, clean, structure, and ingest the full Ambulance Tasmania CPG library — text, dose tables, flowcharts, and versioning — to parity with the existing ACTAS CMG pipeline.
- Model scope-of-practice correctly and verifiably per service so quiz retrieval filters never show out-of-scope content.
- Guarantee zero cross-service bleed in retrieval, quiz generation, mastery tracking, and history.

### Non-goals

- No multi-user runtime support on a single install. Each install serves one paramedic configured once.
- No cross-service comparison features (e.g., "how does ACTAS dose adrenaline vs AT"). Clean silos only.
- No cloud sync, account system, or authentication.
- No vision-LLM pipeline beyond what is required for Tas flowcharts.

---

## 2. Decisions (captured from brainstorming)

| # | Decision | Choice |
|---|---|---|
| 1 | Service selection model | Single active service; explicit switch in Settings. |
| 2 | ChromaDB layout | One collection per service (no shared collection). |
| 3 | Personal docs (REF/CPD/notes/uploads) | Per-document `service` + `scope` tag (`service-specific` or `general`). Retrieval includes active-service docs plus those marked `general`. |
| 4 | Qualification filter | Multi-select per-user qualification declaration (base + additive endorsements); quiz filters out content requiring qualifications the user does not have. |
| 5 | Tas scraping scope | Full parity with ACTAS — text, dose tables, flowcharts, versioning, cross-references. |
| 6 | Mastery/history | Per-service silos. Switching service shows a fresh heatmap until the user quizzes on the new service. |
| 7 | Multi-user scope | Single user per install. No profile switcher. Multi-service is a codebase concern, not a runtime concern. |

---

## 3. Service model

### 3.1 Registry

A single registry at `src/python/services/registry.py` declares every supported service. The registry is the one place that changes when a new service is added.

Each entry:

```python
Service(
    id="actas",                         # stable slug; used in paths, collection names, SQLite
    display_name="ACT Ambulance Service",
    region="Australian Capital Territory",
    accent_colour="#2D5A54",
    source_url="https://cmg.ambulance.act.gov.au",
    scope_source_doc="Guides/scope-of-practice-actas.md",  # REQUIRED citation
    qualifications=QualificationModel(
        bases=[Base("AP", display="Ambulance Paramedic", implies=[]),
               Base("ICP", display="Intensive Care Paramedic", implies=["AP"])],
        endorsements=[],
    ),
    adapter="src.python.pipeline.actas",    # dotted path to the service adapter package
    category_mapping_doc="Guides/categories-actas.md",
)
```

The Tasmania entry:

```python
Service(
    id="at",
    display_name="Ambulance Tasmania",
    region="Tasmania",
    accent_colour="#005a96",
    source_url="https://cpg.ambulance.tas.gov.au",
    scope_source_doc="Guides/scope-of-practice-at.md",
    qualifications=QualificationModel(
        bases=[
            Base("VAO", display="Volunteer Ambulance Officer", implies=[]),
            Base("PARAMEDIC", display="Paramedic", implies=[]),   # VAO does NOT roll up
        ],
        endorsements=[
            Endorsement("ICP", display="Intensive Care Paramedic", requires_base=["PARAMEDIC"]),
            Endorsement("PACER", display="PACER", requires_base=["PARAMEDIC"]),
            Endorsement("CP_ECP", display="Community Paramedic / Extended Care Paramedic",
                        requires_base=["PARAMEDIC"]),
        ],
    ),
    adapter="src.python.pipeline.at",
    category_mapping_doc="Guides/categories-at.md",
)
```

### 3.2 Qualification semantics

Each content item carries `qualifications_required: list[str]` (qualification IDs — bases or endorsements). The user's *effective qualification set* is:

```
selected_base_implies = closure of the selected base's `implies` graph
effective = {selected_base} ∪ selected_base_implies ∪ selected_endorsements
```

A guideline is in-scope for quizzing iff `set(qualifications_required) ⊆ effective` (empty `qualifications_required` = universally in-scope).

GAP paramedics (ACTAS) are explicitly excluded from the qualification list — GAPs study AP scope, so they select AP.

### 3.3 Frontend exposure

`GET /services` returns the registry (stripped of adapter paths) so the frontend can render the setup modal and settings without hard-coding services.

---

## 4. Shared `GuidelineDocument` schema

All service adapters produce documents conforming to a single pydantic model (`src/python/services/schema.py`):

```python
class GuidelineDocument(BaseModel):
    service: str                         # service id
    guideline_id: str                    # service-scoped stable id (e.g. "CMG_14", "AT_CPG_Anaphylaxis")
    title: str
    categories: list[str]                # project-wide broad categories, mapped via category_mapping_doc
    qualifications_required: list[str]
    content_sections: list[ContentSection]
    medications: list[MedicationDose]
    flowcharts: list[Flowchart]
    references: list[Reference]
    source_url: str | None
    source_hash: str                     # for change detection
    last_modified: date | None
    extra: dict                          # service-specific metadata; not consumed by quiz/retriever
```

The existing ACTAS CMG JSON files become valid `GuidelineDocument`s after a light refactor (mostly renaming `cmg_number` → `guideline_id`, adding `service: "actas"`).

---

## 5. Data storage and isolation

### 5.1 ChromaDB — collection per service

| Collection | Contents |
|---|---|
| `guidelines_<service_id>` | Official guidelines for that service (CMGs / CPGs). |
| `personal_<service_id>` | Personal notes, REF docs, CPD docs, and uploads that belong to that service or are marked `general`. Each chunk carries `service` and `scope`. |

Retrieval for the active service queries exactly two collections:

```python
results = guidelines_collection.query(...) \
        + personal_collection.query(where={"$or": [{"service": active}, {"scope": "general"}]})
```

No chunk carrying `service != active` and `scope != "general"` can ever surface. This isolation is test-enforced (§10).

### 5.2 On-disk layout

```
data/
├── services/
│   ├── actas/
│   │   └── structured/           # per-guideline JSON (migrated from data/cmgs/structured/)
│   └── at/
│       └── structured/
├── personal_docs/
│   └── structured/               # existing; every file gains `service` + `scope` front-matter fields
├── uploads/
│   └── structured/               # existing; same tagging
└── chroma_db/                    # now holds multiple collections
```

`build/resources/data/services/<service_id>/structured/` bundles official content in packaged builds, mirroring how ACTAS CMG structured data is bundled today.

### 5.3 `paths.py` changes

Replace:

- `CMG_STRUCTURED_DIR` → removed
- `USER_CMG_STRUCTURED_DIR` → removed
- `resolve_cmg_structured_dir()` → removed

Add:

- `service_structured_dir(service_id)`
- `user_service_structured_dir(service_id)`
- `resolve_service_structured_dir(service_id)` — same precedence rule (user dir > bundled dir) as the old function.

All callers (medication router, guidelines router, seed, chunker) are updated in lock-step.

### 5.4 SQLite (quiz store)

`mastery.db` schema gains a `service TEXT NOT NULL` column on:

- `questions`
- `sessions`
- `mastery`
- `history`

All queries in `src/python/quiz/store.py` add `WHERE service = ?`. Existing rows are backfilled to `actas` on migration.

---

## 6. Settings, first-run UX, frontend

### 6.1 First-run

On app launch, if `config/settings.json` does not contain `active_service`, a blocking modal appears:

1. Choose service (radio, rendered from `GET /services`).
2. Choose base qualification (radio, dynamic from chosen service).
3. Tick applicable endorsements (checkboxes, filtered to those whose `requires_base` matches the chosen base).
4. Save → writes `active_service`, `base_qualification`, `endorsements` to `settings.json`.

The user cannot reach any other screen until this is completed.

### 6.2 Sidebar

A compact "service chip" in the sidebar shows the active service's display name and accent colour. Clicking it opens the same service/qualification edit dialog from Settings.

### 6.3 Settings page

New sections:

- **Active service** (radio, switch confirms with a warning).
- **Qualifications** (base radio + endorsement checkboxes, dynamic).
- **Personal documents** — table of all personal docs with per-row `service` dropdown (one of the registered services) and `scope` dropdown (`service-specific` or `general`). Saving re-tags the chunk metadata in the personal collection for that document.

Switching `active_service` shows a confirmation: "All quizzes, guidelines, medication reference, and mastery will now be filtered to <new service>. Existing <old service> data is preserved and will return if you switch back."

### 6.4 Backend statefulness

The backend reads `active_service` from `settings.json` on each request, rather than accepting a query parameter from the frontend. This removes a whole class of bug (frontend sending the wrong service id) and makes isolation testable as a backend invariant.

### 6.5 Page impact

Every content page (Dashboard, Quiz, Feedback, Library, Medication, Guidelines) gets a subtle service chip in its header. No page shows cross-service data under any path.

---

## 7. Ambulance Tasmania scraping pipeline

### 7.1 Structure

New adapter at `src/python/pipeline/at/` mirroring `src/python/pipeline/cmg/`:

```
pipeline/at/
├── discover.py
├── extractor.py
├── content_extractor.py
├── dose_tables.py
├── flowcharts.py
├── structurer.py
├── chunker.py
├── orchestrator.py
├── version_tracker.py
└── __init__.py          # registers `run_pipeline()` for the service registry adapter contract
```

### 7.2 Phase 0 — Discovery (gate)

Static inspection of the Tas main JS bundle (`main.8dc81c14ca768807.js`, ~10 MB) found:

- Angular/Ionic SPA with `<base href="/">` and client-side routing under `/tabs/guidelines`.
- AWS AppSync GraphQL endpoint `https://ziyqflv7avh6zjrkvmhe7s3rxy.appsync-api.ap-southeast-2.amazonaws.com/graphql` with ops `ListNotes`, `ListFavouritess`, `ListUsers`, and their CRUD siblings — all user-specific, **not clinical content**.
- Only asset URLs: two PDFs (`ChildSafetyWellbeingConcerns.pdf`, `SupportResourcesMembersPublic.pdf`) and two images (`LundandBrowder.png`, `WallaceRuleofNines.png`). No Mermaid library. No large structured JSON blobs.
- String `"title":"Flowchart"` present — flowcharts are first-class content.

Static inspection therefore does **not** reveal where clinical content lives. Discovery step (required before any extraction code):

1. Use Playwright to load the app, accept any cookie/terms modal, and navigate every top-level category and a sample of guidelines. Record all network traffic (XHR, `fetch`, WebSocket, service-worker cache).
2. Identify the clinical content source — expected to be one of:
   - Lazy-loaded JSON files from an S3/CloudFront CDN (most likely).
   - A GraphQL query (possibly public/Cognito-identity-pool-authed) distinct from user ops.
   - Chunks served by an Angular lazy route we missed statically.
3. Capture three representative guidelines end-to-end: a text-only CPG, one with dose tables, one with flowcharts.
4. For each content type observed, note: delivery format, MIME type, auth requirements, asset URL patterns, and any indexing endpoint (a "list all guidelines" call).

**Deliverable:** `Guides/at-cpg-extraction-findings.md` committed to the repo. No extraction code is written until this is reviewed and approved.

### 7.3 Phase 1 — Text + metadata

Based on findings:

- Implement `discover.py` to enumerate every guideline.
- Implement `content_extractor.py` to extract clinical text, section tree, categories, `qualifications_required`, `source_url`, and `last_modified`.
- `structurer.py` maps AT's scope tags to the canonical qualification IDs (`VAO`, `PARAMEDIC`, `ICP`, `PACER`, `CP_ECP`).
- `structurer.py` maps AT's category taxonomy to the project's broad study categories via `Guides/categories-at.md` (reviewed with the user before being committed).
- Output: `data/services/at/structured/AT_CPG_<id>.json` files, each a valid `GuidelineDocument`.

### 7.4 Phase 2 — Dose tables

- If dose information is structured in the source data, extract directly.
- If embedded in prose, reuse the ACTAS `dose_tables.py` extraction approach: regex candidates → structured-prompt LLM normalisation → schema validation. Model defaults to the user's configured cleaning model.
- Output goes into the `medications[]` field of each `GuidelineDocument`.

### 7.5 Phase 3 — Flowcharts

Flowchart handling is a four-way decision tree based on Phase 0 findings:

1. **Data-driven nodes/edges JSON (preferred):** deterministic transform to Mermaid `graph TD`. No LLM. Fully audit-able.
2. **Rendered HTML/SVG with semantic DOM:** parse to node/edge graph, same transform.
3. **Raster image (PNG/JPG/bitmap SVG):** vision-LLM path. We don't have this implemented yet — ships as part of this project:
   - New module `src/python/llm/vision.py` with `describe_flowchart(image_bytes: bytes, model_id: str) -> MermaidGraph`.
   - Uses the active LLM provider abstraction; structured prompt captures nodes, directional edges, decision branches, and terminal outcomes.
   - Results cached by `sha256(image_bytes)` to avoid re-billing on re-runs.
   - Output marked `review_required: true` until the user approves it in the UI, mirroring the `[REVIEW_REQUIRED]` pattern used for Notability OCR.
4. **PDF:** rasterise the flowchart page via `pdf2image` / `pypdf` + Pillow, then route through path 3.

Each flowchart is stored with:

- Mermaid text (rendered in-app via a new `<FlowchartViewer>` component — Mermaid.js on the renderer side).
- Reference to the original asset (URL or bundled file path) for audit.
- `source_format` field so we can spot-check origin later.

### 7.6 Phase 4 — Versioning & refresh

- Hash each guideline's source content to `source_hash`.
- If AT exposes its own version signal (content-updated timestamp, etag, or a "version" field in its API), prefer that over content hashing.
- On re-scrape, diff hashes and queue only changed guidelines for re-ingestion.
- A "Refresh service content" button in Settings triggers a background pipeline run; ChromaDB updates are transactional per guideline.

### 7.7 Bundled + fetched data

- Tas structured JSON bundled into `build/resources/data/services/at/structured/` for packaged builds.
- `guidelines_at` ChromaDB collection pre-built and included in the release payload alongside `guidelines_actas`.
- Personal builds (`electron-builder.personal.yml`) continue to fetch user-specific ChromaDB data from GitHub Releases; release payload now includes both services' pre-built collections.

---

## 8. Adding future services

`Guides/adding-a-service.md` (new) documents the repeatable recipe:

1. Source and commit a scope-of-practice document for the service (`Guides/scope-of-practice-<id>.md`).
2. Source and commit a category mapping document (`Guides/categories-<id>.md`).
3. Add a `Service(...)` entry to the registry with verified qualification model.
4. Create `src/python/pipeline/<id>/` adapter; implement the `run_pipeline()` contract.
5. Run Phase 0 discovery; commit findings doc.
6. Implement Phases 1–4; each phase gated by user review of outputs.
7. Add bundle rules to `electron-builder.yml` / `electron-builder.personal.yml`.
8. Add service-specific tests (qualification model, adapter contract, golden flowcharts).
9. User sign-off checklist: qualification model verified against source, sample guidelines reviewed, flowchart quality reviewed, quiz generation reviewed end-to-end.

No other code in the project needs to change to add a service.

---

## 9. Migration from current state

One-shot migration script `scripts/migrate_to_multi_service.py`:

1. Move `data/cmgs/structured/*` → `data/services/actas/structured/*`.
2. Move bundled `build/resources/data/chroma_db/` → rebuild as `guidelines_actas` collection (old default collection name deleted only after user confirms via a Settings "Clean up legacy data" button, not during migration itself).
3. Re-ingest ACTAS structured files into `guidelines_actas`.
4. Personal collection: ingest existing REF/CPD/notability/upload chunks into `personal_actas`. Default every existing personal doc to `service: "actas"`, `scope: "service-specific"`.
5. SQLite backfill: `UPDATE questions/sessions/mastery/history SET service = 'actas' WHERE service IS NULL`.
6. Write `active_service: "actas"`, `base_qualification: "AP"`, `endorsements: []` to `settings.json` as a safe default (user will be prompted via the first-run modal on next launch to confirm).
7. After migration, the user is prompted once in Settings to review each personal document and optionally retag its `scope` to `general`.

The old paths are left intact. Removal happens only on explicit user action.

---

## 10. Testing strategy

| Layer | Tests |
|---|---|
| Service registry | Unit tests for qualification implication math per registered service. Golden cases per service: specific content item + user qual set → expected in-scope/out-of-scope verdict. |
| Adapter contract | Each registered adapter must produce `GuidelineDocument` objects that pass schema validation. Shared fixture set runs against every adapter. |
| Collection isolation | Ingest two services' fixtures, run a retrieval query for service A, assert zero hits from service B's collection under any code path. |
| Migration | Run against a snapshot of current ACTAS data; assert every pre-migration file is reachable post-migration and every chunk resides in `guidelines_actas`. |
| Tas Phase 0 | N/A (discovery only). Manual review of findings doc. |
| Tas Phases 1–3 | Unit + integration tests per adapter module. Golden-set test for the vision flowchart path: ≥5 real AT flowcharts with hand-authored Mermaid ground truth; tolerance on node/edge set equivalence (not string equality). Gated behind `AT_VISION_TESTS=1` env var to avoid burning API budget in routine CI. |
| Frontend | Vitest + Testing Library: first-run modal flow, service-switch confirmation, per-doc retag flow, page re-render on service change, stale-data clearing. |

Pre-existing test failures documented in `KNOWN_TEST_FAILURES.md` stay out of scope.

---

## 11. Key risks and mitigations

| Risk | Mitigation |
|---|---|
| Inaccurate qualification model for a new service | Scope-of-practice source document is a mandatory registry field and must be cited and reviewed before merge. |
| Tas clinical content source requires authentication we can't satisfy | Phase 0 is a hard gate. If discovery reveals a blocker (e.g., Cognito-backed content requiring per-user login), stop and surface options before writing extraction code. |
| Vision-LLM flowchart quality | Hash-keyed cache; `review_required: true` flag until user sign-off; allow per-flowchart re-run against a stronger model; golden-set test to catch regressions. |
| Migration is irreversible | Migration writes to new locations only. Legacy paths removed only via explicit user action in Settings. |
| Cross-service quiz bleed | Collection-per-service + backend-read-from-settings + isolation test make bleed a test-detected bug, not a silent failure. |
| Source-hierarchy rules differ per service | Each service's registry entry carries its own source hierarchy; retriever consults the active service's hierarchy, not a global one. |
| Tas flowchart format turns out to be mixed (some data-driven, some raster) | Each flowchart records `source_format`; adapter picks the right handler per flowchart. No global assumption. |

---

## 12. Rollout order (staged commits on one feature branch)

1. Shared schema + service registry + ACTAS adapter refactor (no behaviour change; all existing tests still pass).
2. Collection-per-service ChromaDB migration + `paths.py` refactor + SQLite service column + backfill.
3. Settings/first-run UX + service chip across pages + per-doc retag UI.
4. Tas Phase 0 discovery (committed findings doc, no production Tas code).
5. Tas Phase 1 (text + metadata) — landable once AT structured output validates.
6. Tas Phase 2 (dose tables).
7. Tas Phase 3 (flowcharts; introduces `llm/vision.py`).
8. Tas Phase 4 (versioning + refresh button).
9. `Guides/adding-a-service.md` + per-service sign-off checklist.

---

## 13. Out of scope (explicit)

- Authentication / account system.
- Cloud sync between installs.
- Profile switcher / multi-user runtime.
- Cross-service comparison UI.
- Vision OCR of handwritten or photographed non-flowchart content.
- Any service other than ACTAS and AT in this project (though the architecture is designed to absorb them).

---

## 14. Open questions for user review

1. Category mapping for AT (`Guides/categories-at.md`) — will be drafted during Phase 1 and submitted for review before ingestion.
2. Whether the Tas `VAO` qualification should be quiz-eligible at all — some VAO content is general-public-facing first aid; we may want to filter some of it out rather than include it. To be resolved based on Phase 1 findings.
3. Default ACTAS qualification after migration — the spec defaults to `AP` with no endorsements. User should confirm the first-run modal prompts clearly on next launch after migration rather than silently assuming `AP`.
