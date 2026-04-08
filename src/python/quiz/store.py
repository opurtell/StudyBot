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
