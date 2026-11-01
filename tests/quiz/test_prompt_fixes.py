import json
import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm.factory import load_config
from quiz.agent import (
    EVALUATION_SYSTEM_PROMPT,
    EvaluationParseError,
    build_generation_prompt,
    evaluate_answer,
    generate_question,
)
from quiz.models import Question, RetrievedChunk
from services.registry import get_service

TEST_CONFIG = load_config("config/settings.example.json")

CHUNK_TEXTS = [
    "CMG 4 Cardiac Arrest: Adrenaline 1 mg IV/IO every 3-5 minutes.",
    "CMG 7 Anaphylaxis: Adrenaline 500 microg IM, repeat every 5 minutes.",
    "CMG 14 Asthma: Salbutamol 5 mg nebulised, repeat as required.",
]


def _chunk(text: str, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        content=text,
        source_type="cmg",
        source_file=f"cmg_{rank}.json",
        source_rank=0,
        category="Cardiac",
        cmg_number=str(rank),
        chunk_type="protocol",
        relevance_score=0.9,
    )


def _chunks() -> list[RetrievedChunk]:
    return [_chunk(t, i) for i, t in enumerate(CHUNK_TEXTS)]


def _question(primary: int) -> Question:
    return Question(
        id="q-primary",
        question_text="What is the salbutamol dose for asthma?",
        question_type="drug_dose",
        source_chunks=_chunks(),
        source_citation="ACTAS CMG 14",
        difficulty="medium",
        category="Respiratory",
        primary_chunk_index=primary,
    )


def _json_example(prompt: str) -> dict:
    match = re.search(r"Respond with valid JSON only:\n(\{.*\})", prompt, re.DOTALL)
    assert match, prompt
    return json.loads(match.group(1))


class TestGenerationPromptRendering:
    @pytest.mark.parametrize("service_id", ["actas", "at"])
    def test_json_example_is_valid_json_with_rendered_citation(self, service_id):
        svc = get_service(service_id)
        with patch("services.active.active_service", return_value=svc):
            prompt = build_generation_prompt(frozenset({"AP"}))

        example = _json_example(prompt)
        assert example["source_citation"] == f"e.g. {svc.short_name} CMG 14.1"
        assert set(example) == {
            "question_text",
            "question_type",
            "source_citation",
            "category",
            "source_index",
        }

    @pytest.mark.parametrize("quals", [frozenset({"AP"}), frozenset({"AP", "ICP"})])
    def test_no_template_syntax_leaks(self, quals):
        with patch("services.active.active_service", return_value=get_service("actas")):
            prompt = build_generation_prompt(quals)

        assert 'f"' not in prompt
        assert "{svc" not in prompt
        assert "{{" not in prompt and "}}" not in prompt

    def test_prompt_ties_question_to_single_source(self):
        with patch("services.active.active_service", return_value=get_service("actas")):
            prompt = build_generation_prompt()

        assert "answerable from that one source alone" in prompt


class TestMarksAgainstPrimaryChunk:
    @pytest.mark.parametrize("primary", [0, 1, 2])
    def test_only_primary_chunk_reaches_the_marker(self, primary):
        llm = MagicMock()
        llm.complete.return_value = json.dumps(
            {
                "score": "correct",
                "correct_elements": ["dose"],
                "missing_or_wrong": [],
                "source_quote": CHUNK_TEXTS[primary],
                "feedback_summary": "Correct.",
            }
        )

        evaluate_answer(_question(primary), "5 mg", 10.0, llm)

        user_msg = llm.complete.call_args[0][0][1]["content"]
        assert CHUNK_TEXTS[primary] in user_msg
        for i, text in enumerate(CHUNK_TEXTS):
            if i != primary:
                assert text not in user_msg

    def test_out_of_range_index_falls_back_to_first_chunk(self):
        llm = MagicMock()
        llm.complete.return_value = json.dumps({"score": "partial"})

        evaluate_answer(_question(9), "5 mg", 10.0, llm)

        user_msg = llm.complete.call_args[0][0][1]["content"]
        assert CHUNK_TEXTS[0] in user_msg
        assert CHUNK_TEXTS[2] not in user_msg

    def test_string_source_index_is_honoured(self):
        llm = MagicMock()
        retriever = MagicMock()
        retriever.retrieve.return_value = _chunks()
        llm.complete.return_value = json.dumps(
            {"question_text": "Q?", "source_index": "3"}
        )

        with patch("services.active.active_service", return_value=get_service("actas")):
            q = generate_question(
                mode="topic",
                topic="Respiratory",
                llm=llm,
                retriever=retriever,
                tracker=MagicMock(),
                randomize=False,
            )

        assert q.primary_chunk_index == 2


class TestParseFailures:
    @pytest.mark.parametrize(
        "reply",
        [
            "Sorry, I cannot help with that.",
            "",
            "{not json",
            json.dumps({"feedback_summary": "No score here."}),
            json.dumps({"score": "mostly right"}),
            json.dumps(["correct"]),
        ],
    )
    def test_unreadable_reply_raises_instead_of_scoring_incorrect(self, reply):
        llm = MagicMock()
        llm.complete.return_value = reply

        with pytest.raises(EvaluationParseError):
            evaluate_answer(_question(0), "1 mg", 10.0, llm)

    def test_reveal_path_never_calls_the_marker(self):
        llm = MagicMock()

        result = evaluate_answer(_question(1), None, 4.0, llm)

        llm.complete.assert_not_called()
        assert result.score is None
        assert result.source_quote == CHUNK_TEXTS[1]

    def test_non_list_elements_are_dropped(self):
        llm = MagicMock()
        llm.complete.return_value = json.dumps(
            {"score": "partial", "correct_elements": "dose", "missing_or_wrong": None}
        )

        result = evaluate_answer(_question(0), "1 mg", 10.0, llm)

        assert result.score == "partial"
        assert result.correct_elements == []
        assert result.missing_or_wrong == []


@pytest.fixture
def router_env():
    from quiz import store
    from quiz.router import router as quiz_router

    store.clear_all()
    llm = MagicMock()
    retriever = MagicMock()
    tracker = MagicMock()
    tracker.get_recent_chunk_keys.return_value = set()
    with (
        patch("quiz.router._get_llm", return_value=llm),
        patch("quiz.router._get_retriever", return_value=retriever),
        patch("quiz.router._get_tracker", return_value=tracker),
        patch("quiz.router.load_config", return_value=TEST_CONFIG),
        patch("quiz.router.is_seeding_complete", return_value=True),
        patch("services.active.active_service", return_value=get_service("actas")),
    ):
        app = FastAPI()
        app.include_router(quiz_router)
        yield {
            "client": TestClient(app),
            "llm": llm,
            "retriever": retriever,
            "tracker": tracker,
        }
    store.clear_all()


def _generate_through_router(env, source_index: int) -> str:
    env["retriever"].retrieve.return_value = _chunks()
    env["llm"].complete.return_value = json.dumps(
        {
            "question_text": "What is the salbutamol dose for asthma?",
            "question_type": "drug_dose",
            "source_citation": "ACTAS CMG 14",
            "category": "Respiratory",
            "source_index": source_index,
        }
    )
    start = env["client"].post(
        "/quiz/session/start",
        json={"mode": "topic", "topic": "Respiratory", "randomize": False},
    )
    gen = env["client"].post(
        "/quiz/question/generate", json={"session_id": start.json()["session_id"]}
    )
    assert gen.status_code == 200, gen.text
    return gen.json()["question_id"]


class TestRouterWithRealStore:
    def test_primary_chunk_survives_store_and_is_the_only_one_marked(self, router_env):
        qid = _generate_through_router(router_env, source_index=3)

        router_env["llm"].complete.reset_mock()
        router_env["llm"].complete.return_value = json.dumps(
            {
                "score": "correct",
                "correct_elements": ["5 mg"],
                "missing_or_wrong": [],
                "source_quote": "Salbutamol 5 mg nebulised",
                "feedback_summary": "Correct.",
            }
        )
        res = router_env["client"].post(
            "/quiz/question/evaluate",
            json={"question_id": qid, "user_answer": "5 mg", "elapsed_seconds": 8},
        )

        assert res.status_code == 200
        messages = router_env["llm"].complete.call_args[0][0]
        assert messages[0]["content"].startswith(EVALUATION_SYSTEM_PROMPT)
        assert CHUNK_TEXTS[2] in messages[1]["content"]
        assert CHUNK_TEXTS[0] not in messages[1]["content"]
        assert CHUNK_TEXTS[1] not in messages[1]["content"]
        router_env["tracker"].record_answer.assert_called_once()

    def test_parse_failure_returns_502_and_is_not_recorded(self, router_env):
        qid = _generate_through_router(router_env, source_index=1)

        router_env["llm"].complete.return_value = "I think the answer is fine."
        res = router_env["client"].post(
            "/quiz/question/evaluate",
            json={"question_id": qid, "user_answer": "1 mg", "elapsed_seconds": 8},
        )

        assert res.status_code == 502
        assert "not scored" in res.json()["detail"]
        router_env["tracker"].record_answer.assert_not_called()
