# Multi-Ambulance-Service Foundation — Implementation Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-ambulance-service support to the Clinical Recall Assistant: service registry, per-service qualification model, collection-per-service ChromaDB isolation, settings/first-run UX, ACTAS module rename and qualifications backfill, and a committed Ambulance Tasmania Phase 0 extraction findings doc. Tas content ingestion is a later plan.

**Architecture:** Introduce a `Service` registry as the single source of truth. Rename `src/python/pipeline/cmg/` to `pipeline/actas/`. Split the current two ChromaDB collections (`cmg_guidelines`, `paramedic_notes`) into per-service collections (`guidelines_<id>`, `personal_<id>`). Migrate the hard-coded `skill_level` filter to a qualification-set filter driven by `qualifications_required` chunk metadata. Add a blocking first-run Settings modal, a service chip across pages, and a per-doc service/scope retag UI. Gather and commit live-network Tas Phase 0 findings via Playwright before any Tas extraction code exists.

**Tech Stack:** Python 3.12, FastAPI, ChromaDB, pydantic, pytest, httpx; TypeScript 5, React 19, Tailwind, React Router 7, Vitest, Testing Library; Playwright (for Phase 0 discovery only).

**Spec:** `docs/superpowers/specs/2026-04-19-multi-service-support-design.md`

---

## File structure

### Created

**Backend:**
- `src/python/services/__init__.py`
- `src/python/services/registry.py` — `Service`, `QualificationModel`, `Base`, `Endorsement`, `SOURCE_HIERARCHY_DEFAULTS`, `REGISTRY`
- `src/python/services/schema.py` — `GuidelineDocument`, `ContentSection`, `MedicationDose`, `Flowchart`, `Reference`
- `src/python/services/qualifications.py` — `effective_qualifications(base, endorsements, service)` and `is_in_scope(required, effective)` pure functions
- `src/python/services/router.py` — `GET /services`
- `src/python/services/active.py` — `active_service()` helper reading `config/settings.json`
- `scripts/migrate_to_multi_service.py` — one-shot migration
- `scripts/backfill_actas_qualifications.py` — §15.7 backfill
- `src/python/llm/vision.py` — placeholder module with `VisionNotSupportedError` + `describe_flowchart` stub raising `NotImplementedError` (real impl in Plan B)
- `src/renderer/components/ServiceChip.tsx`
- `src/renderer/components/ServiceSetupModal.tsx`
- `src/renderer/providers/ServiceProvider.tsx` — registry fetch + active service context
- `src/renderer/hooks/useService.ts`
- `Guides/scope-of-practice-actas.md`
- `Guides/scope-of-practice-at.md`
- `Guides/categories-actas.md`
- `Guides/actas-qualifications-backfill.md`
- `Guides/at-cpg-extraction-findings.md` (Tas Phase 0 deliverable)
- `Guides/adding-a-service.md`
- `tests/python/services/test_registry.py`
- `tests/python/services/test_qualifications.py`
- `tests/python/services/test_schema.py`
- `tests/python/services/test_router.py`
- `tests/python/services/test_isolation.py` — cross-service retrieval isolation
- `tests/python/migration/test_migrate_to_multi_service.py`
- `tests/python/migration/test_backfill_actas_qualifications.py`
- `tests/python/fixtures/services/actas/` (3 trimmed guideline JSONs)
- `tests/renderer/ServiceSetupModal.test.tsx`
- `tests/renderer/ServiceChip.test.tsx`
- `tests/renderer/useService.test.tsx`

### Renamed (git mv)

- `src/python/pipeline/cmg/` → `src/python/pipeline/actas/` (entire directory)

### Modified

**Backend:**
- `src/python/paths.py` — replace CMG-specific constants with `service_structured_dir()` / `user_service_structured_dir()` / `resolve_service_structured_dir(service_id)` / `service_uploads_dir()` / `user_service_uploads_dir()`
- `src/python/main.py` — register services router; include in CORS/lifespan
- `src/python/seed.py` — iterate registry; seed per-service bundled Chroma trees
- `src/python/guidelines/router.py` — read from active service's structured dir; emit both `guideline_id` and legacy `cmg_number`
- `src/python/medication/router.py` — read from `data/services/<active>/medications/`; service-scoped
- `src/python/sources/router.py` — service-aware source status
- `src/python/settings/router.py` — expose/update `active_service`, `base_qualification`, `endorsements`; re-run pipeline routes per service
- `src/python/upload/router.py` — accept `service` + `scope`; write into `data/services/<service>/uploads/`; ingest into `personal_<service>`
- `src/python/quiz/router.py` — remove `skill_level`; pass effective qualifications
- `src/python/quiz/agent.py` — service-neutral prompt; remove hard-coded AP/ICP text
- `src/python/quiz/retriever.py` — query `guidelines_<active>` + `personal_<active>`; filter by qualification-set membership
- `src/python/quiz/models.py` — add `service`, `guideline_id`; keep `cmg_number` through deprecation window
- `src/python/quiz/store.py` — add `service` column to questions/sessions/mastery/history; filter every query
- `src/python/llm/factory.py` — remove `skill_level: "AP"` default
- `src/python/pipeline/actas/chunker.py` — write into `guidelines_actas` + `personal_actas`; tag chunks with `service="actas"` and `qualifications_required`
- `src/python/pipeline/actas/orchestrator.py` — service-aware paths
- `src/python/pipeline/actas/refresh.py` — service-aware paths
- `src/python/pipeline/actas/web_structurer.py` — service-aware paths
- `src/python/pipeline/personal_docs/` — read front-matter `service`/`scope`; ingest into `personal_<service>`

**Frontend:**
- `src/renderer/App.tsx` — wrap with `ServiceProvider`; show `ServiceSetupModal` if unconfigured
- `src/renderer/components/Sidebar.tsx` — render `ServiceChip`
- `src/renderer/providers/SettingsProvider.tsx` — expose `activeService`, `baseQualification`, `endorsements`
- `src/renderer/providers/ResourceCacheProvider.tsx` — namespace keys by active service
- `src/renderer/pages/Settings.tsx` — Active Service + Qualifications sections + per-doc service/scope retag UI
- `src/renderer/pages/Dashboard.tsx` — empty-state copy when switching services
- `src/renderer/pages/Quiz.tsx`, `Feedback.tsx`, `Library.tsx`, `Medication.tsx`, `Guidelines.tsx` — service chip in header
- `src/renderer/types/api.ts` — add `Service`, `QualificationModel`; add `guideline_id` (prefer over `cmg_number`)
- `src/renderer/components/UploadDialog.tsx` — service + scope dropdowns

**Packaging / data:**
- `electron-builder.yml` — per-service bundled resources
- `electron-builder.personal.yml` — per-service download manifest
- `scripts/upload-personal-data.sh` — enumerate `personal_<id>`
- `scripts/package-backend.sh`, `scripts/package-backend.ps1` — new bundled layout

### Data migrations (produced by scripts, committed)

- `data/services/actas/structured/*.json` (moved + `service` + `guideline_id` + `qualifications_required` added)
- `data/services/actas/medications/*.json` (denormalised medication index)
- `data/personal_docs/structured/*.md` (front-matter gains `service: actas`, `scope: service-specific`)

---

## Implementation order & task index

The plan has **24 tasks** grouped into five phases. Each task leaves `main` in a working, tested state. Tasks within a phase can be done in order; phases must be completed sequentially because later phases depend on earlier invariants.

- **Phase 1 — Foundation without behaviour change** (Tasks 1–6): service registry, schema, qualifications math, routers/exposure; no data moved yet.
- **Phase 2a — Module rename + data layout** (Tasks 7–9): `pipeline/cmg/` → `pipeline/actas/`, `paths.py` helpers, upload router service-awareness.
- **Phase 2b — ACTAS data migration + qualifications backfill** (Tasks 10–13): structured-file migration, qualifications backfill script, medication denormalisation, front-matter tagging.
- **Phase 2c — ChromaDB split + retriever rewrite** (Tasks 14–17): collection-per-service, SQLite service column, retriever + factory + quiz prompt migration, isolation test.
- **Phase 3 — Frontend UX** (Tasks 18–21): ServiceProvider, setup modal, settings page changes, service chip + empty state.
- **Phase 4 — Tas Phase 0 & packaging updates** (Tasks 22–24): Playwright discovery + findings doc, per-service bundled Chroma build, adding-a-service guide.

---

## Phase 1 — Foundation without behaviour change

### Task 1: Service registry + qualification dataclasses

**Files:**
- Create: `src/python/services/__init__.py`
- Create: `src/python/services/registry.py`
- Test: `tests/python/services/test_registry.py`

- [ ] **Step 1: Write failing test for registry lookup**

```python
# tests/python/services/test_registry.py
from src.python.services.registry import REGISTRY, get_service

def test_actas_registered():
    svc = get_service("actas")
    assert svc.id == "actas"
    assert svc.display_name.startswith("ACT")
    assert any(b.id == "AP" for b in svc.qualifications.bases)
    assert any(b.id == "ICP" for b in svc.qualifications.bases)

def test_at_registered():
    svc = get_service("at")
    assert svc.id == "at"
    assert any(b.id == "PARAMEDIC" for b in svc.qualifications.bases)
    assert any(b.id == "VAO" for b in svc.qualifications.bases)
    endorsement_ids = {e.id for e in svc.qualifications.endorsements}
    assert {"ICP", "PACER", "CP_ECP"} <= endorsement_ids

def test_unknown_service_raises():
    import pytest
    with pytest.raises(KeyError):
        get_service("nswa")
```

- [ ] **Step 2: Run test, expect ImportError/fail**

```bash
pytest tests/python/services/test_registry.py -v
```

- [ ] **Step 3: Implement `registry.py`**

```python
# src/python/services/registry.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Base:
    id: str
    display: str
    implies: tuple[str, ...] = ()

@dataclass(frozen=True)
class Endorsement:
    id: str
    display: str
    requires_base: tuple[str, ...] = ()

@dataclass(frozen=True)
class QualificationModel:
    bases: tuple[Base, ...]
    endorsements: tuple[Endorsement, ...] = ()

SOURCE_HIERARCHY_DEFAULTS: tuple[tuple[str, float], ...] = (
    ("guideline", 1.00),
    ("ref_doc",   0.80),
    ("cpd_doc",   0.60),
    ("notability",0.40),
    ("upload",    0.30),
)

@dataclass(frozen=True)
class Service:
    id: str
    display_name: str
    region: str
    accent_colour: str
    source_url: str
    scope_source_doc: str
    qualifications: QualificationModel
    adapter: str
    category_mapping_doc: str
    source_hierarchy: tuple[tuple[str, float], ...] = SOURCE_HIERARCHY_DEFAULTS

REGISTRY: tuple[Service, ...] = (
    Service(
        id="actas",
        display_name="ACT Ambulance Service",
        region="Australian Capital Territory",
        accent_colour="#2D5A54",
        source_url="https://cmg.ambulance.act.gov.au",
        scope_source_doc="Guides/scope-of-practice-actas.md",
        qualifications=QualificationModel(
            bases=(
                Base("AP", "Ambulance Paramedic"),
                Base("ICP", "Intensive Care Paramedic", implies=("AP",)),
            ),
        ),
        adapter="src.python.pipeline.actas",
        category_mapping_doc="Guides/categories-actas.md",
    ),
    Service(
        id="at",
        display_name="Ambulance Tasmania",
        region="Tasmania",
        accent_colour="#005a96",
        source_url="https://cpg.ambulance.tas.gov.au",
        scope_source_doc="Guides/scope-of-practice-at.md",
        qualifications=QualificationModel(
            bases=(
                Base("VAO", "Volunteer Ambulance Officer"),
                Base("PARAMEDIC", "Paramedic"),
            ),
            endorsements=(
                Endorsement("ICP", "Intensive Care Paramedic", requires_base=("PARAMEDIC",)),
                Endorsement("PACER", "PACER", requires_base=("PARAMEDIC",)),
                Endorsement("CP_ECP", "Community Paramedic / Extended Care Paramedic",
                            requires_base=("PARAMEDIC",)),
            ),
        ),
        adapter="src.python.pipeline.at",
        category_mapping_doc="Guides/categories-at.md",
    ),
)

_BY_ID = {s.id: s for s in REGISTRY}

def get_service(service_id: str) -> Service:
    return _BY_ID[service_id]

def all_service_ids() -> tuple[str, ...]:
    return tuple(s.id for s in REGISTRY)
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/python/services/test_registry.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/python/services/ tests/python/services/test_registry.py
git commit -m "feat(services): add service registry with ACTAS and AT entries"
```

---

### Task 2: Qualification-set math

**Files:**
- Create: `src/python/services/qualifications.py`
- Test: `tests/python/services/test_qualifications.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/services/test_qualifications.py
from src.python.services.registry import get_service
from src.python.services.qualifications import effective_qualifications, is_in_scope

ACTAS = get_service("actas")
AT = get_service("at")

def test_actas_ap_does_not_include_icp():
    eff = effective_qualifications("AP", (), ACTAS)
    assert eff == frozenset({"AP"})

def test_actas_icp_implies_ap():
    eff = effective_qualifications("ICP", (), ACTAS)
    assert eff == frozenset({"AP", "ICP"})

def test_at_paramedic_plus_icp_endorsement():
    eff = effective_qualifications("PARAMEDIC", ("ICP",), AT)
    assert eff == frozenset({"PARAMEDIC", "ICP"})

def test_at_vao_does_not_roll_up():
    eff = effective_qualifications("VAO", (), AT)
    assert eff == frozenset({"VAO"})

def test_empty_required_always_in_scope():
    assert is_in_scope(frozenset(), frozenset({"AP"}))

def test_required_subset_of_effective_is_in_scope():
    assert is_in_scope(frozenset({"AP"}), frozenset({"AP", "ICP"}))

def test_required_not_subset_is_out_of_scope():
    assert not is_in_scope(frozenset({"ICP"}), frozenset({"AP"}))

def test_endorsement_requires_valid_base():
    import pytest
    with pytest.raises(ValueError):
        effective_qualifications("VAO", ("ICP",), AT)  # ICP endorsement requires PARAMEDIC
```

- [ ] **Step 2: Run, expect fail.**

```bash
pytest tests/python/services/test_qualifications.py -v
```

- [ ] **Step 3: Implement**

```python
# src/python/services/qualifications.py
from src.python.services.registry import Service

def _closure(base_id: str, service: Service) -> frozenset[str]:
    seen = {base_id}
    stack = [base_id]
    bases_by_id = {b.id: b for b in service.qualifications.bases}
    while stack:
        cur = stack.pop()
        for implied in bases_by_id[cur].implies:
            if implied not in seen:
                seen.add(implied)
                stack.append(implied)
    return frozenset(seen)

def effective_qualifications(
    base_id: str,
    endorsement_ids: tuple[str, ...],
    service: Service,
) -> frozenset[str]:
    bases_by_id = {b.id: b for b in service.qualifications.bases}
    endorsements_by_id = {e.id: e for e in service.qualifications.endorsements}
    if base_id not in bases_by_id:
        raise ValueError(f"Unknown base {base_id} for service {service.id}")
    for eid in endorsement_ids:
        if eid not in endorsements_by_id:
            raise ValueError(f"Unknown endorsement {eid} for service {service.id}")
        endorsement = endorsements_by_id[eid]
        if endorsement.requires_base and base_id not in endorsement.requires_base:
            raise ValueError(
                f"Endorsement {eid} requires base one of {endorsement.requires_base}, got {base_id}"
            )
    return _closure(base_id, service) | frozenset(endorsement_ids)

def is_in_scope(required: frozenset[str], effective: frozenset[str]) -> bool:
    return required.issubset(effective)
```

- [ ] **Step 4: Run, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/python/services/qualifications.py tests/python/services/test_qualifications.py
git commit -m "feat(services): add qualification-set math (effective + in_scope)"
```

---

### Task 3: `GuidelineDocument` pydantic schema

**Files:**
- Create: `src/python/services/schema.py`
- Test: `tests/python/services/test_schema.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/services/test_schema.py
import pytest
from src.python.services.schema import GuidelineDocument

def test_minimal_valid_document():
    doc = GuidelineDocument(
        service="actas",
        guideline_id="CMG_14",
        title="Anaphylaxis",
        categories=["Clinical Guidelines"],
        qualifications_required=["AP"],
        content_sections=[],
        medications=[],
        flowcharts=[],
        references=[],
        source_hash="abc",
        extra={},
    )
    assert doc.service == "actas"

def test_rejects_unknown_top_level_field():
    with pytest.raises(Exception):
        GuidelineDocument(
            service="actas", guideline_id="X", title="T",
            categories=[], qualifications_required=[],
            content_sections=[], medications=[], flowcharts=[],
            references=[], source_hash="x", extra={},
            bogus_field=1,
        )
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement**

```python
# src/python/services/schema.py
from datetime import date
from pydantic import BaseModel, ConfigDict

class ContentSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading: str
    body: str
    qualifications_required: list[str] = []

class MedicationDose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medication: str
    indication: str
    dose: str
    route: str | None = None
    qualifications_required: list[str] = []

class Flowchart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    mermaid: str
    source_format: str  # "data" | "svg" | "image" | "pdf"
    review_required: bool = False
    asset_ref: str | None = None

class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    url: str | None = None

class GuidelineDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: str
    guideline_id: str
    title: str
    categories: list[str]
    qualifications_required: list[str]
    content_sections: list[ContentSection]
    medications: list[MedicationDose]
    flowcharts: list[Flowchart]
    references: list[Reference]
    source_url: str | None = None
    source_hash: str
    last_modified: date | None = None
    extra: dict = {}
```

- [ ] **Step 4: Run, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/python/services/schema.py tests/python/services/test_schema.py
git commit -m "feat(services): add GuidelineDocument pydantic schema"
```

---

### Task 4: `GET /services` endpoint

**Files:**
- Create: `src/python/services/router.py`
- Modify: `src/python/main.py` (register the router)
- Test: `tests/python/services/test_router.py`

- [ ] **Step 1: Write failing test**

```python
# tests/python/services/test_router.py
from fastapi.testclient import TestClient
from src.python.main import app

client = TestClient(app)

def test_list_services_includes_both():
    r = client.get("/services")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert ids == {"actas", "at"}

def test_list_services_strips_adapter_path():
    r = client.get("/services")
    for s in r.json():
        assert "adapter" not in s
```

- [ ] **Step 2: Run, expect 404.**

- [ ] **Step 3: Implement router**

```python
# src/python/services/router.py
from fastapi import APIRouter
from src.python.services.registry import REGISTRY

router = APIRouter()

@router.get("/services")
def list_services():
    out = []
    for s in REGISTRY:
        out.append({
            "id": s.id,
            "display_name": s.display_name,
            "region": s.region,
            "accent_colour": s.accent_colour,
            "source_url": s.source_url,
            "qualifications": {
                "bases": [{"id": b.id, "display": b.display, "implies": list(b.implies)}
                          for b in s.qualifications.bases],
                "endorsements": [{"id": e.id, "display": e.display,
                                  "requires_base": list(e.requires_base)}
                                 for e in s.qualifications.endorsements],
            },
        })
    return out
```

- [ ] **Step 4: Register in `src/python/main.py`**

Add:

```python
from src.python.services.router import router as services_router
app.include_router(services_router)
```

- [ ] **Step 5: Run, expect pass.**

- [ ] **Step 6: Commit**

```bash
git add src/python/services/router.py src/python/main.py tests/python/services/test_router.py
git commit -m "feat(services): expose GET /services for frontend"
```

---

### Task 5: `active_service()` helper

**Files:**
- Create: `src/python/services/active.py`
- Test: `tests/python/services/test_active.py`

Reads `active_service` from `config/settings.json`, falling back to `settings.example.json`, then to the first registered service if unset. Used everywhere the backend needs to know the current service.

- [ ] **Step 1: Write failing test**

```python
# tests/python/services/test_active.py
import json, tempfile, pathlib
from src.python.services.active import active_service_from_path

def test_reads_active_service_from_config(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"active_service": "at"}))
    assert active_service_from_path(cfg).id == "at"

def test_missing_falls_back_to_first(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text("{}")
    assert active_service_from_path(cfg).id == "actas"

def test_unknown_service_raises(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"active_service": "bogus"}))
    import pytest
    with pytest.raises(KeyError):
        active_service_from_path(cfg)
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement**

```python
# src/python/services/active.py
import json
from pathlib import Path
from src.python.services.registry import get_service, REGISTRY, Service

def active_service_from_path(path: Path) -> Service:
    data = json.loads(path.read_text()) if path.exists() else {}
    svc_id = data.get("active_service")
    if not svc_id:
        return REGISTRY[0]
    return get_service(svc_id)

def active_service() -> Service:
    from src.python.paths import SETTINGS_PATH
    return active_service_from_path(SETTINGS_PATH)
```

- [ ] **Step 4: Run, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/python/services/active.py tests/python/services/test_active.py
git commit -m "feat(services): add active_service() helper reading settings.json"
```

---

### Task 6: Authoring `Guides/scope-of-practice-actas.md` and `Guides/scope-of-practice-at.md`

**Files:**
- Create: `Guides/scope-of-practice-actas.md`
- Create: `Guides/scope-of-practice-at.md`

These are referenced by `scope_source_doc` in the registry. They must cite authoritative sources and list every qualification in the registry entry with its scope summary.

- [ ] **Step 1: Draft ACTAS scope doc** listing AP and ICP scopes, citing ACTAS CMGs and ACTAS scope-of-practice source.
- [ ] **Step 2: Draft AT scope doc** listing VAO, Paramedic, ICP, PACER, CP/ECP, citing AT scope-of-practice matrix URL (`https://intranet.health.tas.gov.au/resources/scope-practice-matrix` — public alternate TBD during review).
- [ ] **Step 3: Get user review/sign-off** before committing. (Ask user in-session; do not proceed without acknowledgement.)
- [ ] **Step 4: Commit**

```bash
git add Guides/scope-of-practice-actas.md Guides/scope-of-practice-at.md
git commit -m "docs: add scope-of-practice source docs for ACTAS and AT"
```

---

## Phase 2a — Module rename + data layout

### Task 7: Rename `pipeline/cmg/` → `pipeline/actas/`

**Files:**
- Rename: `src/python/pipeline/cmg/` → `src/python/pipeline/actas/`
- Modify: every importer of `src.python.pipeline.cmg.*`

- [ ] **Step 1: Check tests currently pass on main**

```bash
pytest tests/python/ -x -q
```

- [ ] **Step 2: Do the rename**

```bash
git mv src/python/pipeline/cmg src/python/pipeline/actas
```

- [ ] **Step 3: Update every import.** Grep first:

```bash
rg -l "pipeline\.cmg|pipeline/cmg"
```

Rewrite each hit from `src.python.pipeline.cmg` → `src.python.pipeline.actas`.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/python/ -x -q
```

Expected: same pass/fail profile as before rename (KNOWN_TEST_FAILURES remains as-is).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename pipeline/cmg/ to pipeline/actas/"
```

---

### Task 8: Refactor `paths.py` to service-aware helpers

**Files:**
- Modify: `src/python/paths.py`
- Modify: every caller listed in spec §16.1
- Test: `tests/python/test_paths.py`

- [ ] **Step 1: Write failing tests for new helpers**

```python
# tests/python/test_paths.py
from src.python.paths import (
    service_structured_dir, user_service_structured_dir,
    resolve_service_structured_dir, service_uploads_dir,
)

def test_service_structured_dir_shape():
    p = service_structured_dir("actas")
    assert p.name == "structured"
    assert p.parent.name == "actas"

def test_resolve_prefers_user_dir(tmp_path, monkeypatch):
    user_dir = tmp_path / "user" / "services" / "actas" / "structured"
    user_dir.mkdir(parents=True)
    (user_dir / "x.json").write_text("{}")
    monkeypatch.setattr("src.python.paths.USER_DATA_ROOT", tmp_path / "user")
    out = resolve_service_structured_dir("actas")
    assert out == user_dir
```

- [ ] **Step 2: Run, expect ImportError.**

- [ ] **Step 3: Implement new helpers in `paths.py`**

Add:

```python
def service_structured_dir(service_id: str) -> Path:
    return APP_ROOT / "data" / "services" / service_id / "structured"

def user_service_structured_dir(service_id: str) -> Path:
    return USER_DATA_ROOT / "services" / service_id / "structured"

def resolve_service_structured_dir(service_id: str) -> Path:
    user = user_service_structured_dir(service_id)
    if user.exists() and any(user.glob("*.json")):
        return user
    return service_structured_dir(service_id)

def service_uploads_dir(service_id: str) -> Path:
    return USER_DATA_ROOT / "services" / service_id / "uploads"

def user_service_uploads_dir(service_id: str) -> Path:
    return service_uploads_dir(service_id)

def service_medications_dir(service_id: str) -> Path:
    return USER_DATA_ROOT / "services" / service_id / "medications"

def bundled_service_structured_dir(service_id: str) -> Path:
    return APP_ROOT / "data" / "services" / service_id / "structured"
```

Remove (or deprecate by raising) `CMG_STRUCTURED_DIR`, `USER_CMG_STRUCTURED_DIR`, `resolve_cmg_structured_dir`.

- [ ] **Step 4: Rewrite every caller (§16.1 list + `quiz/retriever.py` + `llm/factory.py`).** Completeness check:

```bash
rg "CMG_STRUCTURED_DIR|USER_CMG_STRUCTURED_DIR|resolve_cmg_structured_dir" src/ tests/
```

Expect zero hits outside `paths.py` (where the symbols are removed).

- [ ] **Step 5: Run backend tests**

```bash
pytest tests/python/ -x -q
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(paths): introduce service-aware structured-dir helpers"
```

---

### Task 9: Upload router service-awareness

**Files:**
- Modify: `src/python/upload/router.py`
- Modify: `src/python/upload/extractor.py`
- Test: update `tests/python/upload/test_router.py` (or create)

- [ ] **Step 1: Write failing test that `POST /upload` accepts `service` + `scope`**

```python
def test_upload_accepts_service_and_scope(client, tmp_path, monkeypatch):
    # existing fixture: in-memory chroma, temp user data root
    r = client.post(
        "/upload",
        data={"service": "actas", "scope": "general"},
        files={"file": ("test.md", b"# Hi\n", "text/markdown")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "actas"
    assert body["scope"] == "general"
    # file landed in data/services/actas/uploads/
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement**

Change router signature: read `service: str = Form(...)`, `scope: Literal["service-specific","general"] = Form("service-specific")`. Write to `service_uploads_dir(service)`. Tag chunks with `service` + `scope`. Default `source_type` stays `"upload"` (correcting the current `"cpd_doc"` hard-code).

- [ ] **Step 4: Run, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/python/upload/ tests/python/upload/
git commit -m "feat(upload): accept service and scope, write into per-service dirs"
```

---

## Phase 2b — Data migration + qualifications backfill

### Task 10: Migration script `migrate_to_multi_service.py`

**Files:**
- Create: `scripts/migrate_to_multi_service.py`
- Test: `tests/python/migration/test_migrate_to_multi_service.py`

The script:
1. Moves `data/cmgs/structured/*.json` → `data/services/actas/structured/*.json`. Adds `service: "actas"` and `guideline_id: "CMG_<n>"` (preserving `cmg_number` in `extra`).
2. Moves `data/uploads/` contents → `data/services/actas/uploads/`.
3. Adds `service: actas`, `scope: service-specific` front-matter to every file in `data/personal_docs/structured/`.
4. Writes default `active_service: "actas"` to `config/settings.json` if unset.
5. Idempotent — rerun is a no-op.

- [ ] **Step 1: Write failing test operating on a fixture tree** (snapshot of small sample of current `data/cmgs/structured/`).

```python
def test_migration_moves_cmg_files(tmp_repo):
    # tmp_repo has data/cmgs/structured/CMG_14_Anaphylaxis.json
    run_migration(repo_root=tmp_repo)
    assert (tmp_repo / "data/services/actas/structured/CMG_14_Anaphylaxis.json").exists()
    assert not (tmp_repo / "data/cmgs/structured/CMG_14_Anaphylaxis.json").exists()

def test_migration_adds_service_field(tmp_repo):
    run_migration(repo_root=tmp_repo)
    doc = json.loads((tmp_repo / "data/services/actas/structured/CMG_14_Anaphylaxis.json").read_text())
    assert doc["service"] == "actas"
    assert doc["guideline_id"].startswith("CMG_")

def test_migration_is_idempotent(tmp_repo):
    run_migration(repo_root=tmp_repo)
    run_migration(repo_root=tmp_repo)  # must not raise
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement the script** with a `run_migration(repo_root: Path)` entry point + `if __name__ == "__main__":` wrapper.

- [ ] **Step 4: Run tests, expect pass.**

- [ ] **Step 5: Commit (script only — do NOT run against real data yet)**

```bash
git add scripts/migrate_to_multi_service.py tests/python/migration/
git commit -m "feat(migration): one-shot migrate_to_multi_service script"
```

---

### Task 11: ACTAS qualifications backfill + review doc

**Files:**
- Create: `scripts/backfill_actas_qualifications.py`
- Create: `Guides/actas-qualifications-backfill.md`
- Test: `tests/python/migration/test_backfill_actas_qualifications.py`

Adds `qualifications_required` to every section in every `data/services/actas/structured/*.json` based on current `quiz/agent.py` ICP markers + medicine-level scope (ICP-only medicines → section marked ICP).

- [ ] **Step 1: Write failing test using a fixture with one AP-tagged and one ICP-tagged section.**
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement.** Inputs: structured JSON files, ICP marker list extracted from current `agent.py`. Output: mutated JSON files with `qualifications_required` on each section + each `MedicationDose`.
- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Draft review doc** — `Guides/actas-qualifications-backfill.md` lists every ICP-tagged section with source evidence and a "confirmed / needs review" column for the user.
- [ ] **Step 6: Run backfill against real `data/services/actas/structured/`**; commit the resulting structured JSON changes as a separate commit.
- [ ] **Step 7: Commit**

```bash
git add scripts/backfill_actas_qualifications.py tests/python/migration/test_backfill_actas_qualifications.py Guides/actas-qualifications-backfill.md
git commit -m "feat(migration): ACTAS qualifications_required backfill"
# then:
git add data/services/actas/structured/
git commit -m "data: apply ACTAS qualifications_required backfill"
```

---

### Task 12: Medication denormalisation index

**Files:**
- Modify: `src/python/pipeline/actas/chunker.py` or new `src/python/pipeline/actas/medications_index.py`
- Create: `data/services/actas/medications/*.json` (generated)
- Test: `tests/python/pipeline/test_medications_index.py`

Produces one JSON per medication aggregating all doses across all ACTAS guidelines, so the medication router has a single source to read from.

- [ ] **Step 1: Write failing test** that running the index builder on a fixture set produces per-medication files matching the `MedicationDose` schema + `service`, `guideline_id`, `source_file`.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement** the index builder as a function callable during `run_pipeline()`.
- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Regenerate index against real data; commit generated files.**
- [ ] **Step 6: Commit**

```bash
git add src/python/pipeline/actas/medications_index.py tests/python/pipeline/test_medications_index.py
git commit -m "feat(medications): add per-service medication denormalised index"
git add data/services/actas/medications/
git commit -m "data: generate ACTAS medication index"
```

---

### Task 13: Point routers at new paths

**Files:**
- Modify: `src/python/guidelines/router.py`
- Modify: `src/python/medication/router.py`
- Modify: `src/python/sources/router.py`
- Test: update existing router tests

- [ ] **Step 1: Update each router to use `resolve_service_structured_dir(active_service().id)` and `service_medications_dir(active_service().id)`.**
- [ ] **Step 2: Guidelines router emits both `guideline_id` and legacy `cmg_number` (from `extra`) in its response.**
- [ ] **Step 3: Run router tests, expect pass.**
- [ ] **Step 4: Commit**

```bash
git add src/python/guidelines/router.py src/python/medication/router.py src/python/sources/router.py tests/python/
git commit -m "refactor: point guidelines/medication/sources routers at active service"
```

---

## Phase 2c — ChromaDB split + retriever rewrite

### Task 14: ChromaDB split in migration + `seed.py`

**Files:**
- Modify: `scripts/migrate_to_multi_service.py` (add chroma migration step)
- Modify: `src/python/seed.py`
- Test: extend `test_migrate_to_multi_service.py`

- [ ] **Step 1: Write failing test** using a temp chroma client: seed `cmg_guidelines` + `paramedic_notes` with fixture chunks, run migration, assert `guidelines_actas` + `personal_actas` exist with the right chunks and `service: "actas"` metadata on every personal chunk.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement.** Migration reads both legacy collections, writes to new collections with added metadata, leaves legacy collections intact.
- [ ] **Step 4: Rewrite `seed.py`** to iterate `REGISTRY`; for each service check `guidelines_<id>` exists, otherwise copy from bundled `build/resources/data/services/<id>/chroma/`, otherwise run that service's adapter's `run_pipeline()` as a dev fallback.
- [ ] **Step 5: Run tests, expect pass.**
- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_to_multi_service.py src/python/seed.py tests/
git commit -m "feat(migration): split Chroma collections per service; seed per-service"
```

---

### Task 15: SQLite service column + backfill

**Files:**
- Modify: `src/python/quiz/store.py`
- Test: `tests/python/quiz/test_store_service_scoping.py`

- [ ] **Step 1: Write failing test** that inserting questions for services `actas` and `at` and querying for `actas` returns only ACTAS questions.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement.** Add `service TEXT NOT NULL` to `questions`, `sessions`, `mastery`, `history`. Add schema-version bump + migration that sets existing rows to `actas`. Every query gains `WHERE service = ?`.
- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit**

```bash
git add src/python/quiz/store.py tests/python/quiz/test_store_service_scoping.py
git commit -m "feat(quiz): scope questions/sessions/mastery/history by service"
```

---

### Task 16: Retriever, agent, router, factory, models — qualification-set filter

**Files:**
- Modify: `src/python/quiz/retriever.py`
- Modify: `src/python/quiz/agent.py`
- Modify: `src/python/quiz/router.py`
- Modify: `src/python/quiz/models.py`
- Modify: `src/python/llm/factory.py`
- Test: `tests/python/quiz/test_retriever_qualifications.py`

- [ ] **Step 1: Write failing tests:**
  - Retriever for service `actas` must return zero hits from any other service's collection.
  - Retriever with effective `{AP}` excludes chunks with `qualifications_required: ["ICP"]`.
  - Retriever with effective `{AP, ICP}` includes both.
  - Empty `qualifications_required` is always returned.
  - Personal chunk with `scope: "general"` is returned for any service; `service-specific` chunk is only returned for its service.

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement.** Retriever queries `guidelines_<active>` + `personal_<active>`, filtering with Chroma `where` clauses on `qualifications_required` membership and `scope`. Merge results per §15.11 ranking rule.

- [ ] **Step 4: Remove `skill_level` from router/agent/factory/models.** Router accepts `{active_service, effective_qualifications}` (derived server-side from `settings.json`). Agent prompt becomes service-neutral — takes service display name and qualification list as template vars.

- [ ] **Step 5: Run tests, expect pass.**

- [ ] **Step 6: Run full quiz test suite** to confirm nothing else depends on `skill_level`.

```bash
pytest tests/python/quiz/ tests/quiz/ -x -q
```

- [ ] **Step 7: Commit**

```bash
git add src/python/quiz/ src/python/llm/factory.py tests/python/quiz/
git commit -m "refactor(quiz): replace skill_level with qualification-set retrieval filter"
```

---

### Task 17: Cross-service isolation test

**Files:**
- Test: `tests/python/services/test_isolation.py`

- [ ] **Step 1: Write the test.** Ingest minimal fixtures for `actas` (1 doc) and `at` (1 doc) into fresh collections. Call every retrieval path in the codebase (quiz retriever, guidelines router, medication router, search router) with `active_service = actas` and assert zero `at`-tagged results across every response. Then swap and repeat.

- [ ] **Step 2: Run, expect pass (if earlier tasks are correct).**

- [ ] **Step 3: Commit**

```bash
git add tests/python/services/test_isolation.py
git commit -m "test(services): cross-service retrieval isolation"
```

---

## Phase 3 — Frontend UX

### Task 18: `ServiceProvider`, `useService`, `ServiceChip`

**Files:**
- Create: `src/renderer/providers/ServiceProvider.tsx`
- Create: `src/renderer/hooks/useService.ts`
- Create: `src/renderer/components/ServiceChip.tsx`
- Test: `tests/renderer/useService.test.tsx`, `tests/renderer/ServiceChip.test.tsx`

- [ ] **Step 1: Write failing tests** — provider fetches `/services`, exposes `activeService`, `baseQualification`, `endorsements`, `setActiveService`, etc. Chip renders display name + qualification summary.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement.** Provider does a single fetch on mount; `useService()` hook throws if used outside. Wrap `App.tsx` with provider.
- [ ] **Step 4: Wire `ServiceChip` into `Sidebar.tsx`.**
- [ ] **Step 5: Run tests, expect pass.**
- [ ] **Step 6: Commit**

```bash
git add src/renderer/providers/ServiceProvider.tsx src/renderer/hooks/useService.ts src/renderer/components/ServiceChip.tsx src/renderer/components/Sidebar.tsx src/renderer/App.tsx tests/renderer/
git commit -m "feat(renderer): ServiceProvider + useService + ServiceChip"
```

---

### Task 19: `ServiceSetupModal` (first-run + edit)

**Files:**
- Create: `src/renderer/components/ServiceSetupModal.tsx`
- Modify: `src/renderer/App.tsx` (render modal when unconfigured)
- Test: `tests/renderer/ServiceSetupModal.test.tsx`

- [ ] **Step 1: Write failing tests** — modal is blocking when `active_service` unset; shows registered services; selecting service shows bases; selecting base shows endorsements filtered by `requires_base`; save calls `PUT /settings`.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests, expect pass.**
- [ ] **Step 5: Commit**

```bash
git add src/renderer/components/ServiceSetupModal.tsx src/renderer/App.tsx tests/renderer/ServiceSetupModal.test.tsx
git commit -m "feat(renderer): first-run service setup modal"
```

---

### Task 20: Settings page — Active service + Qualifications + per-doc retag

**Files:**
- Modify: `src/renderer/pages/Settings.tsx`
- Modify: `src/python/settings/router.py`
- Test: `tests/renderer/Settings.test.tsx`

- [ ] **Step 1: Write failing tests** — active-service radio, qualification edit form, per-doc table with service + scope dropdowns, confirmation dialog on service switch.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement backend endpoints** — `PUT /settings/active-service`, `PUT /settings/qualifications`, `PUT /settings/personal-docs/<doc_id>` to retag a single doc (rewrite front-matter + re-ingest that doc).
- [ ] **Step 4: Implement frontend sections.**
- [ ] **Step 5: Run tests, expect pass.**
- [ ] **Step 6: Commit**

```bash
git add src/renderer/pages/Settings.tsx src/python/settings/router.py tests/
git commit -m "feat(settings): active-service, qualifications, per-doc retag UI"
```

---

### Task 21: Cache invalidation + empty-state + service chip rollout

**Files:**
- Modify: `src/renderer/providers/ResourceCacheProvider.tsx`
- Modify: `src/renderer/pages/Dashboard.tsx`, `Quiz.tsx`, `Feedback.tsx`, `Library.tsx`, `Medication.tsx`, `Guidelines.tsx`
- Modify: `src/renderer/components/UploadDialog.tsx`
- Test: `tests/renderer/ResourceCacheProvider.test.tsx`, per-page smoke tests

- [ ] **Step 1: Write failing tests** — cache keys namespaced by active service; switching service keeps old entries in memory but fetches fresh for the new service; Dashboard shows empty state text when no mastery rows exist for the active service; upload dialog has service + scope dropdowns.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Add `ServiceChip` to each content-page header.**
- [ ] **Step 5: Run tests, expect pass.**
- [ ] **Step 6: Commit**

```bash
git add src/renderer/providers/ResourceCacheProvider.tsx src/renderer/pages/ src/renderer/components/UploadDialog.tsx tests/renderer/
git commit -m "feat(renderer): cache namespacing, empty-state, upload service/scope, chip rollout"
```

---

## Phase 4 — Tas Phase 0 discovery + packaging

### Task 22: Tas Phase 0 discovery + findings doc

**Files:**
- Create: `Guides/at-cpg-extraction-findings.md`
- Create: `scripts/at_phase0_probe.py` (Playwright probe — committed for reproducibility)

This is an investigation task, not a TDD task. Output is a findings doc committed to the repo.

- [ ] **Step 1: Install Playwright in a dev venv if not already available.**

```bash
pip install playwright && playwright install chromium
```

- [ ] **Step 2: Write `scripts/at_phase0_probe.py`** — loads `https://cpg.ambulance.tas.gov.au/tabs/guidelines`, navigates a sample of guidelines across at least three categories (text-only, dose-heavy, flowchart-heavy), records all network traffic (XHR, fetch, WS) to a JSON file.
- [ ] **Step 3: Run the probe** against at least three representative guidelines; save results to `tmp/at-phase0/`.
- [ ] **Step 4: Analyse the network traffic.** Identify:
  - The content source (CDN JSON? unauth GraphQL? Cognito identity-pool-authed GraphQL? lazy JS chunk?)
  - Per-guideline request pattern and any indexing endpoint
  - Auth requirements
  - For each of text, dose tables, flowcharts: the delivered format (JSON model / HTML / SVG / image / PDF)
  - Whether flowcharts are data-driven (nodes/edges) or raster/PDF
- [ ] **Step 5: Write `Guides/at-cpg-extraction-findings.md`** summarising the above, including concrete URL patterns, auth flow, and a recommendation for each of Tas Phase 1–3 handlers.
- [ ] **Step 6: Ask the user to review the findings doc** before committing. Surface any blockers (e.g., auth wall) in that review.
- [ ] **Step 7: Commit**

```bash
git add Guides/at-cpg-extraction-findings.md scripts/at_phase0_probe.py
git commit -m "docs: Ambulance Tasmania Phase 0 extraction findings"
```

---

### Task 23: Per-service bundled Chroma at build time

**Files:**
- Create: `scripts/build_bundled_chroma.py`
- Modify: `scripts/package-backend.sh`, `scripts/package-backend.ps1`
- Modify: `electron-builder.yml`, `electron-builder.personal.yml`
- Modify: `scripts/upload-personal-data.sh`

- [ ] **Step 1: Write `build_bundled_chroma.py`.** For each registered service, spawn a fresh Chroma instance, ingest that service's `data/services/<id>/structured/` into `guidelines_<id>`, write the resulting Chroma tree to `build/resources/data/services/<id>/chroma/`.
- [ ] **Step 2: Update packaging scripts** to invoke it and bundle each service's tree. Remove the old `build/resources/data/chroma_db/` single-tree step.
- [ ] **Step 3: Update `electron-builder.yml` extraResources list accordingly.**
- [ ] **Step 4: Update `electron-builder.personal.yml`** to reflect per-service downloads.
- [ ] **Step 5: Update `scripts/upload-personal-data.sh`** to enumerate `personal_<id>` collections and upload each as a separate release asset.
- [ ] **Step 6: Run a packaged build dry-run (macOS arm64 only is fine)** and confirm the bundled tree is correct.
- [ ] **Step 7: Commit**

```bash
git add scripts/build_bundled_chroma.py scripts/package-backend.sh scripts/package-backend.ps1 scripts/upload-personal-data.sh electron-builder.yml electron-builder.personal.yml
git commit -m "build: per-service bundled Chroma trees"
```

---

### Task 24: `Guides/adding-a-service.md` + user sign-off

**Files:**
- Create: `Guides/adding-a-service.md`

Documents the repeatable process per spec §8:
1. Source & commit scope-of-practice doc + category mapping doc.
2. Add `Service(...)` registry entry.
3. Create `src/python/pipeline/<id>/` adapter implementing `run_pipeline()`.
4. Run Phase 0 discovery; commit findings doc.
5. Implement Phases 1–4.
6. Update packaging rules.
7. Add service-specific tests (qualifications, adapter contract, golden flowcharts).
8. User sign-off checklist.

- [ ] **Step 1: Draft the guide.**
- [ ] **Step 2: Commit**

```bash
git add Guides/adding-a-service.md
git commit -m "docs: Guide for adding a new ambulance service"
```

---

## Acceptance for Plan A

At Plan A completion the app must:

- Start on a fresh clone with only ACTAS content; `active_service: "actas"` works end-to-end (guidelines browser, medication browser, quiz, mastery, upload).
- Pass the cross-service isolation test (Task 17) for ACTAS + AT fixtures.
- Expose `GET /services` returning both ACTAS and AT entries.
- Render a blocking first-run modal when `active_service` is unset.
- Ship a committed `Guides/at-cpg-extraction-findings.md` produced from live Playwright traffic.
- Have zero references to `CMG_STRUCTURED_DIR`, `USER_CMG_STRUCTURED_DIR`, `resolve_cmg_structured_dir`, `skill_level`, or the legacy collection names `cmg_guidelines` / `paramedic_notes` outside the migration script itself.
- Pass the frontend and Python test suites at the same pass/fail profile as `KNOWN_TEST_FAILURES.md` declares (no new regressions).

Tas content ingestion (Phases 1–4) is out of scope for Plan A and will be specified in **Plan B** once the Phase 0 findings doc is in hand.

---

## Plan review corrections

Addresses plan-review feedback. Authoritative where it conflicts with earlier task descriptions.

### Task ordering fixes

- **Run Task 10 migration against real data** as a dedicated numbered commit between Task 10 Step 5 and Task 11 Step 1. The original Task 10 Step 5 is amended: "commit the script, then immediately run it against real repo data (`python scripts/migrate_to_multi_service.py`), commit the resulting `data/services/actas/structured/*.json` tree and the old directory cleanup as a separate commit." Task 11 depends on this having happened.
- **Task 14 must re-ingest into Chroma after Task 11's backfill** so chunks in `guidelines_actas` carry `qualifications_required`. Task 14 Step 3 is extended: after splitting `cmg_guidelines` → `guidelines_actas`, re-run the ACTAS chunker against the post-backfill structured JSON so new chunks include the `qualifications_required` metadata. Verify with a test that a query for effective `{AP}` returns zero chunks whose metadata has `"ICP" in qualifications_required`.
- **Task 9 depends on `personal_<service>` collection existing.** Add a line: "the upload router's ingest path must lazily create the per-service personal collection if absent; Task 9 tests stub Chroma with `get_or_create_collection`." This works before Task 14 because `get_or_create_collection` is idempotent.
- **Task 13 router changes land before Task 14's collection split is acceptable** because Task 13 routers do not hit Chroma — they read structured JSON and the medication index. Explicit note added.

### Missing-task additions

**Task 8b — Migrate `src/python/settings/router.py` paths**. Between Task 8 and Task 9. The settings router imports `CMG_STRUCTURED_DIR` and the "Re-run Pipeline" handler calls the legacy chunker. Rewrite to read active service via `active_service()` and trigger that service's adapter's `run_pipeline()`. Tests: hitting `POST /settings/re-run-pipeline` with `active_service: "actas"` kicks the ACTAS adapter; with a service that has no adapter implemented yet (AT pre-Plan-B) returns HTTP 409 `{"error": "adapter not ready"}`.

**Task 13b — Migrate `src/python/pipeline/personal_docs/`**. Between Task 13 and Task 14. The personal docs ingester currently writes into `paramedic_notes`. Rewrite to read `service` + `scope` front-matter from each file and ingest into `personal_<service>`. Tests: ingest a fixture file with `service: actas, scope: general` lands chunks in `personal_actas` with `scope=general`; ingest with `service: at` lands chunks in `personal_at`.

**Task 14b — Migrate `paramedic_notes` → `personal_<service>` explicitly**. Make this an explicit step inside Task 14 (currently implied by a test). Iterate every chunk in `paramedic_notes`, write into `personal_<service>` using the `service` front-matter of the source doc (or `personal_actas` if absent), preserving the `scope` field. Commit the resulting Chroma state change as a data commit.

**Task 15b — Migrate existing `settings.json` `skill_level` key**. Part of migration script Task 10 is amended to detect a legacy `skill_level` value and rewrite it to `base_qualification` + empty `endorsements` as per spec §15.4. Test covers both `AP` and `ICP` legacy values. This is added to Task 10's test list.

**Task 16b — Ranking math + source-hierarchy wiring**. Split from Task 16 for clarity. Implements percentile normalisation across `guidelines_<id>` and `personal_<id>` query results and applies the active service's `source_hierarchy` weights before sorting. Tests:
- Two collections return results with different raw distance scales; after normalisation the top result is from the collection whose top hit is the strongest relative to its own distribution.
- A `ref_doc` chunk with equal normalised rank to an `upload` chunk ranks above the `upload` chunk.

**Task 19b — `types/api.ts` and frontend `cmg_number` fallback**. Standalone task under Phase 3. Updates `src/renderer/types/api.ts` to add `guideline_id: string; cmg_number?: string` on relevant types. Updates every consumer (Guidelines, Quiz, Feedback, Medication pages) to read `g.guideline_id ?? g.cmg_number`. Tests: a fixture response carrying only `guideline_id` renders correctly; a fixture carrying only `cmg_number` still renders (deprecation window coverage).

**Task 20b — "Clean up legacy data" Settings action**. Part of Task 20. Add a `POST /settings/cleanup-legacy-data` endpoint that deletes the old `cmg_guidelines` + `paramedic_notes` Chroma collections and the `data/cmgs/structured/` tree. Frontend: a destructive-styled button under Settings → Indexed data management, gated behind a confirmation dialog. Not automatic — user must click.

### Task clarifications

- **Task 4 test — `/services` response shape**. The endpoint strips `adapter`, `scope_source_doc`, `category_mapping_doc`, and `source_hierarchy` from the response (those are backend-only). Public fields are `id`, `display_name`, `region`, `accent_colour`, `source_url`, `qualifications`. Update Task 4 test to assert exactly this set and that no other fields leak.
- **Task 9 conftest**. Upload router tests require a fixture that: (a) monkeypatches `USER_DATA_ROOT` to a tmp_path; (b) initialises an in-memory Chroma client bound to that tmp path; (c) ensures `active_service` in the tmp `settings.json` is `actas`. Add to `tests/python/upload/conftest.py` as part of Task 9.
- **Task 11 ICP marker source**. The current ICP markers live in `src/python/quiz/agent.py` inside the prompt builder; additionally, ICP-restricted medicines are inferable from ACTAS CMG sections tagged with "ICP" in the `profiles` or `scope` field of the structured JSON. Task 11 Step 3 must cite these two sources explicitly in its implementation.
- **Task 12 decision — pick one file**. Create `src/python/pipeline/actas/medications_index.py` as a new module (not inside `chunker.py`). `chunker.py` stays focused on chunking; the index builder calls are added to `orchestrator.py` after chunking completes.
- **Task 20 `doc_id` scheme**. `doc_id` is the structured-file path relative to `data/personal_docs/structured/` with the extension stripped (e.g., `ECGs` for `ECGs.md`). Uploaded files use their generated filename minus extension. The frontend Settings page lists every structured file under its doc_id.
- **Task 22 intranet URL**. The intranet URL in Task 6 for the AT scope-of-practice matrix is a placeholder. The public alternative is the Ambulance Tasmania CPG site's "About / Scope of Practice" page (confirmed during Phase 0 probe). Task 22's findings doc must capture the correct public URL before Task 6 is finalised. Task 6 and Task 22 therefore interlock: Task 6 drafts with a TBD citation; Task 22 fills in the authoritative URL; both are committed after Phase 0.

### Vision settings row — explicit deferral

The spec §15.13 "Vision model" Settings row is deferred to Plan B, where `llm/vision.py` moves from stub to real implementation. Plan A ships the stub module only so imports don't break. This deferral is explicit; it is not an oversight.
