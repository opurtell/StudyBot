# Adding a New Ambulance Service

This guide documents the repeatable process for integrating a new Australian ambulance
service into the app. It is written for a developer working with Claude Code and
references actual file paths and function signatures from the codebase.

The reference implementation is the ACTAS adapter at `src/python/pipeline/actas/`.
Ambulance Tasmania (`src/python/pipeline/at/`) follows the same contract.

---

## Prerequisites

Before starting, you need:

- The service's public Clinical Practice Guideline (CPG) / Clinical Management Guideline
  (CMG) website URL
- Access to the service's scope-of-practice documentation (public or supplied by the user)
- A short, stable identifier for the service (lowercase, no spaces — e.g. `actas`, `at`,
  `nswas`, `qas`)

---

## Step 1: Source and Commit Scope-of-Practice Document

Create `Guides/scope-of-practice-<id>.md` listing every qualification the service
uses, with a plain-language scope summary for each level.

### What to include

1. **Authoritative source URL** in a blockquote at the top (the CPG/CMG site, or a
   published scope-of-practice matrix if one exists).
2. **Every qualification level** the service recognises, including:
   - Full title and short ID (e.g. `AP`, `ICP`, `PARAMEDIC`, `VAO`)
   - Scope summary: procedures, medications, and restrictions
   - Whether it implies any other qualification
3. **Endorsements** if the service uses a base-plus-endorsement model, noting which
   base(s) each endorsement requires.
4. **Registry mapping snippet** — the `QualificationModel(...)` Python literal that
   will go into `registry.py`, so the scope-of-practice doc and registry entry stay
   in sync.
5. **ChromaDB collection** naming convention — guidelines will land in
   `guidelines_<id>`, personal docs in `personal_<id>`.
6. **Placeholder warnings** for any sections that cannot be filled in until Phase 0
   discovery is complete (see Step 4).

### Examples

- `Guides/scope-of-practice-actas.md` — two-level model (AP, ICP with implication)
- `Guides/scope-of-practice-at.md` — base-plus-endorsement model (VAO, PARAMEDIC +
  ICP/PACER/CP_ECP endorsements)

Mark sections that are unconfirmed with `[REVIEW REQUIRED]` tags. These get resolved
during Phase 0 discovery (Step 4) and user sign-off (Step 8).

---

## Step 2: Add the Service Registry Entry

Edit `src/python/services/registry.py` to add a `Service(...)` dataclass instance to
the `REGISTRY` tuple.

### Service dataclass fields

```python
@dataclass(frozen=True)
class Service:
    id: str                           # Unique identifier (e.g. "nswas")
    display_name: str                 # Human-readable name (e.g. "NSW Ambulance")
    region: str                       # State/territory (e.g. "New South Wales")
    accent_colour: str                # Hex colour for UI theming
    source_url: str                   # CPG/CMG website root URL
    scope_source_doc: str             # Path to scope-of-practice guide
    qualifications: QualificationModel  # Qualification structure
    adapter: str                      # Python module path for pipeline adapter
    category_mapping_doc: str         # Path to category mapping guide
    source_hierarchy: tuple[...]      # Optional: overrides SOURCE_HIERARCHY_DEFAULTS
```

### Qualification model

Define bases and endorsements using the dataclasses from the same file:

```python
from src.python.services.registry import Base, Endorsement, QualificationModel

# Two-level model (like ACTAS):
QualificationModel(
    bases=(
        Base("AP", "Ambulance Paramedic"),
        Base("ICP", "Intensive Care Paramedic", implies=("AP",)),
    ),
)

# Base-plus-endorsement model (like Ambulance Tasmania):
QualificationModel(
    bases=(
        Base("VAO", "Volunteer Ambulance Officer"),
        Base("PARAMEDIC", "Paramedic"),
    ),
    endorsements=(
        Endorsement("ICP", "Intensive Care Paramedic", requires_base=("PARAMEDIC",)),
    ),
)
```

### Qualification math

The `implies` field on `Base` and the `requires_base` field on `Endorsement` drive the
qualification math in `src/python/services/qualifications.py`:

- `effective_qualifications(base_id, endorsement_ids, service) -> frozenset[str]`
  computes the transitive closure of the base plus any valid endorsements.
- `is_in_scope(required, effective) -> bool` checks whether content is visible to the
  user.

Key rules:
- `implies` is transitive — if A implies B and B implies C, then A implies C.
- `requires_base` is enforced at validation time — passing an endorsement without the
  required base raises `ValueError`.
- Independent bases (like VAO and PARAMEDIC) have no implication relationship.

### Adapter module path

Set `adapter` to the dotted Python import path for the pipeline module:

```python
adapter="src.python.pipeline.<id>"
```

This module must expose a callable `run_pipeline()` at its top level (see Step 3).

---

## Step 3: Create the Adapter Pipeline Directory

Create `src/python/pipeline/<id>/` with the following minimum structure:

```
src/python/pipeline/<id>/
    __init__.py          # Exports run_pipeline
    orchestrator.py      # Chains stages, defines run_pipeline()
    discover.py          # Phase 0: Playwright probe of the CPG site
    ...                  # Additional stage modules as needed
```

### `__init__.py`

Must re-export `run_pipeline` so the adapter module is callable:

```python
"""<Service Name> CPG Extraction Pipeline"""

from .orchestrator import run_pipeline  # noqa: F401
```

### `orchestrator.py` — the `run_pipeline()` contract

The orchestrator defines the stages and exposes a single entry point:

```python
def run_pipeline(
    stages: str = "all",          # Comma-separated stage names, or "all"
    dry_run: bool = False,        # If True, skip ChromaDB writes
    **kwargs,                     # Service-specific options
) -> dict[str, Any]:
    ...
```

**Return value:** A dict with at minimum:

```python
{
    "stages": list[str],           # Stages that were requested
    "dry_run": bool,
    # ... stage-specific results
}
```

**Stage naming convention:** Follow the ACTAS pattern from
`src/python/pipeline/actas/orchestrator.py`:

```
navigation, routes, content, dose, merge, flowcharts, structure, chunk, version
```

Not all stages are required for every service. A simpler site may only need
`content, structure, chunk`. The key requirement is that the `chunk` stage writes
to the correct service-scoped ChromaDB collection.

### Reference implementation

Read `src/python/pipeline/actas/orchestrator.py` for the full stage-chaining pattern.
The ACTAS pipeline has these modules:

| Module | Purpose |
|--------|---------|
| `discover.py` | Playwright SPA crawler, saves raw guideline data |
| `discover_metadata.py` | Extracts JS bundle metadata and asset paths |
| `extractor.py` | Navigation tree and route mapping extraction |
| `content_extractor.py` | Per-guideline content extraction from raw data |
| `dose_tables.py` | Medication dose table extraction |
| `flowcharts.py` | Flowchart extraction (SVG, image, Mermaid.js) |
| `structurer.py` | Raw data to structured JSON conversion |
| `web_structurer.py` | Web-scraped content structuring |
| `template_parser.py` | CMG template format parsing |
| `chunker.py` | Text splitting and ChromaDB ingestion |
| `medications_index.py` | Medication index generation |
| `version_tracker.py` | Source version tracking for incremental updates |
| `refresh.py` | Incremental refresh logic |
| `models.py` | Pydantic schemas for the pipeline's data structures |
| `orchestrator.py` | Stage chaining and CLI entry point |

You do not need to replicate every module. The minimum viable adapter is:

```
src/python/pipeline/<id>/
    __init__.py
    orchestrator.py    # run_pipeline() with at least: content, structure, chunk
    chunker.py         # Service-scoped ChromaDB ingestion
```

---

## Step 4: Run Phase 0 Discovery

Phase 0 is a Playwright-based probe of the service's CPG/guideline website. Its goal
is to understand the site's architecture before building the full extraction pipeline.

### What to discover

1. **Site framework** — Is it a SPA (Angular/Ionic, React), server-rendered HTML, or a
   static site? This determines the extraction strategy.
2. **Content structure** — How are guidelines organised? Categories, sections, nested
   pages?
3. **Medication data** — Are doses embedded in guideline pages, in separate JS bundles,
   or in downloadable PDFs?
4. **Flowcharts** — Are they SVG, canvas-rendered, images, or embedded data?
5. **Authentication** — Is the site publicly accessible or does it require login?
6. **URL patterns** — Map the URL structure for scraping.
7. **Qualification markers** — Is content tagged by qualification level (e.g.
   "ICP only", "Paramedic")?

### How to run

Create `src/python/pipeline/<id>/discover.py` following the pattern in
`src/python/pipeline/actas/discover.py`. The ACTAS discover module uses Playwright
to:

1. Launch a headless browser
2. Navigate to the CPG site
3. Handle any modals (disclaimers, level selection)
4. Extract the navigation tree
5. Save raw content and a discovery summary

Run it:

```bash
cd src/python
python -m pipeline.<id>.discover
```

### Commit findings

Write results to `Guides/<id>-extraction-findings.md` covering:

- Site technology stack
- Content architecture (how guidelines are structured in the DOM/source)
- Medication data format and location
- Flowchart formats found
- Any authentication or anti-scraping measures
- Recommended extraction strategy
- Number of guidelines discovered
- Any content that requires manual handling (e.g. image-based flowcharts needing OCR)

---

## Step 5: Implement Ingestion Phases

Based on Phase 0 findings, implement the extraction stages. The general flow is:

### Phase 1: Content scraping

- If the site is a SPA with data in JS bundles (like ACTAS): extract the raw JSON from
  the JavaScript, following `src/python/pipeline/actas/extractor.py`.
- If the site is server-rendered HTML: use Playwright or requests + BeautifulSoup4 to
  crawl and extract content.
- If the site serves PDFs: download and parse them with `pypdf`.

Save raw extracted data to a staging directory (e.g. `data/<id>/raw/`).

### Phase 2: Dose-table extraction

If the service has structured medication dosing (most Australian ambulance services do):

- Extract medicine names, indications, routes, doses, weight bands
- Look for pre-computed lookup tables (ACTAS uses these) or formula-based calculators
- Follow the pattern in `src/python/pipeline/actas/dose_tables.py`

### Phase 3: Flowchart handling

- Convert flowcharts to Mermaid.js where possible
- For image-based flowcharts, use a vision LLM for OCR conversion
- Flag uncertain conversions with `review_required: true`
- Follow the pattern in `src/python/pipeline/actas/flowcharts.py`

### Phase 4: Qualifications backfill

Tag every piece of content with its `qualifications_required`:

- Content available to all levels: `qualifications_required: []`
- Content restricted to a specific level: `qualifications_required: ["ICP"]`
- This drives the visibility filter in the retriever (see
  `src/python/quiz/retriever.py` method `_build_where()`)

The qualifications data flows through the schema in
`src/python/services/schema.py` — each `ContentSection`, `MedicationDose`,
and `GuidelineDocument` carries a `qualifications_required` list.

### Phase 5: Chunker and ChromaDB ingestion

This is the critical stage that connects the pipeline output to the quiz system.

**Collection naming:** Use service-scoped collection names:

```python
# In your adapter's chunker.py
collection_name = f"guidelines_{service_id}"  # e.g. "guidelines_at"
```

This matches the naming convention in `src/python/quiz/retriever.py`:

```python
self._cmgs = self._client.get_or_create_collection(f"guidelines_{service_id}")
self._notes = self._client.get_or_create_collection(f"personal_{service_id}")
```

**Chunk metadata** must include:

```python
metadata = {
    "source_type": "cmg",
    "source_file": os.path.basename(file_path),
    "section": category,
    "visibility": "both" | "ap" | "icp",  # or service-specific equivalents
    "chunk_type": "general" | "dosage" | "safety" | "protocol" | "reference" | "assessment",
    "last_modified": timestamp,
    # Optional:
    "cmg_number": cmg_number,
    "qualifications_required": [...],
}
```

**Output path:** Structured JSON files go to the service-scoped data directory,
resolved via `src/python/paths.py`:

```python
from paths import resolve_service_structured_dir
structured_dir = resolve_service_structured_dir(service_id)
# Returns APP_ROOT/data/services/<id>/structured or USER_DATA_DIR/services/<id>/structured
```

**Path helpers available in `paths.py`:**

| Function | Returns |
|----------|---------|
| `service_structured_dir(service_id)` | `APP_ROOT/data/services/{id}/structured` |
| `user_service_structured_dir(service_id)` | `USER_DATA_DIR/services/{id}/structured` |
| `resolve_service_structured_dir(service_id)` | User dir if it has data, else bundled dir |
| `service_uploads_dir(service_id)` | `USER_DATA_DIR/services/{id}/uploads` |
| `service_medications_dir(service_id)` | `USER_DATA_DIR/services/{id}/medications` |
| `bundled_service_structured_dir(service_id)` | Alias for `service_structured_dir` |

**Never use bare relative paths** like `Path("data/...")`. Always import from
`src/python/paths.py`.

---

## Step 6: Update Packaging

### electron-builder.yml

Add the new service's structured data to `extraResources`:

```yaml
extraResources:
  # ... existing entries ...
  - from: data/services/<id>/structured
    to: data/services/<id>/structured
    filter:
      - "**/*.json"
```

If the service has pre-built ChromaDB data, also add:

```yaml
  - from: build/resources/data/services/<id>/chroma_db
    to: data/services/<id>/chroma_db
    filter:
      - "**/*"
```

### Build scripts

Update `scripts/package-backend.sh` (macOS) and `scripts/package-backend.ps1` (Windows)
to include the new service's data in the staging area.

If the service requires platform-specific handling (like the sequential macOS arm64/x64
build constraint for ACTAS), document it in `Guides/standalone-packaging-macos-windows.md`.

### Artifact naming

Update `electron-builder.yml` `artifactName` if the default build should reflect the
new service. Currently:

```yaml
artifactName: "StudyBot - CMGs-${version}-${arch}.${ext}"
```

For a multi-service build, consider a generic name:

```yaml
artifactName: "StudyBot-${version}-${arch}.${ext}"
```

---

## Step 7: Add Service-Specific Tests

### Qualification tests

Test the qualification math for the new service in `tests/python/`:

```python
from src.python.services.qualifications import effective_qualifications, is_in_scope
from src.python.services.registry import get_service

def test_<id>_base_qualifications():
    svc = get_service("<id>")
    q = effective_qualifications("<base_id>", (), svc)
    assert "<base_id>" in q

def test_<id>_endorsement_requires_base():
    svc = get_service("<id>")
    # Should raise ValueError if endorsement requires a different base
    ...

def test_<id>_scope_filtering():
    ap_scope = effective_qualifications("<base_id>", (), svc)
    icp_scope = effective_qualifications("<icp_base>", (), svc)
    assert is_in_scope(frozenset({"<base_id>"}), ap_scope)
    assert is_in_scope(frozenset({"<icp_id>"}), icp_scope)
```

### Adapter contract tests

Verify that the adapter module is importable and exposes `run_pipeline()`:

```python
def test_adapter_importable():
    import importlib
    mod = importlib.import_module("src.python.pipeline.<id>")
    assert callable(mod.run_pipeline)
```

### Golden flowchart tests

If the service has flowcharts, store a few known-good Mermaid.js outputs as golden
files and test that the extraction pipeline reproduces them:

```python
def test_flowchart_extraction_matches_golden():
    # Compare extracted Mermaid against committed golden file
    ...
```

---

## Step 8: User Sign-Off Checklist

Before marking the service integration as complete, verify the following with the user:

### Scope-of-practice accuracy

- [ ] Every qualification level is listed with correct scope
- [ ] Medication formulary lists are accurate per qualification
- [ ] ICP/extended-scope restrictions match the actual CPG content
- [ ] No phantom medications or procedures are listed

### Clinical content integrity

- [ ] Sample quiz questions generated from the new service's data are clinically accurate
- [ ] Source citations reference the correct guideline (e.g. `Ref: AT CPG 14.1`)
- [ ] Feedback responses quote actual source text, not fabricated content
- [ ] Flowchart conversions are clinically accurate (check golden flowcharts manually)

### Qualification filtering correctness

- [ ] Content tagged as base-level is visible to all users of that service
- [ ] Content tagged as endorsement-only is hidden from users without that endorsement
- [ ] The `implies` chain works correctly (e.g. ICP sees AP content)
- [ ] Cross-service isolation: ACTAS content does not appear in AT quizzes and vice versa

### Retrieval and quiz behaviour

- [ ] `Retriever` with `service_id="<id>"` queries only the correct collections
- [ ] `effective_qualifications` parameter correctly filters content by visibility
- [ ] Random chunk retrieval works (`get_random_chunk()` returns service-scoped results)
- [ ] Source ranking respects `source_hierarchy` if the service overrides defaults

### Packaging

- [ ] Structured data is included in the packaged app via `electron-builder.yml`
- [ ] `seed.py` correctly copies bundled data on first launch
- [ ] Settings page allows selecting the new service as `active_service`

---

## Quick Reference: Files to Create or Modify

| Action | File | Purpose |
|--------|------|---------|
| Create | `Guides/scope-of-practice-<id>.md` | Qualification scope document |
| Create | `src/python/pipeline/<id>/` | Adapter pipeline directory |
| Create | `src/python/pipeline/<id>/__init__.py` | Exports `run_pipeline` |
| Create | `src/python/pipeline/<id>/orchestrator.py` | Stage chaining |
| Create | `src/python/pipeline/<id>/discover.py` | Phase 0 Playwright probe |
| Create | `Guides/<id>-extraction-findings.md` | Phase 0 results |
| Create | `tests/python/test_<id>_qualifications.py` | Qualification math tests |
| Modify | `src/python/services/registry.py` | Add `Service(...)` to `REGISTRY` |
| Modify | `electron-builder.yml` | Bundle new service data |
| Modify | `scripts/package-backend.sh` | Stage new service data |
| Modify | `scripts/package-backend.ps1` | Stage new service data (Windows) |

---

## Common Patterns and Pitfalls

### Collection naming is strict

The retriever in `src/python/quiz/retriever.py` constructs collection names as
`guidelines_{service_id}` and `personal_{service_id}`. The chunker in the adapter
must use the exact same naming convention. Mismatched names mean content silently
disappears from quizzes.

### Qualification IDs must be unique within a service

The `Base.id` and `Endorsement.id` values in a service's `QualificationModel` must be
unique. The `effective_qualifications()` function in `src/python/services/qualifications.py`
returns a `frozenset[str]` — duplicate IDs would collapse into one entry and break
filtering.

### The `implies` field is transitive

If you define `Base("C", ..., implies=("B",))` and `Base("B", ..., implies=("A",))`,
then holding qualification C grants A, B, and C. The closure is computed by
`_closure()` in `qualifications.py`. Plan the implication chain carefully.

### ChromaDB visibility metadata must use recognised values

The retriever's `_build_where()` method filters on the `visibility` field. Valid values
are `"both"`, `"ap"`, and `"icp"` for ACTAS. For a new service with different
qualification names, update the retriever's visibility logic or use the
`qualifications_required` field on chunks for filtering instead.

### All paths go through `paths.py`

Never use `Path("data/cmgs/structured")` or any bare relative path. Always use
`resolve_service_structured_dir(service_id)` or the other helpers from
`src/python/paths.py`. This ensures the app works correctly in both development and
packaged modes.

### The active service is determined at runtime

`src/python/services/active.py` reads `config/settings.json` for the `active_service`
key and falls back to the first entry in `REGISTRY`. The retriever uses this to
determine which ChromaDB collections to query. Users switch services via the Settings
page.

---

*Last updated: 2026-04-19. Update this guide when the service registry schema or
pipeline contract changes.*
