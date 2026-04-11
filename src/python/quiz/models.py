from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    content: str
    source_type: str
    source_file: str
    source_rank: int
    category: str | None = None
    cmg_number: str | None = None
    chunk_type: str | None = None
    relevance_score: float


class Question(BaseModel):
    id: str
    question_text: str
    question_type: str
    source_chunks: list[RetrievedChunk]
    source_citation: str
    difficulty: str
    category: str
    primary_chunk_index: int = 0


class Evaluation(BaseModel):
    score: str | None = None
    correct_elements: list[str] = []
    missing_or_wrong: list[str] = []
    source_quote: str = ""
    source_citation: str = ""
    feedback_summary: str | None = None
    response_time_seconds: float = 0.0


class CategoryMastery(BaseModel):
    category: str
    total_attempts: int
    correct: int
    partial: int
    incorrect: int
    mastery_percent: float
    status: str


class QuizAttempt(BaseModel):
    id: int
    question_id: str
    category: str
    question_type: str
    score: str | None
    elapsed_seconds: float
    source_citation: str
    created_at: str


class SessionConfig(BaseModel):
    mode: str
    topic: str | None = None
    guideline_id: str | None = None
    difficulty: str = "medium"
    blacklist: list[str] = []
    randomize: bool = True
    asked_question_ids: list[str] = []
    asked_chunk_contents: list[str] = []
