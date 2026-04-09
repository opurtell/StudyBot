from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from llm.factory import load_config
from quiz.models import (
    Question,
    RetrievedChunk,
    Evaluation,
    CategoryMastery,
    SessionConfig,
)

TEST_CONFIG = load_config("config/settings.example.json")


@pytest.fixture(autouse=True)
def _clean_store():
    from quiz import store

    store.clear_all()
    yield
    store.clear_all()


@pytest.fixture
def mock_deps():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()

    with (
        patch("quiz.router._get_llm", return_value=mock_llm),
        patch("quiz.router._get_retriever", return_value=mock_retriever),
        patch("quiz.router._get_tracker", return_value=mock_tracker),
        patch("quiz.router.load_config", return_value=TEST_CONFIG),
        patch("quiz.router.is_seeding_complete", return_value=True),
    ):
        yield {"llm": mock_llm, "retriever": mock_retriever, "tracker": mock_tracker}


@pytest.fixture
def client(mock_deps):
    from fastapi import FastAPI
    from quiz.router import router as quiz_router

    _app = FastAPI()
    _app.include_router(quiz_router)
    return TestClient(_app)


def _make_question():
    return Question(
        id="q-1",
        question_text="What is the adrenaline dose?",
        question_type="drug_dose",
        source_chunks=[
            RetrievedChunk(
                content="Adrenaline 1mg IV.",
                source_type="cmg",
                source_file="cmg_14.json",
                source_rank=0,
                category="Cardiac",
                cmg_number="14",
                chunk_type="protocol",
                relevance_score=0.95,
            )
        ],
        source_citation="ACTAS CMG 14.1",
        difficulty="medium",
        category="Cardiac",
    )


class TestSessionStart:
    def test_start_session_returns_200(self, client):
        response = client.post(
            "/quiz/session/start",
            json={
                "mode": "random",
                "topic": None,
                "difficulty": "medium",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["mode"] == "random"

    def test_start_topic_session_returns_200(self, client):
        response = client.post(
            "/quiz/session/start",
            json={
                "mode": "topic",
                "topic": "Medicine",
                "difficulty": "medium",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "topic"

    def test_start_clinical_guidelines_session_returns_200(self, client):
        response = client.post(
            "/quiz/session/start",
            json={
                "mode": "clinical_guidelines",
                "topic": None,
                "difficulty": "medium",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "clinical_guidelines"


class TestGenerateQuestion:
    def test_generate_returns_question(self, client, mock_deps):
        with patch("quiz.router.generate_question", return_value=_make_question()):
            start = client.post("/quiz/session/start", json={"mode": "random"})
            session_id = start.json()["session_id"]
            response = client.post(
                "/quiz/question/generate", json={"session_id": session_id}
            )
            assert response.status_code == 200
            data = response.json()
            assert "question_id" in data
            assert data["question_text"]


class TestEvaluate:
    def test_evaluate_answer(self, client, mock_deps):
        question = _make_question()
        from quiz import store

        store.store_question(question)

        evaluation = Evaluation(
            score="correct",
            correct_elements=["1mg IV"],
            missing_or_wrong=[],
            source_quote="Adrenaline 1mg IV.",
            source_citation="ACTAS CMG 14.1",
            feedback_summary="Correct.",
            response_time_seconds=45.0,
        )
        with patch("quiz.router.evaluate_answer", return_value=evaluation):
            response = client.post(
                "/quiz/question/evaluate",
                json={
                    "question_id": "q-1",
                    "user_answer": "1mg IV",
                    "elapsed_seconds": 45.0,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["score"] == "correct"

    def test_evaluate_reveal(self, client, mock_deps):
        question = _make_question()
        from quiz import store

        store.store_question(question)

        evaluation = Evaluation(
            score=None,
            source_quote="Adrenaline 1mg IV.",
            source_citation="ACTAS CMG 14.1",
            response_time_seconds=12.0,
        )
        with patch("quiz.router.evaluate_answer", return_value=evaluation):
            response = client.post(
                "/quiz/question/evaluate",
                json={
                    "question_id": "q-1",
                    "user_answer": None,
                    "elapsed_seconds": 12.0,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["score"] is None


class TestMastery:
    def test_get_mastery(self, client, mock_deps):
        mock_tracker = mock_deps["tracker"]
        mock_tracker.get_mastery.return_value = [
            CategoryMastery(
                category="Cardiac",
                total_attempts=5,
                correct=3,
                partial=1,
                incorrect=1,
                mastery_percent=70.0,
                status="developing",
            )
        ]
        response = client.get("/quiz/mastery")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestHistory:
    def test_history_passes_limit_and_offset(self, client, mock_deps):
        mock_tracker = mock_deps["tracker"]
        mock_tracker.get_recent_history.return_value = []

        response = client.get("/quiz/history?limit=5&offset=10")

        assert response.status_code == 200
        mock_tracker.get_recent_history.assert_called_once_with(limit=5, offset=10)


class TestBlacklist:
    def test_get_blacklist(self, client, mock_deps):
        mock_tracker = mock_deps["tracker"]
        mock_tracker.get_blacklist.return_value = ["Paediatrics"]
        response = client.get("/quiz/blacklist")
        assert response.status_code == 200
        assert response.json() == ["Paediatrics"]

    def test_add_to_blacklist(self, client, mock_deps):
        response = client.post("/quiz/blacklist", json={"category_name": "Paediatrics"})
        assert response.status_code == 200

    def test_remove_from_blacklist(self, client, mock_deps):
        response = client.delete("/quiz/blacklist/Paediatrics")
        assert response.status_code == 200


class TestSeedingGuard:
    def test_generate_returns_503_when_seeding(self, client, mock_deps, monkeypatch):
        from seed import _seeding_complete

        _seeding_complete.clear()
        monkeypatch.setattr("quiz.router.is_seeding_complete", lambda: False)

        response = client.post(
            "/quiz/question/generate",
            json={"session_id": "test"},
        )
        assert response.status_code == 503
        assert "seeding" in response.json()["detail"].lower()


class TestClearMastery:
    def test_clear_mastery(self, client, mock_deps):
        mock_tracker = mock_deps["tracker"]

        # Configure the mock tracker to return seeded mastery data
        from quiz.models import CategoryMastery

        mock_tracker.get_mastery.return_value = [
            CategoryMastery(
                category="Cardiac",
                total_attempts=1,
                correct=1,
                partial=0,
                incorrect=0,
                mastery_percent=100.0,
                status="mastered",
            )
        ]

        # Configure the mock to return deleted count
        mock_tracker.clear_mastery_data.return_value = 1

        # Start a session (required for router init)
        client.post("/quiz/session/start", json={"mode": "random"})

        # Clear mastery data
        response = client.post("/quiz/mastery/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["deleted_history"] == 1

        # Verify clear_mastery_data was called
        mock_tracker.clear_mastery_data.assert_called_once()
