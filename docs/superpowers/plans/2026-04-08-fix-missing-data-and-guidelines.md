# Fix Missing Personal Docs/Notes Data and Personal Build Guidelines

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure personal notes, CPD docs, and reference docs appear as chunks in all run modes, and that the personal build shows guidelines correctly.

**Architecture:** Two root causes — (1) the `paramedic_notes` ChromaDB collection is empty because the ingestion pipelines were never run, and there's no auto-seed for non-CMG data; (2) the personal build config is missing `data/cmgs/structured` in its bundled resources, so the guidelines router finds no JSON files to load. Fixes target `seed.py` (auto-seed), `settings/router.py` (pipeline rerun), `electron-builder.personal.yml` (bundled resources), and `scripts/package-backend.sh` (pre-built ChromaDB).

**Tech Stack:** Python (ChromaDB, FastAPI), TypeScript/React (Settings UI), electron-builder (YAML config), Bash (packaging)

---

## Root Cause Analysis

### Issue 1: Personal notes, CPD docs, and ref docs don't appear

**Evidence:**
- `paramedic_notes` ChromaDB collection has **0 chunks** (confirmed by direct query)
- Structured data exists but was never ingested:
  - `data/notes_md/cleaned/`: **380** cleaned notability note markdown files
  - `data/personal_docs/structured/REFdocs/`: **2** REFdoc files
  - `data/personal_docs/structured/CPDdocs/`: **9** CPDdoc files
- `seed.py` only auto-seeds `cmg_guidelines` collection — no equivalent for `paramedic_notes`
- `POST /settings/pipeline/rerun` runs `python3 -m pipeline.run ingest` (notability notes only) — does **not** run the personal docs pipeline
- Personal build's pre-built ChromaDB at `build/resources/data/chroma_db` only has CMG data

**Root cause chain:** Processed data exists on disk → but was never ingested into ChromaDB → and there's no auto-seed mechanism for non-CMG data → so `paramedic_notes` collection stays empty in all modes.

### Issue 2: 0 guidelines in personal build only

**Evidence:**
- `electron-builder.yml` (release build) bundles `data/cmgs/structured` → guidelines router finds 167 JSON files → shows "167 guidelines"
- `electron-builder.personal.yml` (personal build) is **missing** `data/cmgs/structured` → guidelines router finds no JSON files → shows "0 guidelines"
- Both builds bundle a ChromaDB with 877 CMG chunks (search works), but guidelines page reads from the raw JSON files, not ChromaDB

**Root cause:** Missing `extraResources` entry in `electron-builder.personal.yml`.

---

## File Structure

| File | Change | Responsibility |
|------|--------|---------------|
| `electron-builder.personal.yml` | Modify | Add `data/cmgs/structured` resource |
| `src/python/seed.py` | Modify | Add auto-seed for `paramedic_notes` collection |
| `src/python/settings/router.py` | Modify | Extend "Re-run Pipeline" to also run personal docs |
| `scripts/package-backend.sh` | Modify | Build complete ChromaDB for personal builds |
| `tests/python/test_auto_seed.py` | Modify | Add tests for personal docs auto-seed |
| `tests/python/test_settings_router.py` | Modify | Add test for extended pipeline rerun |

---

### Task 1: Add CMG structured data to personal build config

**Files:**
- Modify: `electron-builder.personal.yml`

**Why:** The personal build doesn't bundle `data/cmgs/structured`, so the guidelines router has no JSON files to read. This is the sole cause of "0 guidelines" in personal build.

- [ ] **Step 1: Add `data/cmgs/structured` to `electron-builder.personal.yml` extraResources**

In `electron-builder.personal.yml`, add the missing resource block after the existing `data/chroma_db` entry (line 18):

```yaml
  - from: data/cmgs/structured
    to: data/cmgs/structured
    filter:
      - "**/*.json"
```

The complete `extraResources` section should read:

```yaml
extraResources:
  - from: build/resources/backend
    to: backend
    filter:
      - "**/*"
  - from: config/settings.example.json
    to: config/settings.example.json
  - from: build/resources/data/chroma_db
    to: data/chroma_db
    filter:
      - "**/*"
  - from: data/cmgs/structured
    to: data/cmgs/structured
    filter:
      - "**/*.json"
```

- [ ] **Step 2: Verify the config is valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('electron-builder.personal.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add electron-builder.personal.yml
git commit -m "fix: bundle CMG structured data in personal build"
```

---

### Task 2: Add auto-seed for paramedic_notes collection

**Files:**
- Modify: `src/python/seed.py`
- Modify: `tests/python/test_auto_seed.py`

**Why:** The seed logic only handles CMGs. Personal docs and notability notes are never auto-ingested, so `paramedic_notes` stays empty in dev mode and fresh installs.

- [ ] **Step 1: Write failing test for personal docs auto-seed**

Add to `tests/python/test_auto_seed.py`:

```python
def test_seed_paramedic_notes_runs_notability_pipeline_when_empty(tmp_path, monkeypatch):
    """Auto-seed should run notability notes ingestion when paramedic_notes is empty."""
    import seed as seed_mod

    in_memory = chromadb.Client()

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.CLEANED_NOTES_DIR", tmp_path / "notes_md" / "cleaned")
    monkeypatch.setattr("seed.PERSONAL_STRUCTURED_DIR", tmp_path / "personal_docs" / "structured")

    called = []

    def mock_run_ingest(db_path):
        called.append("notability")
        # Simulate adding chunks so count check passes
        col = in_memory.get_or_create_collection("paramedic_notes")
        col.add(ids=["test_note"], documents=["test content"], metadatas=[{"source_type": "notability_note"}])

    def mock_run_personal_docs(db_path):
        called.append("personal_docs")

    monkeypatch.setattr("seed.chromadb.PersistentClient", return_value=in_memory)
    monkeypatch.setattr("seed._run_notability_notes_ingest", mock_run_ingest)
    monkeypatch.setattr("seed._run_personal_docs_ingest", mock_run_personal_docs)

    seed_mod._seed_paramedic_notes_if_needed()

    assert "notability" in called
    assert "personal_docs" in called


def test_seed_paramedic_notes_skips_when_collection_has_data(tmp_path, monkeypatch):
    """Auto-seed should skip if paramedic_notes already has data."""
    import seed as seed_mod

    in_memory = chromadb.Client()
    col = in_memory.get_or_create_collection("paramedic_notes")
    col.add(ids=["existing"], documents=["test"], metadatas=[{"source_type": "ref_doc"}])

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.chromadb.PersistentClient", return_value=in_memory)

    called = []
    monkeypatch.setattr("seed._run_notability_notes_ingest", lambda db_path: called.append("notability"))

    seed_mod._seed_paramedic_notes_if_needed()

    assert called == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/python && python3 -m pytest ../../tests/python/test_auto_seed.py -v -k "paramedic_notes"`

Expected: FAIL — `_seed_paramedic_notes_if_needed` does not exist in `seed.py`

- [ ] **Step 3: Implement auto-seed for paramedic_notes in `seed.py`**

Add the following to `src/python/seed.py`, after the existing `_seed_cmg_index` function and before the module ends. Also update the `seed_user_data` function and imports.

At the top of `seed.py`, add to the imports from `paths`:

```python
from paths import (
    BUNDLED_CHROMA_DB_DIR,
    CHROMA_DB_DIR,
    CLEANED_NOTES_DIR,
    CMG_STRUCTURED_DIR,
    CONFIG_DIR,
    EXAMPLE_SETTINGS_PATH,
    LOGS_DIR,
    PERSONAL_STRUCTURED_DIR,
    SETTINGS_PATH,
)
```

Update `seed_user_data()` to call the new seed function:

```python
def seed_user_data() -> None:
    _ensure_settings()
    _ensure_dirs()
    _start_cmg_seed_if_needed()
    _start_paramedic_notes_seed_if_needed()
```

Add the new functions after `_seed_cmg_index`:

```python
def _start_paramedic_notes_seed_if_needed() -> None:
    if _paramedic_notes_collection_has_data():
        return
    _run_notability_notes_ingest(CHROMA_DB_DIR)
    _run_personal_docs_ingest(CHROMA_DB_DIR)


def _paramedic_notes_collection_has_data() -> bool:
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_or_create_collection("paramedic_notes")
        return collection.count() > 0
    except Exception:
        return False


def _run_notability_notes_ingest(db_path: Path) -> None:
    if not CLEANED_NOTES_DIR.exists():
        return
    md_files = list(CLEANED_NOTES_DIR.rglob("*.md"))
    if not md_files:
        return
    logger.info(f"Auto-seeding notability notes from {CLEANED_NOTES_DIR} ({len(md_files)} files)")
    try:
        from pipeline.chunker import chunk_and_ingest

        for md_path in md_files:
            try:
                chunk_and_ingest(md_path, db_path)
            except Exception:
                logger.warning(f"Failed to ingest {md_path.name}")
    except Exception:
        logger.exception("Notability notes auto-seed failed")


def _run_personal_docs_ingest(db_path: Path) -> None:
    if not PERSONAL_STRUCTURED_DIR.exists():
        return
    try:
        from pipeline.personal_docs.chunker import chunk_and_ingest_directory

        result = chunk_and_ingest_directory(PERSONAL_STRUCTURED_DIR, db_path)
        logger.info(
            f"Personal docs auto-seed: {result['processed']} files, {result['total_chunks']} chunks"
        )
    except Exception:
        logger.exception("Personal docs auto-seed failed")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/python && python3 -m pytest ../../tests/python/test_auto_seed.py -v -k "paramedic_notes"`

Expected: Both tests PASS

- [ ] **Step 5: Run full auto-seed test suite to verify no regressions**

Run: `cd src/python && python3 -m pytest ../../tests/python/test_auto_seed.py -v`

Expected: All tests PASS (4 total — 2 existing CMG tests + 2 new paramedic_notes tests)

- [ ] **Step 6: Commit**

```bash
git add src/python/seed.py tests/python/test_auto_seed.py
git commit -m "feat: add auto-seed for personal docs and notability notes"
```

---

### Task 3: Extend "Re-run Pipeline" to also run personal docs ingestion

**Files:**
- Modify: `src/python/settings/router.py`
- Modify: `tests/python/test_settings_router.py`

**Why:** The "Re-run Pipeline" button currently only runs the notability notes pipeline. It should also run the personal docs (REFdocs/CPDdocs) pipeline so users can re-ingest all personal data from the UI.

- [ ] **Step 1: Write failing test**

Add to `tests/python/test_settings_router.py`:

```python
def test_rerun_pipeline_starts_both_pipelines(monkeypatch):
    """Re-run Pipeline should trigger both notability notes and personal docs ingestion."""
    commands_run: list[list[str]] = []

    def mock_run(cmd, **kwargs):
        commands_run.append(cmd)

    monkeypatch.setattr(settings_router.subprocess, "run", mock_run)
    monkeypatch.setattr(settings_router, "invalidate_guideline_cache", lambda: None)
    monkeypatch.setattr(settings_router, "invalidate_medication_cache", lambda: None)

    response = client.post("/settings/pipeline/rerun")
    assert response.status_code == 200
    assert response.json()["status"] == "started"

    # Wait for background thread to finish
    import time
    time.sleep(1)

    # Should have run both pipelines
    assert len(commands_run) >= 2
    cmd_strs = [" ".join(c) for c in commands_run]
    assert any("pipeline.run" in c for c in cmd_strs), f"Notability pipeline not found in {cmd_strs}"
    assert any("pipeline.personal_docs.run" in c for c in cmd_strs), f"Personal docs pipeline not found in {cmd_strs}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/python && python3 -m pytest ../../tests/python/test_settings_router.py::test_rerun_pipeline_starts_both_pipelines -v`

Expected: FAIL — only the notability pipeline command is run, not the personal docs one

- [ ] **Step 3: Implement the fix**

In `src/python/settings/router.py`, replace the `_run_pipeline_ingest_in_background` function (lines 35-43):

```python
def _run_pipeline_ingest_in_background() -> None:
    try:
        subprocess.run(
            ["python3", "-m", "pipeline.run", "ingest"],
            cwd=str(Path(__file__).resolve().parent.parent),
            check=False,
        )
        subprocess.run(
            ["python3", "-m", "pipeline.personal_docs.run", "ingest"],
            cwd=str(Path(__file__).resolve().parent.parent),
            check=False,
        )
    finally:
        _invalidate_read_caches()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/python && python3 -m pytest ../../tests/python/test_settings_router.py::test_rerun_pipeline_starts_both_pipelines -v`

Expected: PASS

- [ ] **Step 5: Run full settings router test suite**

Run: `cd src/python && python3 -m pytest ../../tests/python/test_settings_router.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/python/settings/router.py tests/python/test_settings_router.py
git commit -m "feat: extend Re-run Pipeline to also ingest personal docs"
```

---

### Task 4: Update personal build packaging to include complete ChromaDB

**Files:**
- Modify: `scripts/package-backend.sh`

**Why:** The personal build expects a pre-built ChromaDB at `build/resources/data/chroma_db` but only requires it to exist — it doesn't verify it contains personal docs data, nor does it build one with all data types. The pre-built ChromaDB should include CMGs + notability notes + personal docs.

- [ ] **Step 1: Update personal build branch to also run ingestion pipelines**

In `scripts/package-backend.sh`, replace the personal build block (lines 136-143):

```bash
	else
	  echo "--- Personal build: building complete ChromaDB ---"
	  rm -rf "$CHROMA_OUTPUT"
	  mkdir -p "$CHROMA_OUTPUT"
	  PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
from pipeline.cmg.chunker import chunk_and_ingest
chunk_and_ingest(structured_dir='$REPO_ROOT/data/cmgs/structured', db_path='$CHROMA_OUTPUT')
import chromadb
client = chromadb.PersistentClient(path='$CHROMA_OUTPUT')
col = client.get_or_create_collection('cmg_guidelines')
print(f'CMG chunks: {col.count()}')
"
	  # Ingest notability notes if cleaned data exists
	  if [[ -d "$REPO_ROOT/data/notes_md/cleaned" ]] && [[ -n "$(ls -A "$REPO_ROOT/data/notes_md/cleaned")" ]]; then
	    echo "--- Personal build: ingesting notability notes ---"
	    PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
import sys
sys.path.insert(0, '$REPO_ROOT/src/python')
from pathlib import Path
from pipeline.chunker import chunk_and_ingest
from paths import CHROMA_DB_DIR
db_path = Path('$CHROMA_OUTPUT')
cleaned = Path('$REPO_ROOT/data/notes_md/cleaned')
md_files = sorted(cleaned.rglob('*.md'))
print(f'Found {len(md_files)} cleaned notability notes')
count = 0
for md in md_files:
    try:
        chunk_and_ingest(md, db_path)
        count += 1
    except Exception as e:
        print(f'  SKIP: {md.name}: {e}')
import chromadb
client = chromadb.PersistentClient(path=str(db_path))
col = client.get_or_create_collection('paramedic_notes')
print(f'Notability notes ingested: {count} files, total paramedic_notes: {col.count()} chunks')
"
	  fi

	  # Ingest personal docs (REFdocs/CPDdocs) if structured data exists
	  if [[ -d "$REPO_ROOT/data/personal_docs/structured" ]] && [[ -n "$(find "$REPO_ROOT/data/personal_docs/structured" -name '*.md')" ]]; then
	    echo "--- Personal build: ingesting personal docs ---"
	    PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
import sys
sys.path.insert(0, '$REPO_ROOT/src/python')
from pathlib import Path
from pipeline.personal_docs.chunker import chunk_and_ingest_directory
result = chunk_and_ingest_directory(Path('$REPO_ROOT/data/personal_docs/structured'), Path('$CHROMA_OUTPUT'))
print(f'Personal docs: {result[\"processed\"]} files, {result[\"total_chunks\"]} chunks')
"
	  fi

	  echo "--- Personal build: ChromaDB build complete ---"
	  PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
import chromadb
client = chromadb.PersistentClient(path='$CHROMA_OUTPUT')
for col in client.list_collections():
    print(f'  {col.name}: {col.count()} chunks')
"
	fi
```

- [ ] **Step 2: Verify the script syntax**

Run: `bash -n scripts/package-backend.sh`

Expected: No output (valid syntax)

- [ ] **Step 3: Commit**

```bash
git add scripts/package-backend.sh
git commit -m "fix: build complete ChromaDB with all data types for personal build"
```

---

### Task 5: Ingest existing data for dev mode

**Why:** The local dev ChromaDB has 0 paramedic_notes chunks. Running the pipelines now will populate it immediately for `npm run dev`.

- [ ] **Step 1: Ingest notability notes**

Run: `cd src/python && python3 -m pipeline.run ingest`

Expected output showing ingestion of 380 cleaned notes with chunk counts.

- [ ] **Step 2: Ingest personal docs (REFdocs/CPDdocs)**

Run: `cd src/python && python3 -m pipeline.personal_docs.run ingest`

Expected output showing ingestion of 11 structured files (2 REFdocs + 9 CPDdocs) with chunk counts.

- [ ] **Step 3: Verify ChromaDB now has all data**

Run:
```bash
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='data/chroma_db')
for col in client.list_collections():
    print(f'{col.name}: {col.count()} chunks')
"
```

Expected:
```
cmg_guidelines: 877 chunks
paramedic_notes: <N> chunks  (should be > 0)
```

- [ ] **Step 4: Verify in app**

Run: `npm run dev`, navigate to Settings page, confirm chunk counts appear for Reference Documents, CPD Study Documents, and Personal Notes. Navigate to Guidelines page and confirm it shows guidelines count.

---

## Verification Checklist

After all tasks are complete:

- [ ] `npm run dev`: Settings page shows chunk counts for all 4 source types (cmg, ref_doc, cpd_doc, notability_note)
- [ ] `npm run dev`: Guidelines page shows guidelines count (167+)
- [ ] All existing tests pass: `cd src/python && python3 -m pytest ../../tests/python/ -v`
- [ ] `electron-builder.personal.yml` includes `data/cmgs/structured` resource
- [ ] `scripts/package-backend.sh` builds complete ChromaDB for personal builds
