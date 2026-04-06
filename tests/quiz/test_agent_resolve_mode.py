from unittest.mock import MagicMock

import pytest

from quiz.agent import _resolve_mode
from quiz.tracker import Tracker


@pytest.fixture
def tracker():
    return MagicMock(spec=Tracker)


class TestResolveMode:
    def test_topic_mode_returns_section_filter(self, tracker):
        query, filters = _resolve_mode("topic", "Cardiac", tracker)
        assert query == "Cardiac"
        assert filters == {"section": "Cardiac"}

    def test_topic_mode_raises_without_topic(self, tracker):
        with pytest.raises(ValueError, match="Topic mode requires a topic"):
            _resolve_mode("topic", None, tracker)

    def test_gap_driven_uses_weak_category(self, tracker):
        tracker.get_weak_categories.return_value = ["Trauma"]
        query, filters = _resolve_mode("gap_driven", None, tracker)
        assert query == "Trauma"
        assert filters is None

    def test_gap_driven_falls_back_random(self, tracker):
        tracker.get_weak_categories.return_value = []
        query, filters = _resolve_mode("gap_driven", None, tracker)
        assert query in ["Cardiac", "Trauma", "Respiratory"]
        assert filters is None

    def test_random_mode_returns_query_no_filter(self, tracker):
        query, filters = _resolve_mode("random", None, tracker)
        assert isinstance(query, str)
        assert len(query) > 0
        assert filters is None

    def test_clinical_guidelines_returns_query_and_in_filter(self, tracker):
        expected_sections = {
            "Cardiac",
            "Trauma",
            "Medical",
            "Respiratory",
            "Airway Management",
            "Paediatric",
            "Obstetric",
            "Neurology",
            "Behavioural",
            "Toxicology",
            "Environmental",
            "Pain Management",
            "Palliative Care",
            "HAZMAT",
            "General Care",
        }
        query, filters = _resolve_mode("clinical_guidelines", None, tracker)
        assert query in expected_sections
        assert filters is not None
        assert filters == {"section": {"$in": sorted(expected_sections)}}

    def test_unknown_mode_raises(self, tracker):
        with pytest.raises(ValueError, match="Unknown mode"):
            _resolve_mode("nonexistent", None, tracker)
