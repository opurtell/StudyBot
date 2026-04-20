# Service Isolation & Retriever Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the singleton retriever so switching `active_service` immediately re-scopes all quiz and search queries to the new service, with no cross-contamination.

**Architecture:** Add a `reset_retriever()` function that clears the three-level singleton chain (`retriever._shared_retriever`, `quiz/router._retriever`, `search/router._retriever`). Wire it into `settings/router.py:save_settings()` when `active_service` changes. Also fix the service-blind `vector_store_status()` and `clear_vector_store()` endpoints, and remove hardcoded ACTAS references from the ACTAS chunker and quiz prompt.

**Tech Stack:** Python 3.10+, ChromaDB, FastAPI, pytest, chromadb in-memory client for tests

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/python/quiz/retriever.py` | Modify | Add `reset_retriever()` to clear singleton |
| `src/python/quiz/router.py` | Modify | Add `reset_quiz_retriever()` to clear local singleton; call `reset_retriever()` from retriever module |
| `src/python/search/router.py` | Modify | Add `reset_search_retriever()` to clear local singleton |
| `src/python/settings/router.py` | Modify | Detect `active_service` change in `save_settings()`; call all reset functions; fix `vector_store_status()` and `clear_vector_store()` to be service-aware |
| `src/python/pipeline/actas/chunker.py` | Modify | Accept `collection_name` parameter instead of hardcoding `"guidelines_actas"` |
| `src/python/quiz/agent.py` | Modify | Replace hardcoded `"ACTAS CMG 14.1"` with dynamic service citation |
| `src/python/seed.py` | Modify | Pass service-scoped collection name to ACTAS chunker |
| `tests/python/services/test_retriever_reset.py` | Create | Test that `reset_retriever()` clears singletons and next retrieval uses new service |
| `tests/python/services/test_settings_invalidation.py` | Create | Test that `save_settings()` with changed `active_service` triggers retriever reset |

---

### Task 1: Add `reset_retriever()` to retriever module

**Files:**
- Modify: `src/python/quiz/retriever.py:19-21,226-232`
- Test: `tests/python/services/test_retriever_reset.py`

- [ ] **Step 1: Write the failing test**

Create `tests/python/services/test_retriever_reset.py`:

```python
"""Test that reset_retriever() clears the singleton so the next
get_retriever() call picks up the current active_service."""

import chromadb
import pytest

import quiz.retriever as retriever_mod


@pytest.fixture(autouse=True)
def _clean_singleton():
    """Ensure no cached retriever leaks between tests."""
    prev = retriever_mod._shared_retriever
    retriever_mod._shared_retriever = None
    # Wipe in-memory ChromaDB
    _c = chromadb.Client()
    for col in _c.list_collections():
        _c.delete_collection(col.name)
    yield
    retriever_mod._shared_retriever = prev


def test_reset_clears_singleton():
    """After reset_retriever(), _shared_retriever must be None."""
    client = chromadb.Client()

    # Seed ACTAS data so get_retriever() doesn't fail on empty collections
    col = client.get_or_create_collection("guidelines_actas", metadata={"hnsw:space": "cosine"})
    col.add(ids=["a"], documents=["actas chunk"], metadatas=[{"source_type": "cmg", "visibility": "both"}])

    r1 = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = r1
    assert retriever_mod._shared_retriever is r1

    retriever_mod.reset_retriever()
    assert retriever_mod._shared_retriever is None


def test_get_retriever_after_reset_uses_new_service(tmp_path, monkeypatch):
    """After reset, get_retriever() should build a retriever for the
    currently-active service, not a previously-cached one."""
    from services.registry import REGISTRY

    client = chromadb.Client()

    # Seed both services
    for svc in REGISTRY:
        col = client.get_or_create_collection(
            f"guidelines_{svc.id}", metadata={"hnsw:space": "cosine"}
        )
        col.add(
            ids=[f"{svc.id}_1"],
            documents=[f"{svc.display_name} cardiac protocol"],
            metadatas=[{"source_type": "cmg", "section": "Cardiac", "visibility": "both"}],
        )

    # Simulate actas was active, retriever cached
    actas_r = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = actas_r

    # Reset
    retriever_mod.reset_retriever()

    # Monkeypatch active_service to return AT
    at_svc = [s for s in REGISTRY if s.id == "at"][0]
    monkeypatch.setattr(
        "services.active.active_service", lambda: at_svc
    )

    # get_retriever() should now return an AT-scoped retriever
    new_r = retriever_mod.get_retriever()
    assert new_r._service_id == "at"
    assert new_r is not actas_r
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_retriever_reset.py::test_reset_clears_singleton -v`
Expected: FAIL — `reset_retriever` does not exist

- [ ] **Step 3: Write minimal implementation**

In `src/python/quiz/retriever.py`, add after the `warm_retriever()` function (after line 236):

```python
def reset_retriever() -> None:
    """Clear the shared retriever singleton.

    Call this when active_service changes so the next get_retriever()
    creates a fresh Retriever scoped to the new service.
    """
    global _shared_retriever
    with _retriever_lock:
        _shared_retriever = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_retriever_reset.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/quiz/retriever.py tests/python/services/test_retriever_reset.py
git commit -m "feat: add reset_retriever() to clear singleton on service switch"
```

---

### Task 2: Add reset functions to quiz and search routers

**Files:**
- Modify: `src/python/quiz/router.py:31,46-50`
- Modify: `src/python/search/router.py:11,14-18`

- [ ] **Step 1: Add reset to quiz router**

In `src/python/quiz/router.py`, add after `_get_retriever()` (after line 50):

```python
def reset_quiz_retriever() -> None:
    """Clear the local and shared retriever singletons."""
    global _retriever
    _retriever = None
    from .retriever import reset_retriever
    reset_retriever()
```

- [ ] **Step 2: Add reset to search router**

In `src/python/search/router.py`, add after `_get_retriever()` (after line 18):

```python
def reset_search_retriever() -> None:
    """Clear the local and shared retriever singletons."""
    global _retriever
    _retriever = None
    from quiz.retriever import reset_retriever
    reset_retriever()
```

- [ ] **Step 3: Commit**

```bash
git add src/python/quiz/router.py src/python/search/router.py
git commit -m "feat: add reset functions to quiz and search routers"
```

---

### Task 3: Wire reset into settings save when active_service changes

**Files:**
- Modify: `src/python/settings/router.py:115-127`
- Test: `tests/python/services/test_settings_invalidation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/python/services/test_settings_invalidation.py`:

```python
"""Test that saving settings with a new active_service invalidates
the retriever, guideline, and medication caches."""

import json
import chromadb
import pytest

import quiz.retriever as retriever_mod


@pytest.fixture()
def settings_file(tmp_path):
    """Create a temporary settings file with actas active."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"active_service": "actas"}))
    return path


@pytest.fixture(autouse=True)
def _clean_retriever():
    prev = retriever_mod._shared_retriever
    retriever_mod._shared_retriever = None
    _c = chromadb.Client()
    for col in _c.list_collections():
        _c.delete_collection(col.name)
    yield
    retriever_mod._shared_retriever = prev


def test_save_with_changed_service_resets_retriever(settings_file, monkeypatch):
    """Saving a different active_service must clear the retriever singleton."""
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings_file)

    # Prime the singleton with an actas retriever
    client = chromadb.Client()
    actas_r = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = actas_r

    # Import after monkeypatch so it uses our tmp path
    from settings.router import SaveSettingsRequest, save_settings

    req = SaveSettingsRequest(
        providers={},
        active_provider="",
        quiz_model="test",
        clean_model="test",
        active_service="at",
    )
    save_settings(req)

    assert retriever_mod._shared_retriever is None, (
        "Retriever singleton should be cleared after active_service change"
    )


def test_save_with_same_service_does_not_reset_retriever(settings_file, monkeypatch):
    """Saving the same active_service should NOT clear the retriever."""
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings_file)

    client = chromadb.Client()
    actas_r = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = actas_r

    from settings.router import SaveSettingsRequest, save_settings

    req = SaveSettingsRequest(
        providers={},
        active_provider="",
        quiz_model="test",
        clean_model="test",
        active_service="actas",
    )
    save_settings(req)

    assert retriever_mod._shared_retriever is actas_r, (
        "Retriever singleton should NOT be cleared when service unchanged"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_settings_invalidation.py -v`
Expected: FAIL — retriever singleton is not cleared on service change

- [ ] **Step 3: Implement service-change detection in save_settings**

Replace `src/python/settings/router.py:save_settings()` (lines 115-127) with:

```python
@router.put("")
def save_settings(req: SaveSettingsRequest) -> dict:
    global _settings_cache
    config = req.model_dump()

    # Detect active_service change before writing
    _previous_service = _read_active_service_id()

    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    with _cache_lock:
        _settings_cache = _clone_dict(config)

    # Invalidate caches that depend on active_service
    if config.get("active_service") and config["active_service"] != _previous_service:
        _invalidate_service_caches()

    return {"status": "ok"}
```

Add the two helper functions before `save_settings()`:

```python
def _read_active_service_id() -> str | None:
    """Read the current active_service from disk without caching."""
    try:
        if _SETTINGS_PATH.is_file():
            data = json.loads(_SETTINGS_PATH.read_text())
            return data.get("active_service")
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _invalidate_service_caches() -> None:
    """Clear all caches that depend on the active service."""
    _invalidate_read_caches()
    try:
        from quiz.router import reset_quiz_retriever
        reset_quiz_retriever()
    except Exception:
        pass
    try:
        from search.router import reset_search_retriever
        reset_search_retriever()
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_settings_invalidation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/settings/router.py tests/python/services/test_settings_invalidation.py
git commit -m "fix: invalidate retriever singletons when active_service changes"
```

---

### Task 4: Fix `vector_store_status()` to be service-aware

**Files:**
- Modify: `src/python/settings/router.py:246-269`

- [ ] **Step 1: Write the failing test**

Append to `tests/python/services/test_settings_invalidation.py`:

```python
def test_vector_store_status_checks_all_services(tmp_path, monkeypatch):
    """vector_store_status must report chunk counts for the active
    service's collections, not hardcoded ACTAS names."""
    from services.registry import REGISTRY
    import chromadb

    db_dir = tmp_path / "chroma_db"
    db_dir.mkdir()
    client = chromadb.PersistentClient(path=str(db_dir))

    # Seed AT guidelines only
    at_col = client.get_or_create_collection("guidelines_at")
    at_col.add(ids=["at1"], documents=["AT chunk"], metadatas=[{"source_type": "cmg"}])

    monkeypatch.setattr("settings.router.CHROMA_DB_DIR", db_dir)
    # Active service is AT
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"active_service": "at"}))
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings)

    from settings.router import vector_store_status
    status = vector_store_status()

    assert status["cmg"] == 1, f"Expected 1 AT CMG chunk, got {status['cmg']}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_settings_invalidation.py::test_vector_store_status_checks_all_services -v`
Expected: FAIL — returns 0 because it only checks `guidelines_actas`

- [ ] **Step 3: Implement service-aware vector_store_status**

Replace `src/python/settings/router.py:vector_store_status()` (lines 246-269) with:

```python
@router.get("/vector-store/status")
def vector_store_status() -> dict:
    """Return chunk counts per source type for the active service's collections."""
    if not CHROMA_DB_DIR.exists():
        return {"cmg": 0, "ref_doc": 0, "cpd_doc": 0, "notability_note": 0}

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    counts: dict[str, int] = {"cmg": 0, "ref_doc": 0, "cpd_doc": 0, "notability_note": 0}

    service_id = active_service().id
    guidelines_name = f"guidelines_{service_id}"
    personal_name = f"personal_{service_id}"

    try:
        cmg_col = client.get_or_create_collection(guidelines_name)
        counts["cmg"] = cmg_col.count()
    except Exception:
        pass

    try:
        notes_col = client.get_or_create_collection(personal_name)
        for st in ("ref_doc", "cpd_doc", "notability_note"):
            result = notes_col.get(where={"source_type": st})
            counts[st] = len(result["ids"])
    except Exception:
        pass

    return counts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_settings_invalidation.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/settings/router.py tests/python/services/test_settings_invalidation.py
git commit -m "fix: make vector_store_status service-aware instead of ACTAS-only"
```

---

### Task 5: Fix `clear_vector_store()` to be service-aware

**Files:**
- Modify: `src/python/settings/router.py:272-312`

- [ ] **Step 1: Write the failing test**

Append to `tests/python/services/test_settings_invalidation.py`:

```python
def test_clear_cmg_deletes_active_service_collection(tmp_path, monkeypatch):
    """clear_vector_store with source_type='cmg' must delete the active
    service's guidelines collection, not hardcoded 'guidelines_actas'."""
    import chromadb

    db_dir = tmp_path / "chroma_db"
    db_dir.mkdir()
    client = chromadb.PersistentClient(path=str(db_dir))

    # Create both collections with data
    at_col = client.get_or_create_collection("guidelines_at")
    at_col.add(ids=["at1"], documents=["AT chunk"], metadatas=[{"source_type": "cmg"}])
    actas_col = client.get_or_create_collection("guidelines_actas")
    actas_col.add(ids=["a1"], documents=["ACTAS chunk"], metadatas=[{"source_type": "cmg"}])

    monkeypatch.setattr("settings.router.CHROMA_DB_DIR", db_dir)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"active_service": "at"}))
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings)

    from settings.router import clear_vector_store
    clear_vector_store(source_type="cmg")

    # AT should be deleted
    names = [c.name for c in client.list_collections()]
    assert "guidelines_at" not in names, "AT collection should be deleted"
    # ACTAS should survive
    assert "guidelines_actas" in names, "ACTAS collection should NOT be deleted when AT is active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_settings_invalidation.py::test_clear_cmg_deletes_active_service_collection -v`
Expected: FAIL — deletes `guidelines_actas` instead of `guidelines_at`

- [ ] **Step 3: Implement service-aware clear_vector_store**

Replace `src/python/settings/router.py:clear_vector_store()` (lines 272-312) with:

```python
@router.post("/vector-store/clear")
def clear_vector_store(source_type: str | None = None) -> dict:
    """Clear indexed data for the active service. Optional source_type for selective clearing."""
    if source_type is None:
        if CHROMA_DB_DIR.exists():
            shutil.rmtree(CHROMA_DB_DIR)
        _invalidate_read_caches()
        return {"status": "cleared"}

    valid_types = ("cmg", "ref_doc", "cpd_doc", "notability_note")
    if source_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Must be one of: {', '.join(valid_types)}",
        )

    if not CHROMA_DB_DIR.exists():
        return {"status": "cleared", "source_type": source_type}

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    service_id = active_service().id

    if source_type == "cmg":
        collection_name = f"guidelines_{service_id}"
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
    else:
        collection_name = f"personal_{service_id}"
        try:
            notes_col = client.get_or_create_collection(collection_name)
            notes_col.delete(where={"source_type": source_type})
        except Exception:
            pass

    _invalidate_read_caches()
    return {"status": "cleared", "source_type": source_type}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/services/test_settings_invalidation.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/settings/router.py tests/python/services/test_settings_invalidation.py
git commit -m "fix: make clear_vector_store service-aware instead of ACTAS-only"
```

---

### Task 6: Make ACTAS chunker accept collection_name parameter

**Files:**
- Modify: `src/python/pipeline/actas/chunker.py:91-93,116`
- Modify: `src/python/seed.py:270-288`

- [ ] **Step 1: Write the failing test**

Create `tests/python/pipeline/test_actas_chunker_collection_name.py`:

```python
"""Test that the ACTAS chunker accepts an optional collection_name."""

import json
import os
import tempfile

import chromadb
import pytest

from pipeline.actas.chunker import chunk_and_ingest


def _write_sample_cmg(structured_dir: str) -> str:
    """Write a minimal valid CMG JSON file and return its path."""
    data = {
        "id": "test_cmg_1",
        "cmg_number": "1.0",
        "title": "Test CMG",
        "section": "Cardiac",
        "is_icp_only": False,
        "content_markdown": "# Test Section\nAdrenaline dose for cardiac arrest is 1mg.",
        "dose_lookup": {},
        "extraction_metadata": {"timestamp": "2025-01-01"},
    }
    path = os.path.join(structured_dir, "test_cmg_1.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def test_default_collection_name():
    """Without collection_name, chunks go to 'guidelines_actas'."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "chroma")
        structured_dir = os.path.join(tmp, "structured")
        os.makedirs(structured_dir)
        _write_sample_cmg(structured_dir)

        chunk_and_ingest(structured_dir=structured_dir, db_path=db_path)

        client = chromadb.PersistentClient(path=db_path)
        col = client.get_collection("guidelines_actas")
        assert col.count() > 0


def test_custom_collection_name():
    """With collection_name, chunks go to the named collection."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "chroma")
        structured_dir = os.path.join(tmp, "structured")
        os.makedirs(structured_dir)
        _write_sample_cmg(structured_dir)

        chunk_and_ingest(
            structured_dir=structured_dir,
            db_path=db_path,
            collection_name="guidelines_at",
        )

        client = chromadb.PersistentClient(path=db_path)
        col = client.get_collection("guidelines_at")
        assert col.count() > 0

        # Default collection should NOT exist
        names = [c.name for c in client.list_collections()]
        assert "guidelines_actas" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/pipeline/test_actas_chunker_collection_name.py::test_custom_collection_name -v`
Expected: FAIL — `chunk_and_ingest()` doesn't accept `collection_name`

- [ ] **Step 3: Update ACTAS chunker signature**

In `src/python/pipeline/actas/chunker.py`, change the `chunk_and_ingest` function signature (line 91-93) from:

```python
def chunk_and_ingest(
    structured_dir: str = "data/cmgs/structured/", db_path: str = str(CHROMA_DB_DIR)
):
```

to:

```python
def chunk_and_ingest(
    structured_dir: str = "data/cmgs/structured/",
    db_path: str = str(CHROMA_DB_DIR),
    collection_name: str = "guidelines_actas",
):
```

And change line 116 from:

```python
    collection = client.get_or_create_collection(name="guidelines_actas")
```

to:

```python
    collection = client.get_or_create_collection(name=collection_name)
```

- [ ] **Step 4: Update seed.py to pass service-scoped collection name**

In `src/python/seed.py`, update `_run_adapter_seed()` (lines 270-288) to pass the service-scoped collection name. Replace the entire function with:

```python
def _run_adapter_seed(service) -> None:
    """Run the service's chunker to seed guidelines data."""
    service_id = service.id
    adapter = service.adapter
    collection_name = _guidelines_collection_name(service_id)

    if "actas" in adapter:
        try:
            from pipeline.actas.chunker import chunk_and_ingest as actas_chunk_and_ingest

            structured_dir = str(resolve_service_structured_dir(service_id))
            logger.info("Auto-seeding guidelines_%s from %s via adapter.", service_id, structured_dir)
            actas_chunk_and_ingest(
                structured_dir=structured_dir,
                collection_name=collection_name,
            )
            logger.info("guidelines_%s auto-seed complete.", service_id)
        except Exception:
            logger.exception("Failed to seed guidelines_%s via ACTAS adapter.", service_id)
    elif "at" in adapter:
        try:
            from pipeline.at.chunker import chunk_and_ingest as at_chunk_and_ingest

            structured_dir = str(resolve_service_structured_dir(service_id))
            logger.info("Auto-seeding guidelines_%s from %s via AT adapter.", service_id, structured_dir)
            at_chunk_and_ingest(
                structured_dir=structured_dir,
                db_path=str(CHROMA_DB_DIR),
                collection_name=collection_name,
            )
            logger.info("guidelines_%s auto-seed complete.", service_id)
        except Exception:
            logger.exception("Failed to seed guidelines_%s via AT adapter.", service_id)
    else:
        logger.info(
            "No adapter pipeline for service '%s' — skipping guideline seed.",
            service_id,
        )
```

- [ ] **Step 5: Run all new tests to verify they pass**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/pipeline/test_actas_chunker_collection_name.py tests/python/services/test_retriever_reset.py tests/python/services/test_settings_invalidation.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run existing seed and isolation tests to verify no regressions**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/test_auto_seed.py tests/python/services/test_isolation.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/python/pipeline/actas/chunker.py src/python/seed.py tests/python/pipeline/test_actas_chunker_collection_name.py
git commit -m "fix: make ACTAS chunker accept collection_name, wire AT adapter into seed"
```

---

### Task 7: Remove hardcoded ACTAS reference from quiz prompt

**Files:**
- Modify: `src/python/quiz/agent.py:51`

- [ ] **Step 1: Fix the prompt example**

In `src/python/quiz/agent.py`, line 51, change:

```python
  "source_citation": "e.g. ACTAS CMG 14.1",
```

to:

```python
  "source_citation": f"e.g. {svc.short_name} CMG 14.1",
```

Then add `short_name` as a computed property to the Service dataclass in `src/python/services/registry.py`. Add after line 44:

```python
    @property
    def short_name(self) -> str:
        """Short uppercase identifier for citations (e.g. 'ACTAS', 'AT')."""
        return self.id.upper()
```

Note: `@property` works on frozen dataclasses — `frozen=True` only prevents setting instance attributes, not defining properties.

- [ ] **Step 2: Verify no regressions in quiz tests**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/quiz/ -v -k "not known_failure"`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add src/python/quiz/agent.py src/python/services/registry.py
git commit -m "fix: use dynamic service name in quiz prompt instead of hardcoded ACTAS"
```

---

### Task 8: End-to-end verification — run full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run all Python tests**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && PYTHONPATH=src/python pytest tests/python/ tests/quiz/ -v --tb=short 2>&1 | tail -40`
Expected: All tests pass or match pre-existing failures in `KNOWN_TEST_FAILURES.md`

- [ ] **Step 2: Check for any other hardcoded ACTAS references that should be service-aware**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && grep -rn "guidelines_actas\|cmg_guidelines\|paramedic_notes" src/python/ --include="*.py" | grep -v "__pycache__" | grep -v "test_" | grep -v ".pyc"`

Verify that the only remaining hardcoded `"guidelines_actas"` references are:
- `actas/chunker.py` — the default parameter value (correct, backwards-compatible)
- `seed.py` — legacy migration map `_LEGACY_COLLECTION_MAP` (correct, handles old data)
- `settings/router.py` — if any remain in legacy fallback code (acceptable)

If any unexpected hardcodes remain, flag them for the user.

- [ ] **Step 3: Manual smoke test (optional, for user)**

1. Start the app with ACTAS active
2. Start a quiz — confirm it uses ACTAS content
3. Go to Settings, switch to Ambulance Tasmania
4. Start a new quiz — confirm it uses ONLY AT content, zero ACTAS references
5. Switch back to ACTAS — confirm it uses ONLY ACTAS content

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] Retriever singleton reset — Task 1
- [x] Quiz router singleton reset — Task 2
- [x] Search router singleton reset — Task 2
- [x] Settings save triggers reset — Task 3
- [x] vector_store_status service-aware — Task 4
- [x] clear_vector_store service-aware — Task 5
- [x] ACTAS chunker accepts collection_name — Task 6
- [x] AT adapter wired into seed — Task 6
- [x] Quiz prompt dynamic service name — Task 7

**2. Placeholder scan:** No TBD, TODO, or placeholder steps found.

**3. Type consistency:**
- `reset_retriever()` takes no args, returns None — consistent across all callers
- `SaveSettingsRequest.active_service` is `str` — consistent with `_read_active_service_id()` returning `str | None`
- `collection_name` parameter is `str` — consistent between `actas/chunker.py`, `at/chunker.py`, and `seed.py`
- `Service.short_name` property returns `str` — consistent with f-string usage in `agent.py`
