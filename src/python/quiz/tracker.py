from __future__ import annotations

import sqlite3
from pathlib import Path

from paths import MASTERY_DB_PATH

from .models import CategoryMastery, QuizAttempt


class Tracker:
    def __init__(self, db_path: str | Path = MASTERY_DB_PATH):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

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
        """)

    def record_answer(
        self,
        question_id: str,
        category: str,
        question_type: str,
        score: str | None,
        elapsed_seconds: float,
        source_citation: str,
    ) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,)
        )
        row = self._conn.execute(
            "SELECT id FROM categories WHERE name = ?", (category,)
        ).fetchone()
        cat_id = row["id"]

        self._conn.execute(
            """INSERT INTO quiz_history
               (question_id, category_id, question_type, score, elapsed_seconds, source_citation)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                question_id,
                cat_id,
                question_type,
                score,
                elapsed_seconds,
                source_citation,
            ),
        )
        self._conn.commit()

    def get_mastery(self) -> list[CategoryMastery]:
        rows = self._conn.execute("""
            SELECT c.name,
                   COUNT(*) FILTER (WHERE h.score IS NOT NULL) AS total,
                   COUNT(*) FILTER (WHERE h.score = 'correct') AS correct,
                   COUNT(*) FILTER (WHERE h.score = 'partial') AS partial,
                   COUNT(*) FILTER (WHERE h.score = 'incorrect') AS incorrect
            FROM categories c
            JOIN quiz_history h ON h.category_id = c.id
            GROUP BY c.name
        """).fetchall()

        results = []
        for row in rows:
            total = row["total"]
            if total == 0:
                continue
            correct = row["correct"]
            partial = row["partial"]
            incorrect = row["incorrect"]
            percent = (correct + partial * 0.5) / total * 100
            status = (
                "strong" if percent > 75 else "developing" if percent >= 50 else "weak"
            )
            results.append(
                CategoryMastery(
                    category=row["name"],
                    total_attempts=total,
                    correct=correct,
                    partial=partial,
                    incorrect=incorrect,
                    mastery_percent=round(percent, 1),
                    status=status,
                )
            )
        return results

    def get_weak_categories(self, n: int = 3) -> list[str]:
        mastery = self.get_mastery()
        mastery.sort(key=lambda m: m.mastery_percent)
        return [m.category for m in mastery[:n]]

    def get_streak(self) -> int:
        rows = self._conn.execute(
            "SELECT score FROM quiz_history WHERE score IS NOT NULL ORDER BY id DESC"
        ).fetchall()
        streak = 0
        for row in rows:
            if row["score"] == "correct":
                streak += 1
            else:
                break
        return streak

    def get_accuracy(self) -> float:
        row = self._conn.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE score = 'correct') AS correct
            FROM quiz_history
            WHERE score IS NOT NULL
        """).fetchone()
        if not row or row["total"] == 0:
            return 0.0
        return round(row["correct"] / row["total"] * 100, 1)

    def get_recent_history(self, limit: int = 20, offset: int = 0) -> list[QuizAttempt]:
        rows = self._conn.execute(
            """
            SELECT h.id, h.question_id, c.name AS category, h.question_type,
                   h.score, h.elapsed_seconds, h.source_citation, h.created_at
            FROM quiz_history h
            JOIN categories c ON h.category_id = c.id
            ORDER BY h.id DESC
            LIMIT ?
            OFFSET ?
        """,
            (limit, offset),
        ).fetchall()
        return [
            QuizAttempt(
                id=row["id"],
                question_id=row["question_id"],
                category=row["category"],
                question_type=row["question_type"],
                score=row["score"],
                elapsed_seconds=row["elapsed_seconds"],
                source_citation=row["source_citation"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add_to_blacklist(self, category_name: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO blacklist (category_name) VALUES (?)",
            (category_name,),
        )
        self._conn.commit()

    def remove_from_blacklist(self, category_name: str) -> None:
        self._conn.execute(
            "DELETE FROM blacklist WHERE category_name = ?", (category_name,)
        )
        self._conn.commit()

    def get_blacklist(self) -> list[str]:
        rows = self._conn.execute("SELECT category_name FROM blacklist").fetchall()
        return [row["category_name"] for row in rows]
