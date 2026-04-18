from unittest.mock import MagicMock

import pytest

from quiz.agent import _resolve_mode, CMG_ONLY_SECTIONS
from quiz.tracker import Tracker


@pytest.fixture
def tracker():
    return MagicMock(spec=Tracker)


class TestResolveMode:
    def test_topic_mode_returns_section_filter(self, tracker):
        query, filters, restriction = _resolve_mode("topic", "Cardiac", tracker)
        assert query == "Cardiac"
        assert filters == {"section": "Cardiac"}
        assert restriction == "cmg"

    def test_topic_mode_non_cmg_section_no_restriction(self, tracker):
        query, filters, restriction = _resolve_mode("topic", "Pharmacology", tracker)
        assert query == "Pharmacology"
        assert filters == {"section": "Pharmacology"}
        assert restriction is None

    def test_topic_mode_medicine_restricted_to_cmg(self, tracker):
        query, filters, restriction = _resolve_mode("topic", "Medicine", tracker)
        assert query == "Medicine"
        assert filters == {"section": "Medicine"}
        assert restriction == "cmg"

    def test_topic_mode_clinical_skill_restricted_to_cmg(self, tracker):
        query, filters, restriction = _resolve_mode("topic", "Clinical Skill", tracker)
        assert query == "Clinical Skill"
        assert filters == {"section": "Clinical Skill"}
        assert restriction == "cmg"

    def test_topic_mode_raises_without_topic(self, tracker):
        with pytest.raises(ValueError, match="Topic mode requires a topic"):
            _resolve_mode("topic", None, tracker)

    def test_gap_driven_uses_weak_category(self, tracker):
        tracker.get_weak_categories.return_value = ["Trauma"]
        query, filters, restriction = _resolve_mode("gap_driven", None, tracker)
        assert query == "Trauma"
        assert filters is None
        assert restriction == "cmg"

    def test_gap_driven_falls_back_random(self, tracker):
        tracker.get_weak_categories.return_value = []
        query, filters, restriction = _resolve_mode("gap_driven", None, tracker)
        assert query in ["Cardiac", "Trauma", "Respiratory"]
        assert filters is None
        assert restriction == "cmg"

    def test_gap_driven_non_cmg_category(self, tracker):
        tracker.get_weak_categories.return_value = ["Pharmacology"]
        query, filters, restriction = _resolve_mode("gap_driven", None, tracker)
        assert query == "Pharmacology"
        assert filters is None
        assert restriction is None

    def test_random_mode_cmg_sections_have_filter_and_restriction(self, tracker):
        # Run enough times to hit at least one CMG option
        for _ in range(50):
            query, filters, restriction = _resolve_mode("random", None, tracker)
            assert isinstance(query, str)
            assert len(query) > 0
            if filters and "section" in filters:
                section = filters["section"]
                if section in CMG_ONLY_SECTIONS:
                    assert restriction == "cmg"
            else:
                assert restriction is None

    def test_random_mode_all_options_valid(self, tracker):
        valid_queries = {
            "Cardiac", "Trauma", "Respiratory", "Paediatrics",
            "Pharmacology", "Obstetrics", "Mental Health",
            "Infectious Disease", "Pathophysiology", "Clinical Skills",
            "General Paramedicine", "Operational Guidelines",
            "Medication Guidelines", "ECGs",
        }
        for _ in range(100):
            query, filters, restriction = _resolve_mode("random", None, tracker)
            assert query in valid_queries

    def test_clinical_guidelines_returns_query_and_section_filter(self, tracker):
        expected_sections = {
            "Cardiac",
            "Trauma",
            "Medical",
            "Respiratory",
            "Airway Management",
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
        query, filters, restriction = _resolve_mode("clinical_guidelines", None, tracker)
        assert query in expected_sections
        assert filters == {"section": query}
        assert restriction == "cmg"

    def test_unknown_mode_raises(self, tracker):
        with pytest.raises(ValueError, match="Unknown mode"):
            _resolve_mode("nonexistent", None, tracker)
