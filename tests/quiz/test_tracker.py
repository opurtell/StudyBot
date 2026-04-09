import pytest

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
    assert mastery[0].mastery_percent == pytest.approx(75.0)


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
