# Phase 4: Quiz Agent — Design Specification

**Date:** 2026-04-02
**Status:** Draft
**Depends on:** ChromaDB collections (populated), FastAPI skeleton, existing design system

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| Architecture | Direct RAG pipeline (Approach A) |
| Session model | Open-ended, ephemeral (discard on close) |
| Question selection | Three modes: user-chosen topic, gap-driven, random |
| Scoring | 3-tier: Correct / Partially Correct / Incorrect |
| LLM usage | Same model for generation and evaluation |
| Self-grading | Both paths (answer or reveal) always available |
| History persistence | SQLite (quiz history survives; active sessions do not) |

---

## 1. LLM Provider Abstraction

**Module:** `src/python/llm/`

A single interface wrapping Anthropic, Google, and Z.ai. A factory reads `settings.json` and returns the active provider's client.

### Config Shape

`config/settings.json`:

```json
{
  "providers": {
    "anthropic": { "api_key": "", "default_model": "claude-haiku-4-5" },
    "google": { "api_key": "", "default_model": "gemini-2.0-flash" },
    "zai": { "api_key": "", "default_model": "glm-4-flash" }
  },
  "active_provider": "anthropic",
  "quiz_model": "claude-haiku-4-5",
  "clean_model": "claude-opus-4-5"
}
```

### Interface

```python
class LLMClient:
    def complete(self, messages: list[dict], model: str | None = None) -> str
    def get_provider(self) -> str
    def list_models(self) -> list[str]
```

Each provider is a submodule (`anthropic.py`, `google.py`, `zai.py`) translating the generic `complete()` call into the provider's SDK call.

### Error Handling

Provider-specific errors are wrapped into a common `LLMError` with categories: `rate_limit`, `auth`, `timeout`, `unknown`. The quiz agent inspects the category to decide whether to retry, surface a message, or fall back.

### New Dependencies

- `anthropic` (Anthropic SDK)
- `google-generativeai` (Google Gemini SDK)
- `zhipuai` (Z.ai/GLM SDK)

---

## 2. RAG Retrieval Layer

**Module:** `src/python/quiz/retriever.py`

Queries both ChromaDB collections (`paramedic_notes` and `cmg_guidelines`) and merges results respecting source hierarchy: CMGs > REFdocs > CPDdocs > Notability Notes.

### Interface

```python
class Retriever:
    def retrieve(
        self,
        query: str,
        n: int = 5,
        filters: dict | None = None,
        exclude_categories: list[str] | None = None
    ) -> list[RetrievedChunk]
```

### Data Model

```python
class RetrievedChunk(BaseModel):
    content: str
    source_type: str          # "cmg", "ref_doc", "cpd_doc", "notability_note"
    source_file: str
    source_rank: int          # 0=CMG, 1=REFdoc, 2=CPDdoc, 3=Notability
    category: str | None
    cmg_number: str | None
    chunk_type: str | None
    relevance_score: float
```

### Retrieval Flow

1. Query both collections with `n` results each
2. Merge into a single list
3. Assign `source_rank` based on `source_type`
4. Sort by `(source_rank, relevance_score)` — source hierarchy first, relevance within each tier
5. Return top `n` across both collections

### Filter Mapping

Filters map directly to ChromaDB `where` clauses:

| Quiz mode | Filter |
|-----------|--------|
| User-chosen topic | `{"section": "Cardiac"}` or `{"categories": {"$contains": "Cardiac"}}` |
| Drug dose questions | `{"source_type": "cmg", "chunk_type": "dosage"}` |
| Gap-driven | No category filter; uses weak categories as query terms |

### Blacklist

`exclude_categories` adds `$nin` clauses to the ChromaDB query filter.

---

## 3. Quiz Agent — Generation and Evaluation

**Module:** `src/python/quiz/agent.py`

### Data Models

```python
class Question(BaseModel):
    id: str                       # uuid
    question_text: str
    question_type: str            # "recall" | "definition" | "scenario" | "drug_dose"
    source_chunks: list[RetrievedChunk]  # server-side only, not sent to client
    source_citation: str          # e.g. "Ref: ACTAS CMG 14.1 — Cardiac Arrest"
    difficulty: str               # "easy" | "medium" | "hard"
    category: str

class Evaluation(BaseModel):
    score: str | None             # "correct" | "partial" | "incorrect" | None (reveal)
    correct_elements: list[str]
    missing_or_wrong: list[str]
    source_quote: str             # exact relevant snippet from source
    source_citation: str
    feedback_summary: str | None  # 2-3 sentence clinical feedback; null on reveal
    response_time_seconds: float
```

### Question Generation

```python
def generate_question(
    mode: str,                    # "topic" | "gap_driven" | "random"
    topic: str | None = None,
    blacklist: list[str] | None = None,
    difficulty: str = "medium"
) -> Question
```

**Flow:**

1. Determine search query based on mode:
   - **topic:** query = user's chosen topic string, filter to matching category/section
   - **gap_driven:** query tracker for weakest categories, use those as search terms
   - **random:** pick a random category from available ChromaDB metadata, use as query
2. Call `Retriever.retrieve()` with filters and blacklist
3. Pass retrieved chunks + system prompt to `LLMClient.complete()`
4. Parse LLM output into a `Question`

**System prompt rules:**
- Generate one question from the provided source material
- Question must be answerable from the source text alone
- Never fabricate clinical information
- Vary question type across questions
- Australian English (adrenaline, haemorrhage, colour)
- Tone: direct, clinical, not casual

### Answer Evaluation

```python
def evaluate_answer(
    question: Question,
    user_answer: str | None,      # None = self-graded reveal path
    elapsed_seconds: float
) -> Evaluation
```

**Flow:**

1. If `user_answer` is None (reveal path): score = `None`, return source text as feedback, `feedback_summary` = null
2. Otherwise, pass question + source chunks + user answer + system prompt to LLM
3. Parse into `Evaluation`

**System prompt rules:**
- Compare answer against source material only — never against general knowledge
- Score conservatively: "partial" if anything material is wrong or missing
- Cite the exact source text as `source_quote`
- Australian English
- Tone: supportive expert, straightforward, not chatty

### Server-Side Stores

Two in-memory dicts, both discarded on app restart (matching the ephemeral session model):

**Question store** (`dict[str, Question]`): Keyed by `question_id`. Holds source chunks for evaluation without exposing them to the client.

**Session store** (`dict[str, SessionConfig]`): Keyed by `session_id`. Holds the mode, topic, difficulty, and blacklist for the active session so that `/quiz/question/generate` only needs the `session_id` to produce the next question.

```python
class SessionConfig(BaseModel):
    mode: str                    # "topic" | "gap_driven" | "random"
    topic: str | None
    difficulty: str
    blacklist: list[str]
```

---

## 4. Knowledge Tracking (SQLite)

**Module:** `src/python/quiz/tracker.py`

SQLite database at `data/mastery.db`.

### Schema

```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    section TEXT
);

CREATE TABLE quiz_history (
    id INTEGER PRIMARY KEY,
    question_id TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    question_type TEXT,
    score TEXT,
    elapsed_seconds REAL,
    source_citation TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE blacklist (
    id INTEGER PRIMARY KEY,
    category_name TEXT UNIQUE NOT NULL
);
```

### Interface

```python
class Tracker:
    def record_answer(self, question_id, category, question_type, score, elapsed_seconds, source_citation) -> None
    def get_mastery(self) -> list[CategoryMastery]
    def get_weak_categories(self, n: int = 3) -> list[str]
    def get_streak(self) -> int
    def get_accuracy(self) -> float
    def get_recent_history(self, limit: int = 20) -> list[QuizAttempt]
    def add_to_blacklist(self, category_name: str) -> None
    def remove_from_blacklist(self, category_name: str) -> None
    def get_blacklist(self) -> list[str]
```

### Mastery Calculation

```python
class CategoryMastery(BaseModel):
    category: str
    total_attempts: int
    correct: int
    partial: int
    incorrect: int
    mastery_percent: float      # (correct + partial*0.5) / total * 100
    status: str                 # "strong" (>75%), "developing" (50-75%), "weak" (<50%)
```

### Key Behaviours

- Categories auto-created on first recorded answer (no upfront seeding)
- `get_weak_categories()` returns categories sorted by mastery ascending — feeds gap-driven mode
- Streak counts consecutive "correct" scores, resets on any other result
- Self-graded reveals (score=NULL) are recorded but excluded from mastery calculation
- Tracker is a singleton, initialised once at app startup

---

## 5. API Endpoints

**Module:** `src/python/quiz/router.py`

All endpoints under `/quiz/`.

### Endpoint Table

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/quiz/session/start` | Start a new session |
| `POST` | `/quiz/question/generate` | Generate next question |
| `POST` | `/quiz/question/evaluate` | Evaluate answer or reveal source |
| `GET` | `/quiz/mastery` | All category mastery scores |
| `GET` | `/quiz/streak` | Current streak + accuracy |
| `GET` | `/quiz/history` | Recent quiz attempts (paginated, query param `?limit=20&offset=0`) |
| `GET` | `/quiz/blacklist` | Current blacklist |
| `POST` | `/quiz/blacklist` | Add to blacklist |
| `DELETE` | `/quiz/blacklist/{category}` | Remove from blacklist |

### Request/Response Shapes

**Start session:**
```json
// POST /quiz/session/start
{
  "mode": "gap_driven",
  "topic": null,
  "difficulty": "medium"
}
// Response
{
  "session_id": "uuid",
  "mode": "gap_driven",
  "blacklist": ["Paediatrics"]
}
```

**Generate question:**
```json
// POST /quiz/question/generate
{
  "session_id": "uuid"
}
// Response
{
  "question_id": "uuid",
  "question_text": "Describe the recommended adrenaline dosing for an adult cardiac arrest.",
  "question_type": "drug_dose",
  "category": "Cardiac",
  "difficulty": "medium",
  "source_citation": "ACTAS CMG 14.1"
}
```

**Evaluate (answer path):**
```json
// POST /quiz/question/evaluate
{
  "question_id": "uuid",
  "user_answer": "1mg IV push every 3-5 minutes",
  "elapsed_seconds": 45.2
}
// Response
{
  "score": "correct",
  "correct_elements": ["1mg IV push", "every 3-5 minutes"],
  "missing_or_wrong": [],
  "source_quote": "Adrenaline 1 mg IV/IO, repeated every 3-5 minutes during cardiac arrest.",
  "source_citation": "ACTAS CMG 14.1",
  "feedback_summary": "Correct. Adrenaline 1mg IV/IO at 3-5 minute intervals per CMG 14.1."
}
```

**Evaluate (reveal path):**
```json
// POST /quiz/question/evaluate
{
  "question_id": "uuid",
  "user_answer": null,
  "elapsed_seconds": 12.0
}
// Response
{
  "score": null,
  "correct_elements": [],
  "missing_or_wrong": [],
  "source_quote": "Adrenaline 1 mg IV/IO, repeated every 3-5 minutes during cardiac arrest.",
  "source_citation": "ACTAS CMG 14.1",
  "feedback_summary": null
}
```

### Client-Side Session Model

The client holds `session_id` and `question_id` in React state. No server-side session store. The session concept is the client remembering its mode and feeding it to each generate call. History recording happens server-side via the tracker on each evaluate call.

---

## Module Summary

| Module | Path | New/Existing |
|--------|------|-------------|
| LLM abstraction | `src/python/llm/` | New (stub exists) |
| Retriever | `src/python/quiz/retriever.py` | New |
| Quiz agent | `src/python/quiz/agent.py` | New |
| Knowledge tracker | `src/python/quiz/tracker.py` | New |
| Quiz router | `src/python/quiz/router.py` | New |
| Settings migration | `config/settings.json` | Extend existing |

All modules live under `src/python/quiz/` (stub directory already exists) and `src/python/llm/` (stub directory already exists). The FastAPI app in `src/python/main.py` will include the quiz router.
