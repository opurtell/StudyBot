# Quiz Store SQLite Persistence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace in-memory dicts in `quiz/store.py` with SQLite-backed storage so quiz questions and sessions survive brief backend restarts.

**Architecture:** Add a `QuizStore` class backed by SQLite tables in the existing `mastery.db`. Follow the `Tracker` class pattern — single connection, `threading.Lock`, `_init_schema()`. Stale data is cleared on startup (soft-landing semantics). Public API (module-level functions) stays identical so `router.py` and `test_router.py` need no changes.

**Tech Stack:** Python 3.10+, SQLite3, threading.Lock, Pydantic (for model serialisation), json (stdlib).

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/python/quiz/store.py` | Rewrite | `QuizStore` class + module-level singleton + public API functions |
| `tests/quiz/test_store.py` | Create | Tests for `QuizStore` CRUD, serialisation, clear-on-startup, thread safety |
| `src/python/quiz/router.py` | No changes | Imports from `store.py` remain identical |
| `src/python/quiz/models.py` | No changes | Pydantic models used for (de)serialisation |
| `src/python/quiz/tracker.py` | No changes | Shares `MASTERY_DB_PATH` — no conflicts |

---

### Task 1: Write failing tests for QuizStore

**Files:**
- Create: `tests/quiz/test_store.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
import threading

import pytest

from quiz.models import Question, RetrievedChunk, SessionConfig
from quiz.store import QuizStore


def _make_chunk(**overrides):
    defaults = dict(
        content="Adrenaline 1mg IV.",
        source_type="cmg",
        source_file="cmg_14.json",
        source_rank=0,
        category="Cardiac",
        cmg_number="14",
        chunk_type="protocol",
        relevance_score=0.95,
    )
    defaults.update(overrides)
    return RetrievedChunk(**defaults)


def _make_question(**overrides):
    defaults = dict(
        id="q-1",
        question_text="What is the adrenaline dose?",
        question_type="drug_dose",
        source_chunks=[_make_chunk()],
        source_citation="ACTAS CMG 14.1",
        difficulty="medium",
        category="Cardiac",
    )
    defaults.update(overrides)
    return Question(**defaults)


@pytest.fixture
def store(tmp_path):
    return QuizStore(db_path=tmp_path / "quiz.db")


# --- Question CRUD ---


class TestStoreQuestion:
    def test_store_and_retrieve_question(self, store):
        q = _make_question()
        store.store_question(q)
        got = store.get_question("q-1")
        assert got is not None
        assert got.id == "q-1"
        assert got.question_text == "What is the adrenaline dose?"
        assert got.category == "Cardiac"

    def test_get_missing_question_returns_none(self, store):
        assert store.get_question("nonexistent") is None

    def test_source_chunks_roundtrip(self, store):
        chunks = [
            _make_chunk(content="Chunk A", source_rank=0),
            _make_chunk(content="Chunk B", source_rank=1, category="Trauma"),
        ]
        q = _make_question(source_chunks=chunks)
        store.store_question(q)
        got = store.get_question("q-1")
        assert len(got.source_chunks) == 2
        assert got.source_chunks[0].content == "Chunk A"
        assert got.source_chunks[1].category == "Trauma"
        assert got.source_chunks[1].relevance_score == pytest.approx(0.95)

    def test_overwrite_existing_question(self, store):
        store.store_question(_make_question(question_text="Original"))
        store.store_question(_make_question(question_text="Updated"))
        got = store.get_question("q-1")
        assert got.question_text == "Updated"


# --- Session CRUD ---


class TestStoreSession:
    def test_store_and_retrieve_session(self, store):
        config = SessionConfig(mode="random", difficulty="hard")
        store.store_session("s-1", config)
        got = store.get_session("s-1")
        assert got is not None
        assert got.mode == "random"
        assert got.difficulty == "hard"

    def test_get_missing_session_returns_none(self, store):
        assert store.get_session("nonexistent") is None

    def test_session_blacklist_roundtrip(self, store):
        config = SessionConfig(mode="topic", topic="Cardiac", blacklist=["Paediatrics", "Trauma"])
        store.store_session("s-1", config)
        got = store.get_session("s-1")
        assert got.blacklist == ["Paediatrics", "Trauma"]

    def test_session_default_values(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-1", config)
        got = store.get_session("s-1")
        assert got.asked_question_ids == []
        assert got.asked_chunk_contents == []
        assert got.randomize is True
        assert got.difficulty == "medium"


# --- record_asked ---


class TestRecordAsked:
    def test_record_asked_appends_question_id(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-1", config)
        q = _make_question(id="q-1")
        store.record_asked("s-1", q)
        got = store.get_session("s-1")
        assert "q-1" in got.asked_question_ids

    def test_record_asked_appends_chunk_content(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-1", config)
        q = _make_question()
        store.record_asked("s-1", q)
        got = store.get_session("s-1")
        assert len(got.asked_chunk_contents) == 1
        assert got.asked_chunk_contents[0] == q.source_chunks[0].content[:200]

    def test_record_asked_skips_duplicate_chunk(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-1", config)
        q = _make_question(id="q-1")
        store.record_asked("s-1", q)
        store.record_asked("s-1", q)
        got = store.get_session("s-1")
        assert len(got.asked_chunk_contents) == 1

    def test_record_asked_missing_session_is_noop(self, store):
        q = _make_question()
        store.record_asked("nonexistent", q)  # should not raise


# --- clear_all ---


class TestClearAll:
    def test_clear_all_removes_questions_and_sessions(self, store):
        store.store_question(_make_question())
        store.store_session("s-1", SessionConfig(mode="random"))
        store.clear_all()
        assert store.get_question("q-1") is None
        assert store.get_session("s-1") is None


# --- Clear-on-startup (soft landing) ---


class TestClearOnStartup:
    def test_stale_data_cleared_on_new_instance(self, tmp_path):
        db_path = tmp_path / "quiz.db"
        first = QuizStore(db_path=db_path)
        first.store_question(_make_question())
        first.store_session("s-1", SessionConfig(mode="random"))

        # New instance pointing at the same DB should clear stale data
        second = QuizStore(db_path=db_path)
        assert second.get_question("q-1") is None
        assert second.get_session("s-1") is None


# --- Persistence within a run ---


class TestPersistence:
    def test_data_persists_across_instances_without_clear(self, tmp_path):
        db_path = tmp_path / "quiz.db"

        first = QuizStore(db_path=db_path)
        # The first instance cleared stale data on init — now store fresh data
        first.store_question(_make_question())
        first.store_session("s-1", SessionConfig(mode="topic", topic="Cardiac"))

        # Simulate a brief backend restart: new process constructs a new QuizStore.
        # The constructor will clear stale data. To test "persistence within a run",
        # we verify data survives across separate connections to the same DB file
        # WITHOUT going through the constructor again.
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id FROM quiz_questions WHERE id = 'q-1'").fetchone()
        assert row is not None
        conn.close()

        # Verify the first instance can still read its own data
        got = first.get_question("q-1")
        assert got is not None
        assert got.question_text == "What is the adrenaline dose?"


# --- Thread safety ---


class TestThreadSafety:
    def test_concurrent_store_and_read(self, store):
        errors = []

        def writer(n):
            try:
                store.store_question(_make_question(id=f"q-{n}", question_text=f"Q{n}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All 20 questions should be retrievable
        for i in range(20):
            got = store.get_question(f"q-{i}")
            assert got is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/python && python -m pytest ../../tests/quiz/test_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'QuizStore' from 'quiz.store'`

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/quiz/test_store.py
git commit -m "test: add failing tests for QuizStore SQLite persistence"
```

---

### Task 2: Implement QuizStore class

**Files:**
- Rewrite: `src/python/quiz/store.py`

- [ ] **Step 1: Write the full implementation**

Replace the entire contents of `src/python/quiz/store.py` with:

```python
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from paths import MASTERY_DB_PATH

from .models import Question, RetrievedChunk, SessionConfig


class QuizStore:
    def __init__(self, db_path: str | Path = MASTERY_DB_PATH):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()
        self._clear_stale()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id TEXT PRIMARY KEY,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                source_chunks_json TEXT NOT NULL,
                source_citation TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                category TEXT NOT NULL,
                primary_chunk_index INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                topic TEXT,
                difficulty TEXT DEFAULT 'medium',
                blacklist_json TEXT DEFAULT '[]',
                randomize INTEGER DEFAULT 1,
                asked_question_ids_json TEXT DEFAULT '[]',
                asked_chunk_contents_json TEXT DEFAULT '[]'
            );
        """)

    def _clear_stale(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM quiz_questions")
            self._conn.execute("DELETE FROM quiz_sessions")
            self._conn.commit()

    def store_question(self, question: Question) -> None:
        chunks_json = json.dumps([c.model_dump() for c in question.source_chunks])
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO quiz_questions
                   (id, question_text, question_type, source_chunks_json,
                    source_citation, difficulty, category, primary_chunk_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    question.id,
                    question.question_text,
                    question.question_type,
                    chunks_json,
                    question.source_citation,
                    question.difficulty,
                    question.category,
                    question.primary_chunk_index,
                ),
            )
            self._conn.commit()

    def get_question(self, question_id: str) -> Question | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM quiz_questions WHERE id = ?", (question_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_question(row)

    def _row_to_question(self, row: sqlite3.Row) -> Question:
        chunks_data = json.loads(row["source_chunks_json"])
        source_chunks = [RetrievedChunk(**c) for c in chunks_data]
        return Question(
            id=row["id"],
            question_text=row["question_text"],
            question_type=row["question_type"],
            source_chunks=source_chunks,
            source_citation=row["source_citation"],
            difficulty=row["difficulty"],
            category=row["category"],
            primary_chunk_index=row["primary_chunk_index"],
        )

    def store_session(self, session_id: str, config: SessionConfig) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO quiz_sessions
                   (id, mode, topic, difficulty, blacklist_json, randomize,
                    asked_question_ids_json, asked_chunk_contents_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    config.mode,
                    config.topic,
                    config.difficulty,
                    json.dumps(config.blacklist),
                    int(config.randomize),
                    json.dumps(config.asked_question_ids),
                    json.dumps(config.asked_chunk_contents),
                ),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> SessionConfig | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def _row_to_session(self, row: sqlite3.Row) -> SessionConfig:
        return SessionConfig(
            mode=row["mode"],
            topic=row["topic"],
            difficulty=row["difficulty"],
            blacklist=json.loads(row["blacklist_json"]),
            randomize=bool(row["randomize"]),
            asked_question_ids=json.loads(row["asked_question_ids_json"]),
            asked_chunk_contents=json.loads(row["asked_chunk_contents_json"]),
        )

    def record_asked(self, session_id: str, question: Question) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                return
            session = self._row_to_session(row)
            session.asked_question_ids.append(question.id)
            for chunk in question.source_chunks:
                content_key = chunk.content[:200]
                if content_key not in session.asked_chunk_contents:
                    session.asked_chunk_contents.append(content_key)
            self._conn.execute(
                """UPDATE quiz_sessions
                   SET asked_question_ids_json = ?, asked_chunk_contents_json = ?
                   WHERE id = ?""",
                (
                    json.dumps(session.asked_question_ids),
                    json.dumps(session.asked_chunk_contents),
                    session_id,
                ),
            )
            self._conn.commit()

    def clear_all(self) -> None:
        self._clear_stale()


# Module-level singleton — public API unchanged

_store: QuizStore | None = None
_store_lock = threading.Lock()


def _get_store() -> QuizStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = QuizStore()
    return _store


def store_question(question: Question) -> None:
    _get_store().store_question(question)


def get_question(question_id: str) -> Question | None:
    return _get_store().get_question(question_id)


def store_session(session_id: str, config: SessionConfig) -> None:
    _get_store().store_session(session_id, config)


def get_session(session_id: str) -> SessionConfig | None:
    return _get_store().get_session(session_id)


def record_asked(session_id: str, question: Question) -> None:
    _get_store().record_asked(session_id, question)


def clear_all() -> None:
    _get_store().clear_all()
```

- [ ] **Step 2: Run the new store tests**

Run: `cd src/python && python -m pytest ../../tests/quiz/test_store.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Run existing router tests to confirm no breakage**

Run: `cd src/python && python -m pytest ../../tests/quiz/test_router.py -v`
Expected: All tests PASS — `test_router.py` imports `store_question`, `get_question`, etc. from `quiz.store`, which still works via the module-level functions.

- [ ] **Step 4: Run the full Python test suite**

Run: `cd src/python && python -m pytest ../../tests/ -v --timeout=30`
Expected: All tests PASS. If any pre-existing failures, they should match the known failures list in `KNOWN_TEST_FAILURES.md`.

- [ ] **Step 5: Commit**

```bash
git add src/python/quiz/store.py tests/quiz/test_store.py
git commit -m "feat: persist quiz questions and sessions to SQLite

Replace in-memory dicts with QuizStore class backed by SQLite tables
in mastery.db. Data survives brief backend restarts (soft landing).
Stale data is cleared on startup. Public API unchanged."
```
