import time

from .models import Question, SessionConfig

_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours
_CLEANUP_INTERVAL_SECONDS = 5 * 60  # run cleanup at most every 5 minutes

_questions: dict[str, Question] = {}
_sessions: dict[str, SessionConfig] = {}
_question_timestamps: dict[str, float] = {}
_session_timestamps: dict[str, float] = {}
_last_cleanup: float = 0.0


def _cleanup_stale() -> None:
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
        return
    _last_cleanup = now

    cutoff = now - _MAX_AGE_SECONDS

    stale_sessions = [
        sid for sid, ts in _session_timestamps.items() if ts < cutoff
    ]
    for sid in stale_sessions:
        _sessions.pop(sid, None)
        _session_timestamps.pop(sid, None)

    stale_questions = [
        qid for qid, ts in _question_timestamps.items() if ts < cutoff
    ]
    for qid in stale_questions:
        _questions.pop(qid, None)
        _question_timestamps.pop(qid, None)


def store_question(question: Question) -> None:
    _cleanup_stale()
    _questions[question.id] = question
    _question_timestamps[question.id] = time.time()


def get_question(question_id: str) -> Question | None:
    return _questions.get(question_id)


def store_session(session_id: str, config: SessionConfig) -> None:
    _cleanup_stale()
    _sessions[session_id] = config
    _session_timestamps[session_id] = time.time()


def get_session(session_id: str) -> SessionConfig | None:
    return _sessions.get(session_id)


def record_asked(session_id: str, question: Question) -> None:
    session = _sessions.get(session_id)
    if session is None:
        return
    session.asked_question_ids.append(question.id)
    for chunk in question.source_chunks:
        content_key = chunk.content[:200]
        if content_key not in session.asked_chunk_contents:
            session.asked_chunk_contents.append(content_key)


def clear_all() -> None:
    global _last_cleanup
    _questions.clear()
    _sessions.clear()
    _question_timestamps.clear()
    _session_timestamps.clear()
    _last_cleanup = 0.0
