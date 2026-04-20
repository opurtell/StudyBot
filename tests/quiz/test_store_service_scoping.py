"""Tests for service-scoping of quiz questions and sessions.

Covers:
- Cross-service isolation (ACTAS vs AT data must not leak)
- Session scoping by service
- Default service fallback ("actas")
- Schema migration from old DBs lacking the service column
"""

import sqlite3

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


# --- Cross-service isolation ---


class TestCrossServiceIsolation:
    def test_actas_questions_only_return_actas(self, store):
        actas_q = _make_question(id="q-actas", question_text="ACTAS question")
        at_q = _make_question(id="q-at", question_text="AT question")
        store.store_question(actas_q, service="actas")
        store.store_question(at_q, service="at")

        got_actas = store.get_question("q-actas", service="actas")
        got_at_via_actas = store.get_question("q-at", service="actas")
        got_at = store.get_question("q-at", service="at")

        assert got_actas is not None
        assert got_actas.question_text == "ACTAS question"
        assert got_at_via_actas is None  # AT question invisible from ACTAS scope
        assert got_at is not None
        assert got_at.question_text == "AT question"

    def test_different_services_can_share_id(self, store):
        """Two services should be able to store a question with the same ID."""
        actas_q = _make_question(id="q-shared", question_text="ACTAS version")
        at_q = _make_question(id="q-shared", question_text="AT version")
        store.store_question(actas_q, service="actas")
        store.store_question(at_q, service="at")

        got_actas = store.get_question("q-shared", service="actas")
        got_at = store.get_question("q-shared", service="at")

        assert got_actas.question_text == "ACTAS version"
        assert got_at.question_text == "AT version"


# --- Session scoping ---


class TestSessionScoping:
    def test_sessions_scoped_by_service(self, store):
        actas_config = SessionConfig(mode="random", difficulty="hard")
        at_config = SessionConfig(mode="topic", topic="Trauma", difficulty="easy")
        store.store_session("s-1", actas_config, service="actas")
        store.store_session("s-1", at_config, service="at")

        got_actas = store.get_session("s-1", service="actas")
        got_at = store.get_session("s-1", service="at")

        assert got_actas is not None
        assert got_actas.mode == "random"
        assert got_actas.difficulty == "hard"

        assert got_at is not None
        assert got_at.mode == "topic"
        assert got_at.topic == "Trauma"
        assert got_at.difficulty == "easy"

    def test_session_not_visible_across_services(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-at-only", config, service="at")

        assert store.get_session("s-at-only", service="actas") is None
        assert store.get_session("s-at-only", service="at") is not None

    def test_record_asked_scoped_by_service(self, store):
        actas_config = SessionConfig(mode="random")
        at_config = SessionConfig(mode="random")
        store.store_session("s-1", actas_config, service="actas")
        store.store_session("s-1", at_config, service="at")

        q = _make_question(id="q-1")
        store.record_asked("s-1", q, service="actas")

        got_actas = store.get_session("s-1", service="actas")
        got_at = store.get_session("s-1", service="at")

        assert "q-1" in got_actas.asked_question_ids
        assert got_at.asked_question_ids == []  # AT session untouched

    def test_record_asked_missing_service_is_noop(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-1", config, service="actas")

        q = _make_question(id="q-1")
        # Recording against 'at' service — session only exists for 'actas'
        store.record_asked("s-1", q, service="at")

        got = store.get_session("s-1", service="actas")
        assert got.asked_question_ids == []


# --- Default service ---


class TestDefaultService:
    def test_store_question_defaults_to_actas(self, store):
        q = _make_question(id="q-default")
        store.store_question(q)  # no service arg

        # Should be retrievable via explicit "actas"
        got = store.get_question("q-default", service="actas")
        assert got is not None
        assert got.id == "q-default"

    def test_store_session_defaults_to_actas(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-default", config)  # no service arg

        got = store.get_session("s-default", service="actas")
        assert got is not None
        assert got.mode == "random"

    def test_get_question_defaults_to_actas(self, store):
        q = _make_question(id="q-only-actas")
        store.store_question(q, service="actas")

        # No service arg — should default to "actas" and find it
        got = store.get_question("q-only-actas")
        assert got is not None

    def test_get_session_defaults_to_actas(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-only-actas", config, service="actas")

        got = store.get_session("s-only-actas")
        assert got is not None

    def test_record_asked_defaults_to_actas(self, store):
        config = SessionConfig(mode="random")
        store.store_session("s-default", config, service="actas")

        q = _make_question(id="q-1")
        store.record_asked("s-default", q)  # no service arg

        got = store.get_session("s-default", service="actas")
        assert "q-1" in got.asked_question_ids


# --- Migration from old schema ---


class TestServiceMigration:
    def test_migration_recreates_table_with_service_column(self, tmp_path):
        """A database created with the old schema (no service column) should
        be migrated: table is recreated with composite PK and service column.
        Note: _clear_stale wipes all rows on startup, so we verify schema,
        not data persistence."""
        db_path = tmp_path / "old.db"

        # Create tables without the service column (old schema)
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE quiz_questions (
                id TEXT PRIMARY KEY,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                source_chunks_json TEXT NOT NULL,
                source_citation TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                category TEXT NOT NULL,
                primary_chunk_index INTEGER DEFAULT 0
            );
            CREATE TABLE quiz_sessions (
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
        conn.commit()
        conn.close()

        # Open with new QuizStore — should trigger migration
        store = QuizStore(db_path=db_path)

        # Verify schema now has the service column
        conn2 = sqlite3.connect(str(db_path))
        cols_q = [row[1] for row in conn2.execute("PRAGMA table_info(quiz_questions)").fetchall()]
        cols_s = [row[1] for row in conn2.execute("PRAGMA table_info(quiz_sessions)").fetchall()]
        conn2.close()

        assert "service" in cols_q, f"service column missing from quiz_questions: {cols_q}"
        assert "service" in cols_s, f"service column missing from quiz_sessions: {cols_s}"

        # Verify composite PK works: can insert same ID for different services
        store.store_question(_make_question(id="q-1", question_text="ACTAS"), service="actas")
        store.store_question(_make_question(id="q-1", question_text="AT"), service="at")
        assert store.get_question("q-1", service="actas").question_text == "ACTAS"
        assert store.get_question("q-1", service="at").question_text == "AT"

    def test_migration_preserves_schema_after_reopen(self, tmp_path):
        """After migration, reopening the store should not re-migrate (schema is already new)."""
        db_path = tmp_path / "twice.db"

        # First open creates fresh schema with service column
        QuizStore(db_path=db_path)

        # Store data after first open's stale-clear
        store1 = QuizStore(db_path=db_path)
        store1.store_question(_make_question(id="q-test"), service="actas")

        # Second open should work fine — no double-migration issues
        store2 = QuizStore(db_path=db_path)
        # After stale-clear, insert fresh data
        store2.store_question(_make_question(id="q-test"), service="actas")
        got = store2.get_question("q-test", service="actas")
        assert got is not None
        assert got.question_text == "What is the adrenaline dose?"
