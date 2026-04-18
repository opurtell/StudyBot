import pytest
from datetime import datetime, timedelta, timezone

from quiz.tracker import Tracker


@pytest.fixture
def tracker(tmp_path):
    return Tracker(db_path=tmp_path / "mastery.db")


def test_record_answer_creates_category(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14.1")
    mastery = tracker.get_mastery()
    assert len(mastery) == 1
    assert mastery[0].category == "Cardiac"


def test_record_answer_correct_increments(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14.1")
    tracker.record_answer("q2", "Cardiac", "scenario", "correct", 20.0, "CMG 14.1")
    mastery = tracker.get_mastery()
    assert mastery[0].correct == 2
    assert mastery[0].total_attempts == 2


def test_record_answer_partial_and_incorrect(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "partial", 15.0, "CMG 14.1")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14.1")
    mastery = tracker.get_mastery()
    assert mastery[0].partial == 1
    assert mastery[0].incorrect == 1


def test_mastery_percent_calculation(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "partial", 15.0, "CMG 14")
    tracker.record_answer("q3", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    mastery = tracker.get_mastery()
    assert mastery[0].mastery_percent == pytest.approx(50.0)


def test_mastery_status_strong(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q3", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    assert tracker.get_mastery()[0].status == "strong"


def test_mastery_status_developing(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "partial", 15.0, "CMG 14")
    assert tracker.get_mastery()[0].status == "developing"


def test_mastery_status_weak(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    assert tracker.get_mastery()[0].status == "weak"


def test_self_graded_excluded_from_mastery(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", None, 12.0, "CMG 14")
    mastery = tracker.get_mastery()
    assert len(mastery) == 0


def test_self_graded_still_in_history(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", None, 12.0, "CMG 14")
    history = tracker.get_recent_history()
    assert len(history) == 1
    assert history[0].score is None


def test_get_weak_categories(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "recall", "incorrect", 30.0, "CMG 7")
    weak = tracker.get_weak_categories(n=1)
    assert weak == ["Trauma"]


def test_get_streak(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q3", "Cardiac", "recall", "partial", 15.0, "CMG 14")
    assert tracker.get_streak() == 0


def test_get_streak_active(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    assert tracker.get_streak() == 2


def test_get_accuracy(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    assert tracker.get_accuracy() == pytest.approx(50.0)


def test_blacklist_add_and_get(tracker):
    tracker.add_to_blacklist("Paediatrics")
    assert tracker.get_blacklist() == ["Paediatrics"]


def test_blacklist_remove(tracker):
    tracker.add_to_blacklist("Paediatrics")
    tracker.remove_from_blacklist("Paediatrics")
    assert tracker.get_blacklist() == []


def test_blacklist_duplicate_ignored(tracker):
    tracker.add_to_blacklist("Paediatrics")
    tracker.add_to_blacklist("Paediatrics")
    assert tracker.get_blacklist() == ["Paediatrics"]


def test_get_recent_history(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "scenario", "incorrect", 30.0, "CMG 7")
    history = tracker.get_recent_history(limit=10)
    assert len(history) == 2
    assert history[0].category == "Trauma"
    assert history[1].category == "Cardiac"


def test_get_recent_history_applies_offset(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "scenario", "incorrect", 30.0, "CMG 7")
    tracker.record_answer("q3", "Respiratory", "recall", "correct", 12.0, "CMG 9")

    history = tracker.get_recent_history(limit=1, offset=1)

    assert len(history) == 1
    assert history[0].category == "Trauma"


def test_mastery_and_history_persist_across_tracker_restart(tmp_path):
    db_path = tmp_path / "mastery.db"

    first = Tracker(db_path=db_path)
    first.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    first.record_answer("q2", "Trauma", "scenario", "incorrect", 30.0, "CMG 7")

    second = Tracker(db_path=db_path)
    mastery = sorted(second.get_mastery(), key=lambda item: item.category)
    history = second.get_recent_history(limit=10)

    assert [item.category for item in mastery] == ["Cardiac", "Trauma"]
    assert mastery[0].mastery_percent == pytest.approx(100.0)
    assert mastery[1].mastery_percent == pytest.approx(0.0)
    assert [item.category for item in history] == ["Trauma", "Cardiac"]


def test_blacklist_persists_across_tracker_restart(tmp_path):
    db_path = tmp_path / "mastery.db"

    first = Tracker(db_path=db_path)
    first.add_to_blacklist("Paediatrics")
    first.add_to_blacklist("Obstetrics")

    second = Tracker(db_path=db_path)

    assert sorted(second.get_blacklist()) == ["Obstetrics", "Paediatrics"]


def test_correct_answer_updates_score(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 10.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    mastery = tracker.get_mastery()
    assert mastery[0].correct == 1
    assert mastery[0].incorrect == 0


def test_correct_answer_updates_mastery_percent(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    mastery = tracker.get_mastery()
    assert mastery[0].mastery_percent == pytest.approx(50.0)


def test_correct_answer_no_history_row(tracker):
    """Correcting a question with no history should not raise."""
    tracker.correct_answer("nonexistent", "correct")
    # No crash, no rows created
    assert tracker.get_mastery() == []


def test_correct_answer_updates_latest_only(tracker):
    """If the same question_id appears twice, only the latest row is corrected."""
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 10.0, "CMG 14")
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 15.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    history = tracker.get_recent_history(limit=10)
    # Two rows: latest corrected to "correct", earlier still "incorrect"
    assert history[0].score == "correct"
    assert history[1].score == "incorrect"


def test_correct_answer_updates_streak(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.correct_answer("q1", "correct")
    assert tracker.get_streak() == 2


def test_clear_mastery_data_removes_history_and_categories(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "recall", "incorrect", 30.0, "CMG 7")
    assert len(tracker.get_mastery()) == 2
    assert len(tracker.get_recent_history(limit=10)) == 2

    deleted = tracker.clear_mastery_data()

    assert deleted == 2
    assert tracker.get_mastery() == []
    assert tracker.get_recent_history(limit=10) == []
    assert tracker.get_streak() == 0
    assert tracker.get_accuracy() == 0.0


def test_clear_mastery_data_preserves_blacklist(tracker):
    tracker.add_to_blacklist("Paediatrics")
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.clear_mastery_data()
    assert tracker.get_blacklist() == ["Paediatrics"]


def test_clear_mastery_data_empty_db(tracker):
    deleted = tracker.clear_mastery_data()
    assert deleted == 0


def test_record_used_chunks(tracker):
    tracker.record_used_chunks(["chunk_a_200chars...", "chunk_b_200chars..."])
    keys = tracker.get_recent_chunk_keys()
    assert "chunk_a_200chars..." in keys
    assert "chunk_b_200chars..." in keys


def test_record_used_chunks_dedup(tracker):
    tracker.record_used_chunks(["chunk_a"])
    tracker.record_used_chunks(["chunk_a"])
    keys = tracker.get_recent_chunk_keys()
    assert len(keys) == 1


def test_clear_mastery_data_clears_chunk_coverage(tracker):
    tracker.record_used_chunks(["chunk_a", "chunk_b"])
    assert len(tracker.get_recent_chunk_keys()) == 2
    tracker.clear_mastery_data()
    assert len(tracker.get_recent_chunk_keys()) == 0


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
    old_date = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=8)).isoformat()
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
