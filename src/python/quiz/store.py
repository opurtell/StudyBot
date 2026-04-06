from .models import Question, SessionConfig

_questions: dict[str, Question] = {}
_sessions: dict[str, SessionConfig] = {}


def store_question(question: Question) -> None:
    _questions[question.id] = question


def get_question(question_id: str) -> Question | None:
    return _questions.get(question_id)


def store_session(session_id: str, config: SessionConfig) -> None:
    _sessions[session_id] = config


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
    _questions.clear()
    _sessions.clear()
