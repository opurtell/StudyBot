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

        question = generate_question(
            mode="random",
            llm=mock_llm,
            retriever=MagicMock(),
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
