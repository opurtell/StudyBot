import json
from unittest.mock import MagicMock

import pytest

from quiz.agent import generate_question, evaluate_answer
from quiz.models import Question, RetrievedChunk, Evaluation


def _make_chunks(**overrides) -> list[RetrievedChunk]:
    defaults = {
        "content": "Adrenaline 1mg IV/IO every 3-5 minutes during cardiac arrest.",
        "source_type": "cmg",
        "source_file": "cmg_14.json",
        "source_rank": 0,
        "category": "Cardiac",
        "cmg_number": "14",
        "chunk_type": "protocol",
        "relevance_score": 0.95,
    }
    defaults.update(overrides)
    return [RetrievedChunk(**defaults)]


def _make_question(**overrides) -> Question:
    defaults = {
        "id": "test-q-1",
        "question_text": "What is the recommended adrenaline dosing for adult cardiac arrest?",
        "question_type": "drug_dose",
        "source_chunks": _make_chunks(),
        "source_citation": "ACTAS CMG 14.1",
        "difficulty": "medium",
        "category": "Cardiac",
    }
    defaults.update(overrides)
    return Question(**defaults)


class TestGenerateQuestion:
    def test_returns_question_object(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "What adrenaline dose for cardiac arrest?",
                "question_type": "drug_dose",
                "source_citation": "ACTAS CMG 14.1",
                "category": "Cardiac",
                "source_index": 1,
            }
        )

        result = generate_question(
            mode="topic",
            topic="Cardiac",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )
        assert result.question_text
        assert result.question_type == "drug_dose"
        assert result.category == "Cardiac"
        assert result.id
        assert result.primary_chunk_index == 0

    def test_topic_mode_filters_by_topic(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "Test?",
                "question_type": "recall",
                "source_citation": "CMG 14",
                "category": "Cardiac",
            }
        )

        generate_question(
            mode="topic",
            topic="Cardiac",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )
        mock_retriever.retrieve.assert_called_once()
        call_kwargs = mock_retriever.retrieve.call_args
        assert "Cardiac" in str(call_kwargs)

    def test_topic_mode_passes_section_filter_to_retriever(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "Test?",
                "question_type": "recall",
                "source_citation": "CMG 14",
                "category": "Cardiac",
            }
        )

        generate_question(
            mode="topic",
            topic="Cardiac",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )
        call_kwargs = mock_retriever.retrieve.call_args.kwargs
        assert call_kwargs["filters"] == {"section": "Cardiac"}

    def test_gap_driven_uses_weak_categories(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_tracker.get_weak_categories.return_value = ["Trauma", "Paediatrics"]
        mock_retriever.retrieve.return_value = _make_chunks(category="Trauma")
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "Test?",
                "question_type": "recall",
                "source_citation": "CMG 7",
                "category": "Trauma",
            }
        )

        result = generate_question(
            mode="gap_driven",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )
        mock_tracker.get_weak_categories.assert_called_once()

    def test_random_mode(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_retriever.get_random_chunk.return_value = None
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "Test?",
                "question_type": "recall",
                "source_citation": "CMG 14",
                "category": "Cardiac",
                "source_index": 1,
            }
        )

        result = generate_question(
            mode="random",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )
        assert result.question_text

    def test_primary_chunk_index_parsed_from_llm(self):
        chunks = [
            RetrievedChunk(
                content="Unrelated palliative care content.",
                source_type="notability_note",
                source_file="palliative.md",
                source_rank=3,
                category="Palliative Care",
                relevance_score=0.6,
            ),
            RetrievedChunk(
                content="Adrenaline 1mg IV/IO every 3-5 minutes during cardiac arrest.",
                source_type="cmg",
                source_file="cmg_14.json",
                source_rank=0,
                category="Cardiac",
                cmg_number="14",
                chunk_type="protocol",
                relevance_score=0.95,
            ),
        ]
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = chunks
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "What is the adrenaline dose?",
                "question_type": "drug_dose",
                "source_citation": "ACTAS CMG 14",
                "category": "Cardiac",
                "source_index": 2,
            }
        )

        result = generate_question(
            mode="topic",
            topic="Cardiac",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )
        assert result.primary_chunk_index == 1
        assert result.source_citation == "ACTAS CMG 14"

    def test_difficulty_easy_adds_easy_instructions(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "What is the adrenaline dose?",
                "question_type": "drug_dose",
                "source_citation": "ACTAS CMG 14",
                "category": "Cardiac",
            }
        )

        generate_question(
            mode="topic",
            topic="Cardiac",
            difficulty="easy",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

        call_args = mock_llm.complete.call_args[0][0]
        user_msg = [m for m in call_args if m["role"] == "user"][0]["content"]
        assert "straightforward recall" in user_msg
        assert "single-fact" in user_msg

    def test_difficulty_hard_adds_hard_instructions(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "A 65-year-old patient presents with...",
                "question_type": "scenario",
                "source_citation": "ACTAS CMG 14",
                "category": "Cardiac",
            }
        )

        generate_question(
            mode="topic",
            topic="Cardiac",
            difficulty="hard",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

        call_args = mock_llm.complete.call_args[0][0]
        user_msg = [m for m in call_args if m["role"] == "user"][0]["content"]
        assert "multi-step scenario" in user_msg
        assert "2+ clinical concepts" in user_msg

    def test_difficulty_medium_adds_no_extra_instructions(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "What is the adrenaline dose?",
                "question_type": "drug_dose",
                "source_citation": "ACTAS CMG 14",
                "category": "Cardiac",
            }
        )

        generate_question(
            mode="topic",
            topic="Cardiac",
            difficulty="medium",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

        call_args = mock_llm.complete.call_args[0][0]
        user_msg = [m for m in call_args if m["role"] == "user"][0]["content"]
        assert "straightforward recall" not in user_msg
        assert "single-fact" not in user_msg
        assert "multi-step scenario" not in user_msg
        assert "2+ clinical concepts" not in user_msg


class TestEvaluateAnswer:
    def test_correct_answer(self):
        mock_llm = MagicMock()
        question = _make_question()

        mock_llm.complete.return_value = json.dumps(
            {
                "score": "correct",
                "correct_elements": ["1mg IV/IO", "every 3-5 minutes"],
                "missing_or_wrong": [],
                "source_quote": "Adrenaline 1mg IV/IO every 3-5 minutes during cardiac arrest.",
                "feedback_summary": "Correct.",
            }
        )

        result = evaluate_answer(
            question=question,
            user_answer="1mg IV every 3-5 minutes",
            elapsed_seconds=45.0,
            llm=mock_llm,
        )
        assert result.score == "correct"
        assert result.correct_elements
        assert result.feedback_summary

    def test_partial_answer(self):
        mock_llm = MagicMock()
        question = _make_question()

        mock_llm.complete.return_value = json.dumps(
            {
                "score": "partial",
                "correct_elements": ["adrenaline"],
                "missing_or_wrong": ["missed dose amount"],
                "source_quote": "Adrenaline 1mg IV/IO every 3-5 minutes.",
                "feedback_summary": "Partially correct.",
            }
        )

        result = evaluate_answer(
            question=question,
            user_answer="adrenaline",
            elapsed_seconds=20.0,
            llm=mock_llm,
        )
        assert result.score == "partial"

    def test_reveal_path_returns_null_score(self):
        question = _make_question()
        mock_llm = MagicMock()

        result = evaluate_answer(
            question=question,
            user_answer=None,
            elapsed_seconds=12.0,
            llm=mock_llm,
        )
        assert result.score is None
        assert result.feedback_summary is None
        assert result.source_quote
        mock_llm.complete.assert_not_called()

    def test_reveal_uses_primary_chunk_not_first(self):
        chunk_a = RetrievedChunk(
            content="First Nations cultural considerations for end-of-life care.",
            source_type="notability_note",
            source_file="cultural_notes.md",
            source_rank=3,
            category="Palliative Care",
            relevance_score=0.7,
        )
        chunk_b = RetrievedChunk(
            content="STEP 123: During a CBRN incident, evacuate casualties upwind.",
            source_type="cmg",
            source_file="cmg_hazmat.json",
            source_rank=0,
            category="HAZMAT",
            cmg_number="HAZMAT",
            chunk_type="protocol",
            relevance_score=0.95,
        )
        question = Question(
            id="q-cbrn",
            question_text="What does STEP 123 instruct for three casualties?",
            question_type="recall",
            source_chunks=[chunk_a, chunk_b],
            source_citation="ACTAS CMG HAZMAT",
            difficulty="medium",
            category="HAZMAT",
            primary_chunk_index=1,
        )

        result = evaluate_answer(
            question=question,
            user_answer=None,
            elapsed_seconds=5.0,
            llm=MagicMock(),
        )
        assert "STEP 123" in result.source_quote
        assert "First Nations" not in result.source_quote

    def test_evaluation_includes_source_quote(self):
        mock_llm = MagicMock()
        question = _make_question()

        mock_llm.complete.return_value = json.dumps(
            {
                "score": "incorrect",
                "correct_elements": [],
                "missing_or_wrong": ["wrong dose"],
                "source_quote": "Adrenaline 1mg IV/IO every 3-5 minutes.",
                "feedback_summary": "Incorrect.",
            }
        )

        result = evaluate_answer(
            question=question,
            user_answer="5mg",
            elapsed_seconds=10.0,
            llm=mock_llm,
        )
        assert "1mg" in result.source_quote


class TestCitationAccuracy:
    def test_generated_question_includes_source_citation(self):
        chunks = [
            RetrievedChunk(
                content="CMG 14.1: Adult cardiac arrest. Defibrillation 200J biphasic.",
                source_type="cmg",
                source_file="cmg_14.json",
                source_rank=0,
                category="Cardiac",
                cmg_number="14",
                chunk_type="protocol",
                relevance_score=-0.05,
            )
        ]

        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps(
            {
                "question_text": "What is the defibrillation energy for adult cardiac arrest?",
                "question_type": "recall",
                "source_citation": "ACTAS CMG 14.1",
                "category": "Cardiac",
            }
        )

        mock_retriever_citation = MagicMock()
        mock_retriever_citation.retrieve.return_value = chunks
        mock_retriever_citation.get_random_chunk.return_value = None
        question = generate_question(
            mode="random",
            llm=mock_llm,
            retriever=mock_retriever_citation,
            tracker=MagicMock(),
        )

        assert question.source_citation
        assert len(question.source_citation) > 3

    def test_evaluation_includes_source_quote(self):
        chunks = [
            RetrievedChunk(
                content="Defibrillation 200J biphasic for adult VF cardiac arrest.",
                source_type="cmg",
                source_file="cmg_14.json",
                source_rank=0,
                category="Cardiac",
                cmg_number="14",
                chunk_type="protocol",
                relevance_score=-0.05,
            )
        ]
        question = Question(
            id="q-test",
            question_text="What is the defibrillation dose?",
            question_type="recall",
            source_chunks=chunks,
            source_citation="ACTAS CMG 14.1",
            difficulty="medium",
            category="Cardiac",
        )

        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps(
            {
                "score": "correct",
                "correct_elements": ["200J biphasic"],
                "missing_or_wrong": [],
                "source_quote": "Defibrillation 200J biphasic for adult VF cardiac arrest.",
                "feedback_summary": "Correct.",
            }
        )

        evaluation = evaluate_answer(
            question=question,
            user_answer="200J biphasic",
            elapsed_seconds=30.0,
            llm=mock_llm,
        )

        assert evaluation.source_quote
        assert "200J" in evaluation.source_quote
        assert evaluation.source_citation == "ACTAS CMG 14.1"


def test_random_injection_suppressed_in_topic_mode():
    """Random injection must never fire in topic mode."""
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()
    mock_tracker.get_recent_chunk_keys.return_value = set()
    mock_tracker.get_chunk_scores.return_value = {}
    mock_retriever.retrieve.return_value = _make_chunks()
    mock_llm.complete.return_value = json.dumps({
        "question_text": "Q?",
        "question_type": "recall",
        "source_citation": "CMG 14",
        "category": "Cardiac",
        "source_index": 1,
    })

    for _ in range(50):
        generate_question(
            mode="topic",
            topic="Cardiac",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

    # get_random_chunk must never have been called
    mock_retriever.get_random_chunk.assert_not_called()


def test_random_injection_fires_in_random_mode():
    """In random mode, get_random_chunk should be called at least once across 200 calls."""
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()
    mock_tracker.get_recent_chunk_keys.return_value = set()
    mock_tracker.get_chunk_scores.return_value = {}
    mock_retriever.retrieve.return_value = _make_chunks()
    mock_retriever.get_random_chunk.return_value = None  # fallback to normal path
    mock_llm.complete.return_value = json.dumps({
        "question_text": "Q?",
        "question_type": "recall",
        "source_citation": "CMG 14",
        "category": "Cardiac",
        "source_index": 1,
    })

    for _ in range(200):
        generate_question(
            mode="random",
            llm=mock_llm,
            retriever=mock_retriever,
            tracker=mock_tracker,
        )

    call_count = mock_retriever.get_random_chunk.call_count
    # Expect roughly 50 calls (25%) — accept 15–85 as the valid range
    assert 15 <= call_count <= 85, f"Expected ~50 injection calls, got {call_count}"


def test_tracker_passed_to_retrieve_in_topic_mode():
    """tracker must be forwarded to retrieve() in all modes."""
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()
    mock_tracker.get_recent_chunk_keys.return_value = set()
    mock_tracker.get_chunk_scores.return_value = {}
    mock_retriever.retrieve.return_value = _make_chunks()
    mock_llm.complete.return_value = json.dumps({
        "question_text": "Q?",
        "question_type": "recall",
        "source_citation": "CMG 14",
        "category": "Cardiac",
        "source_index": 1,
    })

    generate_question(
        mode="topic",
        topic="Cardiac",
        llm=mock_llm,
        retriever=mock_retriever,
        tracker=mock_tracker,
    )

    # Every retrieve() call must have received tracker=mock_tracker
    for call in mock_retriever.retrieve.call_args_list:
        assert call.kwargs.get("tracker") is mock_tracker or (
            len(call.args) >= 9 and call.args[8] is mock_tracker
        ), f"retrieve() called without tracker: {call}"
