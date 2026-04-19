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

---

## 15. Revisions addressing spec review

This section clarifies and corrects items flagged in the spec review. It is authoritative where it conflicts with earlier sections.

### 15.1 Current state of collections and code

The current ChromaDB has two collections: `cmg_guidelines` (official ACTAS CMGs) and `paramedic_notes` (all personal material — REF docs, CPD docs, Notability notes, and uploads). The migration therefore is a split, not just a rename:

- `cmg_guidelines` → `guidelines_actas`.
- `paramedic_notes` → `personal_actas`. All existing chunks tagged `service: "actas"`, `scope: "service-specific"`. A user-triggered retag pass (Settings UI) allows flipping individual documents to `scope: "general"` after migration.

No chunks are lost; old collections are left in place until the user clicks "Clean up legacy data".

### 15.2 `paths.py` callers — full enumeration

All callers of the removed `CMG_STRUCTURED_DIR` / `USER_CMG_STRUCTURED_DIR` / `resolve_cmg_structured_dir()`:

- `src/python/guidelines/router.py`
- `src/python/medication/router.py`
- `src/python/seed.py`
- `src/python/pipeline/cmg/chunker.py`
- `src/python/pipeline/cmg/orchestrator.py`
- plus any tests that import them.

All are migrated in the same commit that adds the new `resolve_service_structured_dir(service_id)` helper. A repo-wide grep for `CMG_STRUCTURED_DIR` is the completeness check.

### 15.3 ACTAS adapter directory

`src/python/pipeline/cmg/` is renamed to `src/python/pipeline/actas/` (git mv) as part of step 1 of the rollout. The registry entry `adapter: "src.python.pipeline.actas"` matches the new path. This keeps the adapter path as a real module path, not a façade. CMG is ACTAS's term for guideline; the module is now named for the service, not the artefact.

### 15.4 `skill_level` setting migration

The current `skill_level` setting in `quiz/router.py` and `quiz/agent.py` hard-codes an ACTAS AP/ICP scope filter in the generation prompt. Migration:

- `skill_level: "AP"` → `base_qualification: "AP"`, `endorsements: []`.
- `skill_level: "ICP"` → `base_qualification: "ICP"`, `endorsements: []`.
- The hard-coded AP/ICP text in `agent.py` is removed; scope filtering moves to chunk-metadata-driven retrieval using `qualifications_required` per §3.2.
- The generation prompt is rewritten to be service-neutral and to take the active service's display name + qualifications set as inputs. It no longer references "ACTAS" or specific qualification names in its literal text.

Test added: migration test covering both `AP` and `ICP` legacy values.

### 15.5 `cmg_number` field rename

Renaming `cmg_number` → `guideline_id` is wider than "light refactor":

- `src/python/medication/router.py` and `src/python/guidelines/router.py` read `cmg_number` from JSON and emit it in API responses.
- The frontend `api.ts` consumes the field.

Resolution: the `GuidelineDocument` schema uses `guideline_id` as the canonical field, and for ACTAS the migration writes `guideline_id = "CMG_<n>"` and keeps the legacy `cmg_number` field populated in the `extra` blob for the duration of a deprecation window. Routers emit both field names; frontend is updated in the same release to prefer `guideline_id` and fall back to `cmg_number`. After one release, `cmg_number` is removed from both backend and frontend.

### 15.6 Seeding multiple services

`seed.py` is rewritten to iterate the service registry:

- On startup, for each registered service, check whether its `guidelines_<id>` collection exists in the user's ChromaDB. If not and a bundled copy exists at `APP_ROOT/data/services/<id>/structured/` + prebuilt ChromaDB segment, copy it in. Otherwise run that service's adapter's `run_pipeline()` as a dev-mode fallback.
- Personal collections (`personal_<id>`) are never auto-seeded; user imports/uploads populate them.

### 15.7 ACTAS `qualifications_required` backfill

Existing ACTAS CMG structured JSONs do not carry `qualifications_required`. Backfill approach:

- Default: every CMG section gets `qualifications_required: ["AP"]` (safe lower bound — visible to all paramedics).
- ICP-specific sections are identified via two signals combined: (a) the existing hard-coded ICP markers used by `agent.py`'s current filter, and (b) a one-time pass over the source data looking for ICP-tagged medicines, CSMs, and sections. Matches are written as `qualifications_required: ["ICP"]`.
- The backfill result is committed as a reviewable artefact (`Guides/actas-qualifications-backfill.md`) so the user can spot-check before production use. Follow-up corrections go through the same Settings retag UI as personal docs.

### 15.8 Upload pipeline changes

`src/python/upload/router.py` currently hard-codes `source_type = "cpd_doc"` and writes to `paramedic_notes`. Changes:

- Upload dialog (`UploadDialog.tsx`) gains a service dropdown (defaulting to active service) and a scope dropdown (defaulting to `service-specific`).
- `POST /upload` accepts `service` and `scope` params; stores the file into `data/services/<service>/uploads/` and ingests into `personal_<service>` with metadata.
- `source_type` stays as `upload` (existing value); service and scope are independent metadata fields.

### 15.9 Release and upload scripts

- `scripts/upload-personal-data.sh` is updated to enumerate `personal_<id>` collections and upload each as a separate asset per release. Naming convention: `personal_<service_id>.tar.gz`.
- `electron-builder.yml` bundling rule changes from a single `build/resources/data/chroma_db/` tree to per-service subtrees under `build/resources/data/services/<id>/`. Packaging scripts (`scripts/package-backend.sh`, `package-backend.ps1`) updated accordingly.

### 15.10 Frontend cache invalidation

`ResourceCacheProvider` must invalidate all cached data (medication, guidelines, mastery, history, search, uploads list) when `active_service` changes. Implementation: cache keys are namespaced by service id; changing service effectively swaps the key namespace, so in-memory entries for the prior service remain (for fast switch-back) but new-service entries are fetched fresh.

### 15.11 Cross-collection result ranking

Retrieval merges results from `guidelines_<service>` and `personal_<service>` collections. Raw ChromaDB distances across separate collections are not directly comparable because each collection has its own embedding distribution. Implementation:

- Normalise per-collection: for each collection's results, convert distance to a percentile rank within that collection's top-K.
- Merge on percentile rank, then apply the source-hierarchy boost (guidelines outrank personal, REF outranks CPD outranks notability, per §15.12).

This is the retriever's job; adapter code does not see it.

### 15.12 Per-service source hierarchy

The `Service` registry entry gains a `source_hierarchy` field listing the service's own ordered list of source types with relative weights:

```python
source_hierarchy=[
    ("guideline", 1.00),
    ("ref_doc",   0.80),
    ("cpd_doc",   0.60),
    ("notability",0.40),
    ("upload",    0.30),
]
```

`GuidelineDocument` / personal chunk metadata continues to carry `source_type`. The retriever multiplies the normalised rank (§15.11) by the service's source-type weight before sorting. CLAUDE.md's strict tier order is preserved via the default weights; a service may override order if a stronger local rule applies.

### 15.13 Vision provider capability matrix

`src/python/llm/vision.py` depends on provider support for image inputs. Confirmed at spec time:

- Anthropic Claude: supported.
- Google Gemini: supported.
- Z.ai GLM: vision support varies by model; implementation raises `VisionNotSupportedError` and the adapter falls back to Anthropic or Gemini per user preference.

Settings gets a "Vision model" row distinct from "Cleaning model" so the user can pin a specific vision-capable model without affecting other LLM calls.

### 15.14 Authoring prerequisites

Step 1 of the rollout (ACTAS adapter refactor) is expanded to include authoring:

- `Guides/scope-of-practice-actas.md`
- `Guides/categories-actas.md`
- `Guides/scope-of-practice-at.md` (before Phase 1 of the Tas scrape)
- `Guides/categories-at.md` (drafted during Phase 1, reviewed before ingestion)
- `Guides/adding-a-service.md`
- `Guides/actas-qualifications-backfill.md`
- `Guides/at-cpg-extraction-findings.md` (Phase 0 deliverable)

None of these exist today. All are gated prerequisites for their respective rollout steps.

### 15.15 Dashboard empty-state on service switch

When the user switches to a service they have not yet quizzed on:

- Knowledge heatmap shows an empty state with copy like "No mastery data yet for <service>. Start a quiz to begin tracking."
- Metrics tiles show dashes, not zeros, to distinguish "no data" from "poor performance".
- Recent entries list shows an empty state pointing to the Quiz page.

### 15.16 Test fixture sources (see §16.11 for updates)

The isolation and adapter-contract tests need two services' worth of fixtures:

- ACTAS fixtures: seeded from three existing `data/cmgs/structured/` files, trimmed to minimal content, committed under `tests/python/fixtures/services/actas/`.
- AT fixtures: authored from Phase 0 findings against three sample CPGs, committed under `tests/python/fixtures/services/at/` in the same commit as Phase 1 lands. Until Phase 1, AT-specific tests are skipped conditionally.


---

## 16. Second-review corrections

Addresses issues surfaced by the follow-up review of §15. Authoritative where it conflicts with earlier sections.

### 16.1 Complete caller list (supersedes §15.2)

Every module importing `CMG_STRUCTURED_DIR`, `USER_CMG_STRUCTURED_DIR`, or `resolve_cmg_structured_dir` must be migrated. Authoritative list based on repo grep:

- `src/python/guidelines/router.py`
- `src/python/medication/router.py`
- `src/python/seed.py`
- `src/python/settings/router.py` (including the "Re-run Pipeline" handler)
- `src/python/pipeline/cmg/chunker.py` (→ `pipeline/actas/chunker.py` after rename)
- `src/python/pipeline/cmg/orchestrator.py`
- `src/python/pipeline/cmg/web_structurer.py`
- `src/python/pipeline/cmg/refresh.py`
- any tests importing these names

Not a `paths.py` caller but shares the migration concern: `src/python/quiz/retriever.py` hard-codes the collection names `cmg_guidelines` and `paramedic_notes`. Migrate it in the same step.

The completeness check is `rg "CMG_STRUCTURED_DIR|USER_CMG_STRUCTURED_DIR|resolve_cmg_structured_dir|cmg_guidelines|paramedic_notes"` returning zero hits outside the registry and migration script.

### 16.2 Skill-level migration — additional files (supersedes §15.4)

Beyond `quiz/router.py` and `quiz/agent.py`, the `skill_level` concept lives in:

- `src/python/llm/factory.py` — defaults `skill_level: "AP"`.
- `src/python/quiz/retriever.py` — uses `skill_level` to filter chunks at retrieval time (this is the actual enforcement site; the prompt-level text is secondary).
- `src/python/quiz/models.py` — likely carries the field on request/response models.

All four files migrate together. The retriever's filter switches from `skill_level` equality/inclusion to the qualification-set membership rule in §3.2, backed by the `qualifications_required` chunk metadata populated by the §15.7 backfill.

### 16.3 `cmg_number` field touch points (supersedes §15.5)

Rename affects, at minimum:

- `src/python/guidelines/router.py` (API responses)
- `src/python/medication/router.py` (API responses)
- `src/python/quiz/models.py` (carries the field on question objects)
- `src/python/quiz/retriever.py` (populates the field in retrieval results)
- `src/renderer/types/api.ts` and every consuming component (Guidelines, Quiz, Feedback, Medication pages)
- Structured JSON files under `data/cmgs/structured/`

The deprecation window still applies: backend emits both `guideline_id` and legacy `cmg_number`; frontend prefers `guideline_id`, falls back to `cmg_number`. Legacy field removed in the release after the one that ships this project.

### 16.4 Section 7.1 correction

§7.1 should be read as "mirrors `src/python/pipeline/actas/`" (the post-rename path from §15.3), not `pipeline/cmg/`.

### 16.5 Upload on-disk layout (supersedes §5.2)

The §5.2 layout showing `data/uploads/structured/` is superseded. Uploads live at `data/services/<service_id>/uploads/<filename>` with structured output at `data/services/<service_id>/uploads/structured/<filename>.json`. Existing `data/uploads/` content is migrated to `data/services/actas/uploads/` during migration (§9). The upload router writes to the active service's directory by default; user may override both service and scope at upload time (§15.8).

### 16.6 Bundled ChromaDB per service (supersedes §5.2, §15.9)

`build/resources/data/chroma_db/` (a single Chroma tree) is replaced by per-service bundled Chroma trees at `build/resources/data/services/<service_id>/chroma/`. Because Chroma does not export a single collection cleanly, the build-time script produces each service's tree by running a fresh Chroma instance that ingests only that service's structured data. This happens at packaging time, not at first launch.

`seed.py` first-launch behaviour: for each registered service, copy `build/resources/data/services/<service_id>/chroma/` into the user ChromaDB path if the corresponding `guidelines_<service_id>` collection is absent. If no bundled tree exists for a service (dev builds), fall back to running that service's adapter to populate the collection.

### 16.7 Medication router rewiring

The medication router currently reads flat per-medication JSON files under `data/cmgs/structured/`. The spec's `GuidelineDocument.medications: list[MedicationDose]` field does not by itself replace that data source; the medication browser needs an index across all guidelines.

Resolution: the ACTAS adapter writes both per-guideline `GuidelineDocument` JSON files and a denormalised `data/services/<service_id>/medications/<med_id>.json` index file for each medication extracted across that service's guidelines. The medication router is parameterised by active service and reads from `data/services/<active>/medications/`. The AT adapter produces the same index in the same format. Schema for these index files is documented in §4 (`MedicationDose`) plus `service`, `guideline_id`, `source_file`.

### 16.8 Personal doc front-matter vs chunk metadata

`data/personal_docs/structured/` gains front-matter fields `service` and `scope` on every file. For the 11 existing files, migration adds `service: "actas"`, `scope: "service-specific"`. During retagging, front-matter is the authoritative source; chunk metadata is derived from the front-matter on re-ingest. The Settings retag UI rewrites the front-matter and triggers a re-ingest for that file only.

### 16.9 Qualifications backfill is a prerequisite of retrieval migration

The §15.7 backfill for ACTAS `qualifications_required` is a prerequisite of migrating `quiz/retriever.py` to the new qualification-set filter. The rollout order is refined:

- Step 2a — collection split + SQLite service column + `paths.py` refactor.
- Step 2b — ACTAS `qualifications_required` backfill committed as structured-data change + `Guides/actas-qualifications-backfill.md` for review.
- Step 2c — retriever, router, factory, models switched to qualification-set filter; legacy `skill_level` removed.
- Step 2a and 2b are landable independently; 2c cannot land until 2b is merged.

### 16.10 CMG module rename vs Tas adapter — single source of truth

Directory layout post-rollout:

```
src/python/pipeline/
├── actas/          # renamed from cmg/
│   └── ... (existing ACTAS pipeline modules)
├── at/             # new Tas adapter
│   └── ...
└── personal_docs/  # unchanged
```

§7.1's "mirrors the ACTAS pipeline" wording refers to `pipeline/actas/` (the renamed module), not `pipeline/cmg/`.

### 16.11 Test fixtures — restated

- ACTAS fixtures: trimmed copies of three representative `data/services/actas/structured/` files committed under `tests/python/fixtures/services/actas/`. These include `qualifications_required` values matching what the §15.7 backfill produces.
- AT fixtures: authored during Phase 1 from real AT CPGs, committed under `tests/python/fixtures/services/at/` in the same commit that lands Phase 1.
- Isolation and adapter-contract tests use both sets; AT tests are conditionally skipped until Phase 1 lands via a pytest marker.
