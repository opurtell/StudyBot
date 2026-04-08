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
