# Rebuild ChromaDB Chunks with Visibility Metadata

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Regenerate the pre-built ChromaDB so that packaged app builds ship with `visibility` metadata on every CMG chunk, enabling the new AP/ICP content filtering.

**Architecture:** The CMG chunker (`pipeline/cmg/chunker.py`) already produces dual-version chunks with `visibility` metadata after the ICP fix. The problem is the bundled DB at `build/resources/data/chroma_db/` is stale — it was either never built or lacks the new field. We need to wipe the existing user DB and the bundled DB, re-run the chunker against the structured CMG data, copy the result into the build resources directory, and verify every chunk has the `visibility` field.

**Tech Stack:** Python 3.10+, ChromaDB PersistentClient, pytest

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `data/chroma_db/` | Delete & regenerate | User-local ChromaDB (gitignored) |
| `build/resources/data/chroma_db/` | Create from user DB | Pre-built DB bundled by electron-builder |
| `tests/python/test_bundled_chromadb_visibility.py` | Create | Verify bundled DB has visibility on all chunks |

---

### Task 1: Wipe Existing ChromaDB Data

**Files:**
- Delete: `data/chroma_db/` (user-local)
- Delete: `build/resources/data/chroma_db/` (bundled, may not exist)

- [ ] **Step 1: Delete user-local ChromaDB**

This removes the stale DB so the chunker produces a clean one with `visibility` metadata.

```bash
rm -rf data/chroma_db/
```

- [ ] **Step 2: Delete bundled ChromaDB if it exists**

```bash
rm -rf build/resources/data/chroma_db/
```

- [ ] **Step 3: Verify both directories are gone**

```bash
ls data/chroma_db/ 2>&1 || true
ls build/resources/data/chroma_db/ 2>&1 || true
```

Expected: both report "No such file or directory"

---

### Task 2: Re-run CMG Chunker

**Files:**
- Creates: `data/chroma_db/` (fresh)

- [ ] **Step 1: Run the chunker against structured CMG data**

From the project root:

```bash
PYTHONPATH=src/python python3 -c "
from pipeline.cmg.chunker import chunk_and_ingest
from paths import resolve_cmg_structured_dir
result = chunk_and_ingest(structured_dir=str(resolve_cmg_structured_dir()))
print(f'Ingested {result} chunks')
"
```

Expected: output like `Ingested NNN chunks into ChromaDB.` with N > 0.

- [ ] **Step 2: Verify chunk count and visibility coverage**

```bash
PYTHONPATH=src/python python3 -c "
import chromadb
from paths import CHROMA_DB_DIR

client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
col = client.get_or_create_collection('cmg_guidelines')
total = col.count()
print(f'Total chunks: {total}')

# Get all metadata
all_data = col.get(include=['metadatas'])
has_visibility = sum(1 for m in all_data['metadatas'] if 'visibility' in m)
missing_visibility = total - has_visibility
print(f'Chunks with visibility: {has_visibility}')
print(f'Chunks missing visibility: {missing_visibility}')

# Breakdown by visibility value
from collections import Counter
vis_counts = Counter(m.get('visibility', 'MISSING') for m in all_data['metadatas'])
for vis, count in sorted(vis_counts.items()):
    print(f'  {vis}: {count}')
"
```

Expected: `Chunks missing visibility: 0`. Should see `both`, possibly `icp` and `ap` depending on CMG content.

- [ ] **Step 3: Commit is not needed here — this is gitignored data**

`data/chroma_db/` is gitignored and `build/resources/data/chroma_db/` is not committed. No commit.

---

### Task 3: Copy Fresh DB to Build Resources

**Files:**
- Creates: `build/resources/data/chroma_db/`

- [ ] **Step 1: Create build resources directory and copy**

```bash
mkdir -p build/resources/data/
cp -r data/chroma_db/ build/resources/data/chroma_db/
```

- [ ] **Step 2: Verify the copy**

```bash
ls build/resources/data/chroma_db/
```

Expected: ChromaDB files present (e.g. `chroma.sqlite3`, UUID directories).

- [ ] **Step 3: Verify bundled DB also has visibility metadata**

```bash
PYTHONPATH=src/python python3 -c "
import chromadb

client = chromadb.PersistentClient(path='build/resources/data/chroma_db')
col = client.get_or_create_collection('cmg_guidelines')
total = col.count()
all_data = col.get(include=['metadatas'])
has_visibility = sum(1 for m in all_data['metadatas'] if 'visibility' in m)
print(f'Bundled DB chunks: {total}, with visibility: {has_visibility}')
assert has_visibility == total, f'FAIL: {total - has_visibility} chunks missing visibility'
print('PASS: All bundled chunks have visibility metadata')
"
```

Expected: `PASS: All bundled chunks have visibility metadata`

---

### Task 4: Write Verification Test

**Files:**
- Create: `tests/python/test_bundled_chromadb_visibility.py`

- [ ] **Step 1: Write the test**

```python
"""Verify the bundled ChromaDB ships with visibility metadata on every CMG chunk."""

import chromadb
import pytest

from paths import CHROMA_DB_DIR


@pytest.fixture
def _cmg_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return client.get_or_create_collection("cmg_guidelines")


def test_all_cmg_chunks_have_visibility(_cmg_collection):
    """Every CMG chunk must carry a 'visibility' field (both|icp|ap)."""
    col = _cmg_collection
    if col.count() == 0:
        pytest.skip("No CMG chunks in local ChromaDB")

    all_data = col.get(include=["metadatas"])
    missing = [
        (i, mid)
        for i, (mid, meta) in enumerate(
            zip(all_data["ids"], all_data["metadatas"])
        )
        if "visibility" not in meta
    ]
    assert missing == [], (
        f"{len(missing)} chunks missing 'visibility' metadata. "
        f"First 5: {missing[:5]}. Re-run the CMG chunker to regenerate."
    )


def test_visibility_values_are_valid(_cmg_collection):
    """Visibility values must be one of: both, icp, ap."""
    col = _cmg_collection
    if col.count() == 0:
        pytest.skip("No CMG chunks in local ChromaDB")

    all_data = col.get(include=["metadatas"])
    valid = {"both", "icp", "ap"}
    invalid = [
        (i, mid, meta.get("visibility"))
        for i, (mid, meta) in enumerate(
            zip(all_data["ids"], all_data["metadatas"])
        )
        if meta.get("visibility") not in valid
    ]
    assert invalid == [], (
        f"{len(invalid)} chunks have invalid visibility values. "
        f"First 5: {invalid[:5]}"
    )
```

- [ ] **Step 2: Run the test**

```bash
PYTHONPATH=src/python pytest tests/python/test_bundled_chromadb_visibility.py -v
```

Expected: Both tests PASS (assuming Task 2 was completed successfully).

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_bundled_chromadb_visibility.py
git commit -m "test: add visibility metadata verification for ChromaDB chunks"
```

---

## Post-Rebuild Verification Checklist

After all tasks complete:

1. `data/chroma_db/` exists and has CMG chunks with `visibility` metadata
2. `build/resources/data/chroma_db/` is a copy of the above
3. The verification test passes
4. `electron-builder` will now bundle the updated DB on next build

## For Existing Users

No code change needed — when an existing user clicks **"Rebuild Index"** in Settings, it calls `POST /settings/cmg-rebuild` which runs `chunk_and_ingest()` fresh against the structured CMG data, producing chunks with `visibility` metadata.

For new users on the next app release, the packaged app will copy the pre-built bundled DB on first launch via `seed.py`, already containing `visibility` metadata.
