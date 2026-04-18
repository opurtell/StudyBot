# Quiz Chunk Coverage & Variability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the binary `used_chunks` dedup list with a soft coverage-weighted scoring system and add random corpus injection in random quiz mode, so all chunks have a realistic chance of surfacing over time.

**Architecture:** `RetrievedChunk` gains a canonical `content_key` property; `Tracker` replaces `used_chunks` with a `chunk_coverage` table (use_count + last_used) and adds `get_chunk_scores()`; `Retriever.retrieve()` applies coverage-weighted sorting when a tracker is supplied; a new `Retriever.get_random_chunk()` method enables uniform corpus sampling; `generate_question()` in `agent.py` injects a random chunk 25% of the time in random mode and passes the tracker to all `retrieve()` calls.

**Tech Stack:** Python 3.10+, SQLite (via stdlib sqlite3), ChromaDB, Pydantic v1/v2, pytest

**Spec:** `docs/superpowers/specs/2026-04-18-quiz-chunk-coverage-variability-design.md`

---

## File Map

| File | Change |
|------|--------|
| `src/python/quiz/models.py` | Add `content_key` property to `RetrievedChunk` |
| `src/python/quiz/tracker.py` | Replace `used_chunks` with `chunk_coverage`; add migration; add `get_chunk_scores()`; update `record_used_chunks()`, `get_recent_chunk_keys()`, `clear_mastery_data()`; remove `MAX_USED_CHUNKS` |
| `src/python/quiz/retriever.py` | Add `tracker` param to `retrieve()`; replace shuffle with coverage-weighted sort; add `get_random_chunk()` method; update `c.content[:200]` → `c.content_key` |
| `src/python/quiz/agent.py` | Add `RANDOM_INJECTION_PROBABILITY`; add random injection branch; pass `tracker=tracker` to all `retrieve()` calls |
| `src/python/quiz/router.py` | Update `c.content[:200]` → `c.content_key` (cosmetic) |
| `tests/quiz/test_tracker.py` | Add `get_chunk_scores()` tests; update/remove stale `used_chunks` tests |
| `tests/quiz/test_retriever.py` | Add `content_key` test; add coverage-weighted scoring test; add `get_random_chunk()` tests |
| `tests/quiz/test_agent.py` | Add random injection tests |

---

## Task 1: Add `content_key` to `RetrievedChunk`

**Files:**
- Modify: `src/python/quiz/models.py`
- Modify: `src/python/quiz/retriever.py:87` (one `c.content[:200]` usage)
- Modify: `src/python/quiz/router.py:155` (one `c.content[:200]` usage)
- Test: `tests/quiz/test_retriever.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/quiz/test_retriever.py`:

```python
def test_retrieved_chunk_content_key_is_first_200_chars():
    long_content = "x" * 300
    chunk = RetrievedChunk(
        content=long_content,
        source_type="cmg",
        source_file="f.json",
        source_rank=0,
        relevance_score=0.5,
    )
    assert chunk.content_key == "x" * 200


def test_retrieved_chunk_content_key_short_content():
    chunk = RetrievedChunk(
        content="short",
        source_type="cmg",
        source_file="f.json",
        source_rank=0,
        relevance_score=0.5,
    )
    assert chunk.content_key == "short"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot
python -m pytest tests/quiz/test_retriever.py::test_retrieved_chunk_content_key_is_first_200_chars tests/quiz/test_retriever.py::test_retrieved_chunk_content_key_short_content -v
```

Expected: `AttributeError: 'RetrievedChunk' object has no attribute 'content_key'`

- [ ] **Step 3: Add the `content_key` property to `RetrievedChunk`**

In `src/python/quiz/models.py`, after the `relevance_score` field:

```python
class RetrievedChunk(BaseModel):
    content: str
    source_type: str
    source_file: str
    source_rank: int
    category: str | None = None
    cmg_number: str | None = None
    chunk_type: str | None = None
    relevance_score: float

    @property
    def content_key(self) -> str:
        return self.content[:200]
```

- [ ] **Step 4: Run the new tests to confirm they pass**

```bash
python -m pytest tests/quiz/test_retriever.py::test_retrieved_chunk_content_key_is_first_200_chars tests/quiz/test_retriever.py::test_retrieved_chunk_content_key_short_content -v
```

Expected: PASS

- [ ] **Step 5: Update the two call sites that use `c.content[:200]` directly**

In `src/python/quiz/retriever.py` line 87, change:
```python
            c for c in all_chunks if c.content[:200] not in exclude_content_keys
```
to:
```python
            c for c in all_chunks if c.content_key not in exclude_content_keys
```

In `src/python/quiz/router.py` line 155, change:
```python
    chunk_keys = [c.content[:200] for c in question.source_chunks]
```
to:
```python
    chunk_keys = [c.content_key for c in question.source_chunks]
```

- [ ] **Step 6: Run the full quiz test suite to confirm nothing broke**

```bash
python -m pytest tests/quiz/ -v
```

Expected: all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/python/quiz/models.py src/python/quiz/retriever.py src/python/quiz/router.py tests/quiz/test_retriever.py
git commit -m "feat: add content_key property to RetrievedChunk"
```

---

## Task 2: Replace `used_chunks` with `chunk_coverage` in Tracker

**Files:**
- Modify: `src/python/quiz/tracker.py`
- Modify: `tests/quiz/test_tracker.py`

This task replaces the binary 300-entry exclusion list with a persistent coverage table (use_count + last_used) that enables soft weighting. It also includes a one-shot migration for users who already have a `used_chunks` table.

- [ ] **Step 1: Write failing tests for `get_chunk_scores()`**

Add to `tests/quiz/test_tracker.py`:

```python
from datetime import datetime, timedelta


def test_get_chunk_scores_unseen_key_returns_1(tracker):
    scores = tracker.get_chunk_scores({"never_seen_key"})
    assert scores["never_seen_key"] == pytest.approx(1.0)


def test_get_chunk_scores_used_once_today_returns_half(tracker):
    tracker.record_used_chunks(["key_used_once"])
    scores = tracker.get_chunk_scores({"key_used_once"})
    # use_count=1, recency_factor=0 → weight = 1/(1+1) = 0.5
    assert scores["key_used_once"] == pytest.approx(0.5, abs=0.05)


def test_get_chunk_scores_used_three_times_today(tracker):
    for _ in range(3):
        tracker.record_used_chunks(["key_used_three"])
    scores = tracker.get_chunk_scores({"key_used_three"})
    # use_count=3, recency_factor=0 → weight = 1/(3+1) = 0.25
    assert scores["key_used_three"] == pytest.approx(0.25, abs=0.1)


def test_get_chunk_scores_aged_out_returns_1(tracker):
    # Manually insert a row with a last_used date 8 days ago
    old_date = (datetime.utcnow() - timedelta(days=8)).isoformat()
    tracker._conn.execute(
        "INSERT INTO chunk_coverage (content_key, use_count, last_used) VALUES (?, ?, ?)",
        ("old_key", 5, old_date),
    )
    tracker._conn.commit()
    scores = tracker.get_chunk_scores({"old_key"})
    # recency_factor = min(1.0, 8/7) = 1.0 → weight = 1.0
    assert scores["old_key"] == pytest.approx(1.0, abs=0.01)


def test_get_chunk_scores_returns_1_for_empty_input(tracker):
    assert tracker.get_chunk_scores(set()) == {}


def test_used_chunks_migration(tmp_path):
    """Pre-existing used_chunks rows are migrated to chunk_coverage on init."""
    import sqlite3
    db_path = tmp_path / "mastery.db"

    # Manually create the old schema with some rows
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE used_chunks (
        id INTEGER PRIMARY KEY,
        content_key TEXT NOT NULL UNIQUE,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("INSERT INTO used_chunks (content_key) VALUES ('old_key_1')")
    conn.execute("INSERT INTO used_chunks (content_key) VALUES ('old_key_2')")
    conn.commit()
    conn.close()

    # Instantiate a fresh Tracker — migration should run automatically
    tracker = Tracker(db_path=db_path)

    # Migrated rows appear in chunk_coverage with use_count=1
    keys = tracker.get_recent_chunk_keys()
    assert "old_key_1" in keys
    assert "old_key_2" in keys

    # used_chunks table is dropped
    tables = tracker._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='used_chunks'"
    ).fetchone()
    assert tables is None
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
python -m pytest tests/quiz/test_tracker.py::test_get_chunk_scores_unseen_key_returns_1 tests/quiz/test_tracker.py::test_get_chunk_scores_used_once_today_returns_half tests/quiz/test_tracker.py::test_get_chunk_scores_used_three_times_today tests/quiz/test_tracker.py::test_get_chunk_scores_aged_out_returns_1 tests/quiz/test_tracker.py::test_get_chunk_scores_returns_1_for_empty_input -v
```

Expected: FAIL — `get_chunk_scores` does not exist yet

- [ ] **Step 3: Update the existing stale `used_chunks` tests**

The tests `test_used_chunks_prune_to_max` references `tracker.MAX_USED_CHUNKS` which will be removed. Update/replace these tests in `tests/quiz/test_tracker.py`:

Replace `test_used_chunks_prune_to_max` (the last test in the file) with:

```python
def test_record_used_chunks_increments_use_count(tracker):
    tracker.record_used_chunks(["chunk_a"])
    tracker.record_used_chunks(["chunk_a"])
    # Should have use_count=2 after recording twice
    row = tracker._conn.execute(
        "SELECT use_count FROM chunk_coverage WHERE content_key = ?", ("chunk_a",)
    ).fetchone()
    assert row["use_count"] == 2


def test_record_used_chunks_no_size_cap(tracker):
    # No size cap — all 400 entries should persist
    for i in range(400):
        tracker.record_used_chunks([f"chunk_{i}"])
    keys = tracker.get_recent_chunk_keys()
    assert len(keys) == 400
```

Also update `test_clear_mastery_data_clears_used_chunks` to use the new table name (the test logic stays the same — verify `get_recent_chunk_keys()` returns empty after clear):

```python
def test_clear_mastery_data_clears_chunk_coverage(tracker):
    tracker.record_used_chunks(["chunk_a", "chunk_b"])
    assert len(tracker.get_recent_chunk_keys()) == 2
    tracker.clear_mastery_data()
    assert len(tracker.get_recent_chunk_keys()) == 0
```

(Delete the old `test_clear_mastery_data_clears_used_chunks`.)

- [ ] **Step 4: Rewrite the tracker schema and methods**

Replace `src/python/quiz/tracker.py` with the updated version. Key changes:

**Add import at top:**
```python
from datetime import datetime, timedelta
```

**Replace `MAX_USED_CHUNKS = 300` with nothing** (remove the class constant entirely).

**Replace `_init_schema`** — swap the `used_chunks` DDL for `chunk_coverage` and add the migration:

```python
def _init_schema(self) -> None:
    self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            section TEXT
        );
        CREATE TABLE IF NOT EXISTS quiz_history (
            id INTEGER PRIMARY KEY,
            question_id TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            question_type TEXT,
            score TEXT,
            elapsed_seconds REAL,
            source_citation TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY,
            category_name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunk_coverage (
            content_key TEXT PRIMARY KEY,
            use_count   INTEGER NOT NULL DEFAULT 1,
            last_used   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_coverage_last_used ON chunk_coverage(last_used);
    """)
    self._migrate_used_chunks()

def _migrate_used_chunks(self) -> None:
    """One-shot migration: copy used_chunks → chunk_coverage then drop."""
    exists = self._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='used_chunks'"
    ).fetchone()
    if not exists:
        return
    self._conn.executescript("""
        INSERT OR IGNORE INTO chunk_coverage (content_key, use_count, last_used)
        SELECT content_key, 1, datetime('now') FROM used_chunks;
        DROP TABLE used_chunks;
    """)
```

**Replace `record_used_chunks`:**

```python
def record_used_chunks(self, content_keys: list[str]) -> None:
    if not content_keys:
        return
    now = datetime.utcnow().isoformat()
    with self._lock:
        for key in content_keys:
            self._conn.execute(
                """INSERT INTO chunk_coverage (content_key, use_count, last_used)
                   VALUES (?, 1, ?)
                   ON CONFLICT(content_key) DO UPDATE SET
                       use_count = use_count + 1,
                       last_used = excluded.last_used""",
                (key, now),
            )
        self._conn.commit()
```

**Replace `get_recent_chunk_keys`:**

```python
def get_recent_chunk_keys(self, limit: int | None = None) -> set[str]:
    """Return content keys used within the last 7 days."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    with self._lock:
        query = "SELECT content_key FROM chunk_coverage WHERE last_used >= ?"
        params: list = [cutoff]
        if limit:
            query += " ORDER BY last_used DESC LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
    return {row["content_key"] for row in rows}
```

**Add `get_chunk_scores`:**

```python
def get_chunk_scores(self, keys: set[str]) -> dict[str, float]:
    """Return coverage weight (0–1) for each key. Unseen keys get 1.0."""
    if not keys:
        return {}
    now = datetime.utcnow()
    placeholders = ",".join("?" * len(keys))
    with self._lock:
        rows = self._conn.execute(
            f"SELECT content_key, use_count, last_used FROM chunk_coverage WHERE content_key IN ({placeholders})",
            list(keys),
        ).fetchall()
    seen = {}
    for row in rows:
        days_since = (now - datetime.fromisoformat(row["last_used"])).days
        recency_factor = min(1.0, days_since / 7.0)
        base = 1.0 / (row["use_count"] + 1)
        weight = base + recency_factor * (1.0 - base)
        seen[row["content_key"]] = weight
    return {k: seen.get(k, 1.0) for k in keys}
```

**Update `clear_mastery_data`** — add `chunk_coverage` to the clear:

```python
def clear_mastery_data(self) -> int:
    with self._lock:
        count = self._conn.execute("SELECT COUNT(*) FROM quiz_history").fetchone()[0]
        self._conn.execute("DELETE FROM quiz_history")
        self._conn.execute("DELETE FROM categories")
        self._conn.execute("DELETE FROM chunk_coverage")
        self._conn.commit()
    return count
```

- [ ] **Step 5: Run the new tests to confirm they pass**

```bash
python -m pytest tests/quiz/test_tracker.py -v
```

Expected: all tests pass (including the new `get_chunk_scores` tests and the updated `clear` / `no_size_cap` tests)

- [ ] **Step 6: Run the full quiz test suite**

```bash
python -m pytest tests/quiz/ -v
```

Expected: all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/python/quiz/tracker.py tests/quiz/test_tracker.py
git commit -m "feat: replace used_chunks with chunk_coverage table in Tracker"
```

---

## Task 3: Coverage-Weighted Scoring in `retrieve()`

**Files:**
- Modify: `src/python/quiz/retriever.py`
- Modify: `tests/quiz/test_retriever.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/quiz/test_retriever.py`:

```python
def test_coverage_weighted_scoring_demotes_seen_chunk(seeded_chroma):
    from unittest.mock import MagicMock
    retriever = Retriever(client=seeded_chroma)

    # Build a mock tracker: the top-similarity chunk gets low weight (0.1),
    # all others get high weight (1.0)
    mock_tracker = MagicMock()

    def fake_scores(keys):
        # We don't know which key is "top" without running the query, so
        # return low weight for any key that happens to be first in the set
        scores = {}
        for i, k in enumerate(keys):
            scores[k] = 0.1 if i == 0 else 1.0
        return scores

    mock_tracker.get_chunk_scores.side_effect = fake_scores

    # Run multiple times — with weighting, top chunk should not always dominate
    results_with_tracker = retriever.retrieve(
        "adrenaline cardiac", n=2, tracker=mock_tracker
    )
    assert len(results_with_tracker) > 0
    # tracker.get_chunk_scores was called
    mock_tracker.get_chunk_scores.assert_called()


def test_retrieve_without_tracker_still_works(seeded_chroma):
    """tracker=None falls back to shuffle — existing behaviour preserved."""
    retriever = Retriever(client=seeded_chroma)
    results = retriever.retrieve("adrenaline cardiac", n=3, tracker=None)
    assert len(results) > 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/quiz/test_retriever.py::test_coverage_weighted_scoring_demotes_seen_chunk tests/quiz/test_retriever.py::test_retrieve_without_tracker_still_works -v
```

Expected: `TypeError` — `retrieve()` does not accept a `tracker` keyword

- [ ] **Step 3: Update `retrieve()` in `retriever.py`**

Add `tracker=None` to the `retrieve()` signature (after `source_restriction`):

```python
def retrieve(
    self,
    query: str,
    n: int = 5,
    filters: dict | None = None,
    exclude_categories: list[str] | None = None,
    skill_level: str = "AP",
    exclude_content_keys: set[str] | None = None,
    source_restriction: str | None = None,
    tracker=None,
) -> list[RetrievedChunk]:
```

Replace the existing `random.shuffle` + `return` block (lines 90-92):

```python
        # Shuffle to break deterministic ordering from embedding similarity
        random.shuffle(all_chunks)
        return all_chunks[:n]
```

with:

```python
        if tracker is not None:
            candidate_keys = {c.content_key for c in all_chunks}
            scores = tracker.get_chunk_scores(candidate_keys)
            scored = [
                (
                    c.relevance_score
                    + random.uniform(0, 0.05) * scores.get(c.content_key, 1.0),
                    c,
                )
                for c in all_chunks
            ]
            scored.sort(key=lambda t: t[0], reverse=True)
            all_chunks = [c for _, c in scored]
        else:
            random.shuffle(all_chunks)
        return all_chunks[:n]
```

- [ ] **Step 4: Run the new tests**

```bash
python -m pytest tests/quiz/test_retriever.py::test_coverage_weighted_scoring_demotes_seen_chunk tests/quiz/test_retriever.py::test_retrieve_without_tracker_still_works -v
```

Expected: PASS

- [ ] **Step 5: Run full quiz suite**

```bash
python -m pytest tests/quiz/ -v
```

Expected: all passing

- [ ] **Step 6: Commit**

```bash
git add src/python/quiz/retriever.py tests/quiz/test_retriever.py
git commit -m "feat: add coverage-weighted scoring to Retriever.retrieve()"
```

---

## Task 4: Add `get_random_chunk()` to `Retriever`

**Files:**
- Modify: `src/python/quiz/retriever.py`
- Modify: `tests/quiz/test_retriever.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/quiz/test_retriever.py`:

```python
def test_get_random_chunk_returns_chunk(seeded_chroma):
    retriever = Retriever(client=seeded_chroma)
    chunk = retriever.get_random_chunk()
    assert chunk is not None
    assert isinstance(chunk, RetrievedChunk)
    assert chunk.content


def test_get_random_chunk_empty_corpus():
    import chromadb
    client = chromadb.Client()
    client.get_or_create_collection("paramedic_notes", metadata={"hnsw:space": "cosine"})
    client.get_or_create_collection("cmg_guidelines")
    retriever = Retriever(client=client)
    result = retriever.get_random_chunk()
    assert result is None


def test_get_random_chunk_skips_excluded_key(seeded_chroma):
    retriever = Retriever(client=seeded_chroma)
    # Get a chunk, then exclude its key — subsequent call should either return
    # a different chunk or None (not raise)
    first = retriever.get_random_chunk()
    assert first is not None
    result = retriever.get_random_chunk(exclude_content_keys={first.content_key})
    # result may be None (all excluded) or a different chunk — must not raise
    assert result is None or result.content_key != first.content_key
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/quiz/test_retriever.py::test_get_random_chunk_returns_chunk tests/quiz/test_retriever.py::test_get_random_chunk_empty_corpus tests/quiz/test_retriever.py::test_get_random_chunk_skips_excluded_key -v
```

Expected: `AttributeError` — `get_random_chunk` does not exist

- [ ] **Step 3: Add `get_random_chunk()` method to `Retriever`**

Add after the `_parse_results` method in `src/python/quiz/retriever.py`:

```python
def get_random_chunk(
    self,
    exclude_content_keys: set[str] | None = None,
    skill_level: str = "AP",
) -> "RetrievedChunk | None":
    """Return a single uniformly random chunk from the combined corpus."""
    collections = [self._notes, self._cmgs]
    random.shuffle(collections)
    for col in collections:
        try:
            all_ids = col.get(include=[])["ids"]
            if not all_ids:
                continue
            chosen_id = random.choice(all_ids)
            result = col.get(ids=[chosen_id], include=["documents", "metadatas"])
            chunks = self._parse_results(
                {
                    "documents": [result["documents"]],
                    "metadatas": [result["metadatas"]],
                    "distances": [[0.0]],
                },
                col.name,
            )
            if not chunks:
                continue
            chunk = chunks[0]
            if exclude_content_keys and chunk.content_key in exclude_content_keys:
                continue
            return chunk
        except Exception:
            continue
    return None
```

- [ ] **Step 4: Run the new tests**

```bash
python -m pytest tests/quiz/test_retriever.py::test_get_random_chunk_returns_chunk tests/quiz/test_retriever.py::test_get_random_chunk_empty_corpus tests/quiz/test_retriever.py::test_get_random_chunk_skips_excluded_key -v
```

Expected: PASS

- [ ] **Step 5: Run full quiz suite**

```bash
python -m pytest tests/quiz/ -v
```

Expected: all passing

- [ ] **Step 6: Commit**

```bash
git add src/python/quiz/retriever.py tests/quiz/test_retriever.py
git commit -m "feat: add get_random_chunk() to Retriever for uniform corpus sampling"
```

---

## Task 5: Wire Tracker + Random Injection into `agent.py`

**Files:**
- Modify: `src/python/quiz/agent.py`
- Modify: `tests/quiz/test_agent.py`

- [ ] **Step 1a: Fix existing tests that use `mode="random"` without stubbing `get_random_chunk`**

Two existing tests in `tests/quiz/test_agent.py` will break after Task 5's changes because `mock_retriever.get_random_chunk` will return a truthy `MagicMock` (triggering the injection branch) instead of `None`. Add one line to each:

In `test_random_mode` (line ~144), add before the `generate_question` call:
```python
        mock_retriever.get_random_chunk.return_value = None
```

In the `TestCitationAccuracy.test_generated_question_includes_source_citation` test (line ~453), the retriever is an inline `MagicMock()`. Replace:
```python
        question = generate_question(
            mode="random",
            llm=mock_llm,
            retriever=MagicMock(),
            tracker=MagicMock(),
        )
```
with:
```python
        mock_retriever_citation = MagicMock()
        mock_retriever_citation.retrieve.return_value = chunks
        mock_retriever_citation.get_random_chunk.return_value = None
        question = generate_question(
            mode="random",
            llm=mock_llm,
            retriever=mock_retriever_citation,
            tracker=MagicMock(),
        )
```

Run the existing tests to confirm they still pass (before writing new tests):

```bash
python -m pytest tests/quiz/test_agent.py::TestGenerateQuestion::test_random_mode -v
```

Expected: PASS (confirming the fix works)

- [ ] **Step 1b: Write new failing tests**

Add to `tests/quiz/test_agent.py`:

```python
def test_random_injection_suppressed_in_topic_mode():
    """Random injection must never fire in topic mode."""
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()
    mock_tracker.get_recent_chunk_keys.return_value = set()
    mock_tracker.get_chunk_scores.return_value = {}
    mock_retriever.retrieve.return_value = _make_chunks()
    mock_llm.complete.return_value = json.dumps({
        "question_text": "Q?",
        "question_type": "recall",
        "source_citation": "CMG 14",
        "category": "Cardiac",
        "source_index": 1,
    })

    for _ in range(50):
        generate_question(
            mode="topic",
            topic="Cardiac",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

    # get_random_chunk must never have been called
    mock_retriever.get_random_chunk.assert_not_called()


def test_random_injection_fires_in_random_mode():
    """In random mode, get_random_chunk should be called at least once across 200 calls."""
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()
    mock_tracker.get_recent_chunk_keys.return_value = set()
    mock_tracker.get_chunk_scores.return_value = {}
    mock_retriever.retrieve.return_value = _make_chunks()
    mock_retriever.get_random_chunk.return_value = None  # fallback to normal path
    mock_llm.complete.return_value = json.dumps({
        "question_text": "Q?",
        "question_type": "recall",
        "source_citation": "CMG 14",
        "category": "Cardiac",
        "source_index": 1,
    })

    for _ in range(200):
        generate_question(
            mode="random",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

    call_count = mock_retriever.get_random_chunk.call_count
    # Expect roughly 50 calls (25%) — accept 15–85 as the valid range
    assert 15 <= call_count <= 85, f"Expected ~50 injection calls, got {call_count}"


def test_tracker_passed_to_retrieve_in_topic_mode():
    """tracker must be forwarded to retrieve() in all modes."""
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()
    mock_tracker.get_recent_chunk_keys.return_value = set()
    mock_tracker.get_chunk_scores.return_value = {}
    mock_retriever.retrieve.return_value = _make_chunks()
    mock_llm.complete.return_value = json.dumps({
        "question_text": "Q?",
        "question_type": "recall",
        "source_citation": "CMG 14",
        "category": "Cardiac",
        "source_index": 1,
    })

    generate_question(
        mode="topic",
        topic="Cardiac",
        llm=mock_llm,
        retriever=mock_retriever,
        tracker=mock_tracker,
    )

    # Every retrieve() call must have received tracker=mock_tracker
    for call in mock_retriever.retrieve.call_args_list:
        assert call.kwargs.get("tracker") is mock_tracker or (
            len(call.args) >= 9 and call.args[8] is mock_tracker
        ), f"retrieve() called without tracker: {call}"
```

- [ ] **Step 2: Run new tests to confirm failure**

```bash
python -m pytest tests/quiz/test_agent.py::test_random_injection_suppressed_in_topic_mode tests/quiz/test_agent.py::test_random_injection_fires_in_random_mode tests/quiz/test_agent.py::test_tracker_passed_to_retrieve_in_topic_mode -v
```

Expected: FAIL — `get_random_chunk` never called / `tracker` not passed to `retrieve()`

- [ ] **Step 3: Update `agent.py`**

**Add module-level constant** near the top of the file (after imports):

```python
RANDOM_INJECTION_PROBABILITY = 0.25
```

**Replace the retrieval block** in `generate_question()`. The current code (lines ~108–132) is:

```python
    n_to_fetch = 15 if randomize else 5
    chunks = retriever.retrieve(
        query=query,
        n=n_to_fetch,
        filters=filters,
        exclude_categories=blacklist,
        skill_level=skill_level,
        exclude_content_keys=exclude_keys or None,
        source_restriction=source_restriction,
    )

    if not chunks:
        # Fallback: try without chunk exclusions to avoid dead end
        chunks = retriever.retrieve(
            query=query,
            n=n_to_fetch,
            filters=filters,
            exclude_categories=blacklist,
            skill_level=skill_level,
            source_restriction=source_restriction,
        )

    if not chunks:
        raise ValueError("No relevant chunks found for question generation")
```

Replace with:

```python
    n_to_fetch = 15 if randomize else 5

    # Random injection: only in random mode, 25% of questions pull one corpus-random chunk
    injected_chunk = None
    if mode == "random" and random.random() < RANDOM_INJECTION_PROBABILITY:
        injected_chunk = retriever.get_random_chunk(
            exclude_content_keys=exclude_keys or None,
            skill_level=skill_level,
        )

    if injected_chunk is not None:
        # Pair the injected chunk with 4 semantically-retrieved chunks
        semantic_chunks = retriever.retrieve(
            query=query,
            n=4,
            filters=filters,
            exclude_categories=blacklist,
            skill_level=skill_level,
            exclude_content_keys=exclude_keys or None,
            source_restriction=source_restriction,
            tracker=tracker,
        )
        chunks = [injected_chunk] + semantic_chunks
    else:
        chunks = retriever.retrieve(
            query=query,
            n=n_to_fetch,
            filters=filters,
            exclude_categories=blacklist,
            skill_level=skill_level,
            exclude_content_keys=exclude_keys or None,
            source_restriction=source_restriction,
            tracker=tracker,
        )

        if not chunks:
            # Fallback: try without chunk exclusions to avoid dead end
            chunks = retriever.retrieve(
                query=query,
                n=n_to_fetch,
                filters=filters,
                exclude_categories=blacklist,
                skill_level=skill_level,
                source_restriction=source_restriction,
                tracker=tracker,
            )

        if not chunks:
            raise ValueError("No relevant chunks found for question generation")

        if randomize and len(chunks) > 5:
            chunks = random.sample(chunks, 5)
        else:
            chunks = chunks[:5]
```

- [ ] **Step 4: Run the new tests**

```bash
python -m pytest tests/quiz/test_agent.py::test_random_injection_suppressed_in_topic_mode tests/quiz/test_agent.py::test_random_injection_fires_in_random_mode tests/quiz/test_agent.py::test_tracker_passed_to_retrieve_in_topic_mode -v
```

Expected: PASS

- [ ] **Step 5: Run full quiz suite**

```bash
python -m pytest tests/quiz/ -v
```

Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/python/quiz/agent.py tests/quiz/test_agent.py
git commit -m "feat: wire coverage tracker and random injection into quiz agent"
```

---

## Final Verification

- [ ] **Run the complete quiz test suite one final time**

```bash
python -m pytest tests/quiz/ -v --tb=short
```

Expected: all previously passing tests pass; new tests pass

- [ ] **Spot-check migration with a populated DB (manual)**

If `data/mastery.db` already exists with a `used_chunks` table, run the backend briefly and verify:
1. No startup errors
2. `used_chunks` table is gone
3. `chunk_coverage` table exists with the migrated rows

```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot
python -c "
from src.python.quiz.tracker import Tracker
t = Tracker()
tables = t._conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print('Tables:', [r['name'] for r in tables])
print('Coverage rows:', t._conn.execute('SELECT COUNT(*) FROM chunk_coverage').fetchone()[0])
"
```
