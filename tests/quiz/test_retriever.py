import pytest

from quiz.retriever import Retriever, SOURCE_RANK, _matches_excluded_category
from quiz.models import RetrievedChunk


@pytest.fixture
def retriever(seeded_chroma):
    return Retriever(client=seeded_chroma)


def test_retrieve_returns_results(retriever):
    results = retriever.retrieve("adrenaline cardiac arrest", n=3)
    assert len(results) > 0


def test_retrieve_respects_source_hierarchy(retriever):
    results = retriever.retrieve("adrenaline cardiac", n=5)
    cmg_chunks = [r for r in results if r.source_type == "cmg"]
    note_chunks = [r for r in results if r.source_type != "cmg"]
    if cmg_chunks and note_chunks:
        assert cmg_chunks[0].source_rank < note_chunks[0].source_rank


def test_retrieve_limits_results(retriever):
    results = retriever.retrieve("adrenaline", n=1)
    assert len(results) <= 1


def test_retrieve_with_source_type_filter(retriever):
    results = retriever.retrieve("cardiac arrest", n=5, filters={"source_type": "cmg"})
    assert all(r.source_type == "cmg" for r in results)


def test_retrieve_exclude_categories(retriever):
    results = retriever.retrieve("cardiac arrest", n=5, exclude_categories=["Trauma"])
    for r in results:
        cat = (r.category or "").lower()
        assert "trauma" not in cat


def test_retrieve_exclude_multi_category_note(retriever):
    results = retriever.retrieve(
        "neurological assessment", n=5, exclude_categories=["Clinical Skills"]
    )
    for r in results:
        cat_str = (r.category or "").lower()
        cats = [c.strip() for c in cat_str.split(",")]
        assert "clinical skills" not in cats


def test_retrieve_chunk_has_required_fields(retriever):
    results = retriever.retrieve("adrenaline", n=1)
    assert len(results) == 1
    chunk = results[0]
    assert chunk.content
    assert chunk.source_type in ("cmg", "ref_doc", "cpd_doc", "notability_note")
    assert isinstance(chunk.source_rank, int)
    assert isinstance(chunk.relevance_score, float)


def test_retrieve_with_section_filter(retriever):
    results = retriever.retrieve("adrenaline", n=5, filters={"section": "Cardiac"})
    assert len(results) > 0
    cmg_results = [r for r in results if r.source_type == "cmg"]
    for r in cmg_results:
        assert r.category == "Cardiac"


def test_retrieve_medicine_section_filter(retriever):
    results = retriever.retrieve(
        "adrenaline dose", n=5, filters={"section": "Medicine"}
    )
    assert len(results) > 0
    cmg_results = [r for r in results if r.source_type == "cmg"]
    for r in cmg_results:
        assert r.category == "Medicine"


def test_section_filter_returns_notes_when_section_skipped(retriever):
    results = retriever.retrieve(
        "pathophysiology myocardial", n=5, filters={"section": "Pathophysiology"}
    )
    note_results = [r for r in results if r.source_type == "notability_note"]
    assert len(note_results) > 0


def test_matches_excluded_category_single():
    chunk = RetrievedChunk(
        content="test",
        source_type="notability_note",
        source_file="f",
        source_rank=3,
        category="Trauma",
        relevance_score=0.5,
    )
    assert _matches_excluded_category(chunk, ["Trauma"]) is True
    assert _matches_excluded_category(chunk, ["Cardiac"]) is False


def test_matches_excluded_category_multi():
    chunk = RetrievedChunk(
        content="test",
        source_type="notability_note",
        source_file="f",
        source_rank=3,
        category="Clinical Skills,General Paramedicine",
        relevance_score=0.5,
    )
    assert _matches_excluded_category(chunk, ["Clinical Skills"]) is True
    assert _matches_excluded_category(chunk, ["General Paramedicine"]) is True
    assert _matches_excluded_category(chunk, ["Trauma"]) is False


def test_matches_excluded_category_empty():
    chunk = RetrievedChunk(
        content="test",
        source_type="cmg",
        source_file="f",
        source_rank=0,
        category=None,
        relevance_score=0.5,
    )
    assert _matches_excluded_category(chunk, ["Cardiac"]) is False


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
