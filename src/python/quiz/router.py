from __future__ import annotations

import threading
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm.base import LLMClient
from llm.factory import create_client_for_model, load_config
from seed import is_seeding_complete

from .agent import generate_question
from .agent import evaluate_answer
from .models import Evaluation, SessionConfig
from .retriever import Retriever, get_retriever as get_shared_retriever
from .store import (
    get_question,
    get_session,
    store_question,
    store_session,
    record_asked,
)
from .tracker import Tracker

router = APIRouter(prefix="/quiz", tags=["quiz"])

_retriever: Retriever | None = None
_tracker: Tracker | None = None
_tracker_lock = threading.Lock()


def _get_llm(model_id: str) -> LLMClient:
    config = load_config()
    return create_client_for_model(config, model_id)


def _get_quiz_model() -> str:
    config = load_config()
    return config.get("quiz_model", "claude-haiku-4-5-20251001")


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = get_shared_retriever()
    return _retriever


def _get_tracker() -> Tracker:
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = Tracker()
    return _tracker


def _check_seeding() -> None:
    if not is_seeding_complete():
        raise HTTPException(status_code=503, detail="CMG index is still seeding. Please try again in a moment.")


def warm_quiz_dependencies() -> None:
    _get_retriever()
    _get_tracker()


class StartSessionRequest(BaseModel):
    mode: str
    topic: Optional[str] = None
    difficulty: str = "medium"
    randomize: bool = True


class GenerateQuestionRequest(BaseModel):
    session_id: str


class EvaluateRequest(BaseModel):
    question_id: str
    user_answer: Optional[str] = None
    elapsed_seconds: float


class BlacklistRequest(BaseModel):
    category_name: str


@router.post("/session/start")
def start_session(req: StartSessionRequest) -> dict:
    session_id = str(uuid.uuid4())
    tracker = _get_tracker()
    blacklist = tracker.get_blacklist()
    config = SessionConfig(
        mode=req.mode,
        topic=req.topic,
        difficulty=req.difficulty,
        blacklist=blacklist,
        randomize=req.randomize,
    )
    store_session(session_id, config)
    return {
        "session_id": session_id,
        "mode": req.mode,
        "blacklist": blacklist,
    }


@router.post("/question/generate")
def generate(req: GenerateQuestionRequest) -> dict:
    _check_seeding()
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    quiz_model = _get_quiz_model()
    config = load_config()
    skill_level = config.get("skill_level", "AP")

    previous_texts: list[str] = []
    for qid in session.asked_question_ids:
        q = get_question(qid)
        if q:
            previous_texts.append(q.question_text)

    question = generate_question(
        mode=session.mode,
        topic=session.topic,
        blacklist=session.blacklist,
        difficulty=session.difficulty,
        llm=_get_llm(quiz_model),
        retriever=_get_retriever(),
        tracker=_get_tracker(),
        skill_level=skill_level,
        randomize=session.randomize,
        previous_questions=previous_texts if previous_texts else None,
        used_chunk_contents=session.asked_chunk_contents
        if session.asked_chunk_contents
        else None,
    )
    store_question(question)
    record_asked(req.session_id, question)

    return {
        "question_id": question.id,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "category": question.category,
        "difficulty": question.difficulty,
        "source_citation": question.source_citation,
    }


@router.post("/question/evaluate")
def evaluate(req: EvaluateRequest) -> dict:
    question = get_question(req.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    quiz_model = _get_quiz_model()
    evaluation = evaluate_answer(
        question=question,
        user_answer=req.user_answer,
        elapsed_seconds=req.elapsed_seconds,
        llm=_get_llm(quiz_model),
    )

    tracker = _get_tracker()
    tracker.record_answer(
        question_id=question.id,
        category=question.category,
        question_type=question.question_type,
        score=evaluation.score,
        elapsed_seconds=req.elapsed_seconds,
        source_citation=question.source_citation,
    )

    return {
        "score": evaluation.score,
        "correct_elements": evaluation.correct_elements,
        "missing_or_wrong": evaluation.missing_or_wrong,
        "source_quote": evaluation.source_quote,
        "source_citation": evaluation.source_citation,
        "feedback_summary": evaluation.feedback_summary,
        "model_id": quiz_model,
    }


@router.get("/mastery")
def mastery() -> list[dict]:
    tracker = _get_tracker()
    return [m.model_dump() for m in tracker.get_mastery()]


@router.get("/streak")
def streak() -> dict:
    tracker = _get_tracker()
    return {
        "streak": tracker.get_streak(),
        "accuracy": tracker.get_accuracy(),
    }


@router.get("/history")
def history(limit: int = 20, offset: int = 0) -> list[dict]:
    tracker = _get_tracker()
    return [
        h.model_dump() for h in tracker.get_recent_history(limit=limit, offset=offset)
    ]


@router.get("/blacklist")
def get_blacklist() -> list[str]:
    tracker = _get_tracker()
    return tracker.get_blacklist()


@router.post("/blacklist")
def add_blacklist(req: BlacklistRequest) -> dict:
    tracker = _get_tracker()
    tracker.add_to_blacklist(req.category_name)
    return {"status": "ok"}


@router.delete("/blacklist/{category}")
def remove_blacklist(category: str) -> dict:
    tracker = _get_tracker()
    tracker.remove_from_blacklist(category)
    return {"status": "ok"}
