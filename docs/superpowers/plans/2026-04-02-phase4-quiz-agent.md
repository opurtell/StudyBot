# Phase 4: Quiz Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LLM-powered quiz generation and evaluation engine with RAG retrieval, mastery tracking, and API endpoints.

**Architecture:** Direct RAG pipeline — each question is generated live by retrieving chunks from ChromaDB and passing them to an LLM. Evaluations compare user answers against source material using the same LLM. Three selection modes (topic, gap-driven, random) feed into the same generate→answer→evaluate flow. Mastery data persists in SQLite; active sessions are ephemeral.

**Tech Stack:** Python 3.10+, FastAPI, ChromaDB, Pydantic, SQLite, Anthropic SDK, Google Generative AI SDK, ZhipuAI SDK

---

## File Structure

```
src/python/llm/
  __init__.py                     # Re-exports: LLMClient, LLMError, create_client, load_config
  base.py                         # LLMError, LLMClient Protocol
  anthropic_provider.py           # AnthropicProvider
  google_provider.py              # GoogleProvider
  zai_provider.py                 # ZaiProvider
  factory.py                      # create_client(), load_config()

src/python/quiz/
  __init__.py                     # Re-exports: Retriever, Tracker, generate_question, evaluate_answer
  models.py                       # RetrievedChunk, Question, Evaluation, CategoryMastery, SessionConfig, QuizAttempt
  retriever.py                    # Retriever class — queries both ChromaDB collections
  tracker.py                      # Tracker class — SQLite mastery/blacklist/history
  agent.py                        # generate_question(), evaluate_answer()
  store.py                        # In-memory question store + session store
  router.py                       # FastAPI APIRouter with all /quiz/* endpoints

src/python/main.py                # MODIFY: include quiz router

config/settings.json              # MODIFY: new multi-provider format
config/settings.example.json      # MODIFY: new multi-provider format
pyproject.toml                    # MODIFY: add LLM SDK dependencies

tests/llm/__init__.py             # Empty
tests/llm/test_factory.py         # Factory + config loading tests
tests/llm/test_anthropic_provider.py  # Anthropic provider tests
tests/llm/test_google_provider.py     # Google provider tests
tests/llm/test_zai_provider.py        # Z.ai provider tests

tests/quiz/__init__.py            # Empty
tests/quiz/conftest.py            # Shared fixtures (mock LLM, temp ChromaDB, temp SQLite)
tests/quiz/test_retriever.py      # Retriever tests
tests/quiz/test_tracker.py        # Tracker tests
tests/quiz/test_agent.py          # Agent generation + evaluation tests
tests/quiz/test_router.py         # API endpoint tests
```

---

### Task 1: Config and Dependencies Setup

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/settings.json`
- Modify: `config/settings.example.json`

- [ ] **Step 1: Add LLM SDK dependencies to pyproject.toml**

Add `anthropic`, `google-generativeai`, and `zhipuai` to the dependencies list:

```toml
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "chromadb",
  "langchain-text-splitters",
  "playwright",
  "pydantic",
  "pyyaml",
  "anthropic",
  "google-generativeai",
  "zhipuai",
]
```

- [ ] **Step 2: Update config/settings.example.json to new multi-provider format**

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

- [ ] **Step 3: Update config/settings.json to match the new format**

Same content as `settings.example.json` above.

- [ ] **Step 4: Install new dependencies**

Run: `pip install anthropic google-generativeai zhipuai`

Expected: All three packages install successfully.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml config/settings.json config/settings.example.json
git commit -m "chore: add LLM SDK dependencies and update config format for Phase 4"
```

---

### Task 2: LLM Base Types

**Files:**
- Create: `src/python/llm/base.py`
- Modify: `src/python/llm/__init__.py`

- [ ] **Step 1: Create `src/python/llm/base.py`**

```python
from typing import Protocol


class LLMError(Exception):
    def __init__(self, message: str, category: str):
        super().__init__(message)
        self.category = category


class ErrorCategory:
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class LLMClient(Protocol):
    def complete(self, messages: list[dict], model: str | None = None) -> str: ...
    def get_provider(self) -> str: ...
    def list_models(self) -> list[str]: ...
```

- [ ] **Step 2: Update `src/python/llm/__init__.py`**

```python
from .base import LLMClient, LLMError, ErrorCategory
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from llm.base import LLMError, ErrorCategory, LLMClient; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/python/llm/base.py src/python/llm/__init__.py
git commit -m "feat: add LLM base types — LLMError, ErrorCategory, LLMClient protocol"
```

---

### Task 3: LLM Anthropic Provider (TDD)

**Files:**
- Create: `tests/llm/__init__.py`
- Create: `tests/llm/test_anthropic_provider.py`
- Create: `src/python/llm/anthropic_provider.py`

- [ ] **Step 1: Create `tests/llm/__init__.py`** (empty file)

- [ ] **Step 2: Write failing tests for Anthropic provider**

Create `tests/llm/test_anthropic_provider.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from llm.anthropic_provider import AnthropicProvider
from llm.base import LLMError, ErrorCategory


@pytest.fixture
def mock_anthropic():
    with patch("llm.anthropic_provider.anthropic") as mock_mod:
        mock_client = MagicMock()
        mock_mod.Anthropic.return_value = mock_client
        mock_mod.RateLimitError = Exception
        mock_mod.AuthenticationError = Exception
        mock_mod.APIConnectionError = Exception
        yield mock_client


def test_complete_returns_text(mock_anthropic):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response")]
    mock_anthropic.messages.create.return_value = mock_response

    provider = AnthropicProvider(api_key="test-key")
    result = provider.complete([{"role": "user", "content": "Hello"}])

    assert result == "Test response"
    mock_anthropic.messages.create.assert_called_once_with(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}],
    )


def test_complete_uses_custom_model(mock_anthropic):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Response")]
    mock_anthropic.messages.create.return_value = mock_response

    provider = AnthropicProvider(api_key="test-key", default_model="claude-haiku-4-5")
    provider.complete([{"role": "user", "content": "Hi"}], model="claude-opus-4")

    mock_anthropic.messages.create.assert_called_once_with(
        model="claude-opus-4",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hi"}],
    )


def test_complete_wraps_rate_limit_error(mock_anthropic):
    mock_anthropic.messages.create.side_effect = Exception("rate limited")

    provider = AnthropicProvider(api_key="test-key")
    with pytest.raises(LLMError) as exc_info:
        provider.complete([{"role": "user", "content": "Hi"}])
    assert exc_info.value.category == ErrorCategory.UNKNOWN


def test_get_provider_returns_anthropic():
    provider = AnthropicProvider(api_key="test-key")
    assert provider.get_provider() == "anthropic"


def test_list_models():
    provider = AnthropicProvider(api_key="test-key")
    models = provider.list_models()
    assert "claude-haiku-4-5" in models
    assert "claude-opus-4" in models
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/llm/test_anthropic_provider.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'llm.anthropic_provider'`

- [ ] **Step 4: Create `src/python/llm/anthropic_provider.py`**

```python
import anthropic

from .base import LLMError, ErrorCategory


class AnthropicProvider:
    def __init__(self, api_key: str, default_model: str = "claude-haiku-4-5"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model = model or self._default_model
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=1024,
                messages=messages,
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            raise LLMError(str(e), ErrorCategory.RATE_LIMIT) from e
        except anthropic.AuthenticationError as e:
            raise LLMError(str(e), ErrorCategory.AUTH) from e
        except anthropic.APIConnectionError as e:
            raise LLMError(str(e), ErrorCategory.TIMEOUT) from e
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "anthropic"

    def list_models(self) -> list[str]:
        return ["claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/llm/test_anthropic_provider.py -v`

Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/llm/__init__.py tests/llm/test_anthropic_provider.py src/python/llm/anthropic_provider.py
git commit -m "feat: add Anthropic LLM provider with tests"
```

---

### Task 4: LLM Google Provider (TDD)

**Files:**
- Create: `tests/llm/test_google_provider.py`
- Create: `src/python/llm/google_provider.py`

- [ ] **Step 1: Write failing tests**

Create `tests/llm/test_google_provider.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from llm.google_provider import GoogleProvider
from llm.base import LLMError, ErrorCategory


@pytest.fixture
def mock_genai():
    with patch("llm.google_provider.genai") as mock_mod:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Gemini response"
        mock_model.generate_content.return_value = mock_response
        mock_mod.GenerativeModel.return_value = mock_model
        yield mock_mod


def test_complete_returns_text(mock_genai):
    provider = GoogleProvider(api_key="test-key")
    result = provider.complete([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ])
    assert result == "Gemini response"


def test_complete_calls_generate_content(mock_genai):
    provider = GoogleProvider(api_key="test-key")
    provider.complete([{"role": "user", "content": "Hi"}])
    mock_genai.GenerativeModel.assert_called_once_with(model_name="gemini-2.0-flash")


def test_complete_uses_custom_model(mock_genai):
    provider = GoogleProvider(api_key="test-key", default_model="gemini-2.0-flash")
    provider.complete([{"role": "user", "content": "Hi"}], model="gemini-2.5-pro")
    mock_genai.GenerativeModel.assert_called_once_with(model_name="gemini-2.5-pro")


def test_complete_wraps_error(mock_genai):
    mock_model = mock_genai.GenerativeModel.return_value
    mock_model.generate_content.side_effect = Exception("API error")
    provider = GoogleProvider(api_key="test-key")
    with pytest.raises(LLMError) as exc_info:
        provider.complete([{"role": "user", "content": "Hi"}])
    assert exc_info.value.category == ErrorCategory.UNKNOWN


def test_get_provider_returns_google():
    provider = GoogleProvider(api_key="test-key")
    assert provider.get_provider() == "google"


def test_list_models():
    provider = GoogleProvider(api_key="test-key")
    models = provider.list_models()
    assert "gemini-2.0-flash" in models
    assert "gemini-2.5-pro" in models
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/llm/test_google_provider.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/python/llm/google_provider.py`**

```python
import google.generativeai as genai

from .base import LLMError, ErrorCategory


class GoogleProvider:
    def __init__(self, api_key: str, default_model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model_name = model or self._default_model
        try:
            model = genai.GenerativeModel(model_name=model_name)
            prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "google"

    def list_models(self) -> list[str]:
        return ["gemini-2.0-flash", "gemini-2.5-pro"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/llm/test_google_provider.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/llm/test_google_provider.py src/python/llm/google_provider.py
git commit -m "feat: add Google Gemini LLM provider with tests"
```

---

### Task 5: LLM Z.ai Provider (TDD)

**Files:**
- Create: `tests/llm/test_zai_provider.py`
- Create: `src/python/llm/zai_provider.py`

- [ ] **Step 1: Write failing tests**

Create `tests/llm/test_zai_provider.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from llm.zai_provider import ZaiProvider
from llm.base import LLMError, ErrorCategory


@pytest.fixture
def mock_zhipuai():
    with patch("llm.zai_provider.ZhipuAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="GLM response"))]
        mock_client.chat.completions.create.return_value = mock_response
        yield mock_client


def test_complete_returns_text(mock_zhipuai):
    provider = ZaiProvider(api_key="test-key")
    result = provider.complete([{"role": "user", "content": "Hello"}])
    assert result == "GLM response"


def test_complete_passes_messages(mock_zhipuai):
    provider = ZaiProvider(api_key="test-key")
    msgs = [{"role": "user", "content": "Hi"}]
    provider.complete(msgs)
    mock_zhipuai.chat.completions.create.assert_called_once_with(
        model="glm-4-flash",
        messages=msgs,
    )


def test_complete_uses_custom_model(mock_zhipuai):
    provider = ZaiProvider(api_key="test-key", default_model="glm-4-flash")
    provider.complete([{"role": "user", "content": "Hi"}], model="glm-4")
    mock_zhipuai.chat.completions.create.assert_called_once_with(
        model="glm-4",
        messages=[{"role": "user", "content": "Hi"}],
    )


def test_complete_wraps_error(mock_zhipuai):
    mock_zhipuai.chat.completions.create.side_effect = Exception("API error")
    provider = ZaiProvider(api_key="test-key")
    with pytest.raises(LLMError) as exc_info:
        provider.complete([{"role": "user", "content": "Hi"}])
    assert exc_info.value.category == ErrorCategory.UNKNOWN


def test_get_provider_returns_zai():
    provider = ZaiProvider(api_key="test-key")
    assert provider.get_provider() == "zai"


def test_list_models():
    provider = ZaiProvider(api_key="test-key")
    models = provider.list_models()
    assert "glm-4-flash" in models
    assert "glm-4" in models
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/llm/test_zai_provider.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/python/llm/zai_provider.py`**

```python
from zhipuai import ZhipuAI

from .base import LLMError, ErrorCategory


class ZaiProvider:
    def __init__(self, api_key: str, default_model: str = "glm-4-flash"):
        self._client = ZhipuAI(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model_name = model or self._default_model
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "zai"

    def list_models(self) -> list[str]:
        return ["glm-4-flash", "glm-4"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/llm/test_zai_provider.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/llm/test_zai_provider.py src/python/llm/zai_provider.py
git commit -m "feat: add Z.ai GLM LLM provider with tests"
```

---

### Task 6: LLM Factory (TDD)

**Files:**
- Create: `tests/llm/test_factory.py`
- Create: `src/python/llm/factory.py`
- Modify: `src/python/llm/__init__.py`

- [ ] **Step 1: Write failing tests**

Create `tests/llm/test_factory.py`:

```python
import pytest

from llm.factory import create_client, load_config
from llm.anthropic_provider import AnthropicProvider
from llm.google_provider import GoogleProvider
from llm.zai_provider import ZaiProvider


SAMPLE_CONFIG = {
    "providers": {
        "anthropic": {"api_key": "sk-test", "default_model": "claude-haiku-4-5"},
        "google": {"api_key": "g-test", "default_model": "gemini-2.0-flash"},
        "zai": {"api_key": "z-test", "default_model": "glm-4-flash"},
    },
    "active_provider": "anthropic",
    "quiz_model": "claude-haiku-4-5",
    "clean_model": "claude-opus-4-5",
}


def test_create_client_anthropic():
    client = create_client(SAMPLE_CONFIG)
    assert isinstance(client, AnthropicProvider)


def test_create_client_google():
    config = {**SAMPLE_CONFIG, "active_provider": "google"}
    client = create_client(config)
    assert isinstance(client, GoogleProvider)


def test_create_client_zai():
    config = {**SAMPLE_CONFIG, "active_provider": "zai"}
    client = create_client(config)
    assert isinstance(client, ZaiProvider)


def test_create_client_unknown_provider_raises():
    config = {**SAMPLE_CONFIG, "active_provider": "openai"}
    with pytest.raises(ValueError, match="Unknown provider"):
        create_client(config)


def test_load_config_reads_json(tmp_path):
    import json
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps(SAMPLE_CONFIG))
    loaded = load_config(config_path)
    assert loaded["active_provider"] == "anthropic"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/llm/test_factory.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/python/llm/factory.py`**

```python
import json
from pathlib import Path

from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
from .zai_provider import ZaiProvider

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "zai": ZaiProvider,
}


def create_client(config: dict):
    active = config["active_provider"]
    if active not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {active}")
    provider_config = config["providers"][active]
    return _PROVIDERS[active](
        api_key=provider_config["api_key"],
        default_model=provider_config["default_model"],
    )


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)
```

- [ ] **Step 4: Update `src/python/llm/__init__.py`**

```python
from .base import LLMClient, LLMError, ErrorCategory
from .factory import create_client, load_config
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/llm/ -v`

Expected: All tests across all test files PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/llm/test_factory.py src/python/llm/factory.py src/python/llm/__init__.py
git commit -m "feat: add LLM factory with config loading"
```

---

### Task 7: Quiz Data Models

**Files:**
- Create: `src/python/quiz/models.py`

- [ ] **Step 1: Create `src/python/quiz/models.py`**

All Pydantic models for the quiz system in one place:

```python
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
    difficulty: str = "medium"
    blacklist: list[str] = []
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from quiz.models import Question, Evaluation, RetrievedChunk; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/python/quiz/models.py
git commit -m "feat: add quiz Pydantic models — Question, Evaluation, CategoryMastery, SessionConfig"
```

---

### Task 8: In-Memory Stores

**Files:**
- Create: `src/python/quiz/store.py`

- [ ] **Step 1: Create `src/python/quiz/store.py`**

```python
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


def clear_all() -> None:
    _questions.clear()
    _sessions.clear()
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from quiz.store import store_question, get_question, clear_all; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/python/quiz/store.py
git commit -m "feat: add in-memory question and session stores"
```

---

### Task 9: Retriever (TDD)

**Files:**
- Create: `tests/quiz/__init__.py`
- Create: `tests/quiz/conftest.py`
- Create: `tests/quiz/test_retriever.py`
- Create: `src/python/quiz/retriever.py`

- [ ] **Step 1: Create `tests/quiz/__init__.py`** (empty file)

- [ ] **Step 2: Create shared test fixtures in `tests/quiz/conftest.py`**

```python
import chromadb
import pytest


SOURCE_RANK = {
    "cmg": 0,
    "ref_doc": 1,
    "cpd_doc": 2,
    "notability_note": 3,
}


@pytest.fixture
def seeded_chroma(tmp_path):
    """Creates a temp ChromaDB with sample documents in both collections."""
    client = chromadb.Client()  # EphemeralClient for tests
    db_path = str(tmp_path / "chroma_db")

    notes = client.create_collection("paramedic_notes", metadata={"hnsw:space": "cosine"})
    notes.add(
        ids=["note_1", "note_2"],
        documents=[
            "Adrenaline 1mg IV every 3-5 minutes for cardiac arrest.",
            "Haemorrhage control with tourniquet for traumatic amputation.",
        ],
        metadatas=[
            {
                "source_type": "ref_doc",
                "source_file": "cardiac.md",
                "categories": "Cardiac",
                "chunk_index": 0,
                "last_modified": "2024-01-01",
                "has_review_flag": False,
            },
            {
                "source_type": "notability_note",
                "source_file": "trauma.note",
                "categories": "Trauma",
                "chunk_index": 0,
                "last_modified": "2024-01-01",
                "has_review_flag": False,
            },
        ],
    )

    cmgs = client.create_collection("cmg_guidelines")
    cmgs.add(
        ids=["cmg_1", "cmg_2"],
        documents=[
            "CMG 14.1: Adult cardiac arrest. Defibrillation 200J biphasic. Adrenaline 1mg IV/IO after second shock.",
            "CMG 7: Spinal motion restriction. Apply cervical collar. Secure to spinal board.",
        ],
        metadatas=[
            {
                "source_type": "cmg",
                "source_file": "cmg_14.json",
                "cmg_number": "14",
                "section": "Cardiac",
                "chunk_type": "protocol",
                "last_modified": "2024-01-01",
            },
            {
                "source_type": "cmg",
                "source_file": "cmg_7.json",
                "cmg_number": "7",
                "section": "Trauma",
                "chunk_type": "protocol",
                "last_modified": "2024-01-01",
            },
        ],
    )

    return client


@pytest.fixture
def mock_llm():
    """Returns a mock LLMClient that echoes back a structured response."""
    from unittest.mock import MagicMock
    llm = MagicMock()
    return llm
```

- [ ] **Step 3: Write failing retriever tests**

Create `tests/quiz/test_retriever.py`:

```python
from unittest.mock import MagicMock

import pytest

from quiz.retriever import Retriever, SOURCE_RANK


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


def test_retrieve_chunk_has_required_fields(retriever):
    results = retriever.retrieve("adrenaline", n=1)
    assert len(results) == 1
    chunk = results[0]
    assert chunk.content
    assert chunk.source_type in ("cmg", "ref_doc", "cpd_doc", "notability_note")
    assert isinstance(chunk.source_rank, int)
    assert isinstance(chunk.relevance_score, float)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/quiz/test_retriever.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 5: Create `src/python/quiz/retriever.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import chromadb

from .models import RetrievedChunk

SOURCE_RANK = {
    "cmg": 0,
    "ref_doc": 1,
    "cpd_doc": 2,
    "notability_note": 3,
}


class Retriever:
    def __init__(
        self,
        db_path: str | Path | None = None,
        client: chromadb.ClientAPI | chromadb.PersistentClient | None = None,
    ):
        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=str(db_path or "data/chroma_db"))
        self._notes = self._client.get_or_create_collection(
            "paramedic_notes", metadata={"hnsw:space": "cosine"}
        )
        self._cmgs = self._client.get_or_create_collection("cmg_guidelines")

    def retrieve(
        self,
        query: str,
        n: int = 5,
        filters: dict | None = None,
        exclude_categories: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        all_chunks: list[RetrievedChunk] = []

        notes_where = self._build_where(filters, exclude_categories, collection="notes")
        cmgs_where = self._build_where(filters, exclude_categories, collection="cmgs")

        if notes_where is not None or filters is None and exclude_categories is None:
            notes_results = self._notes.query(
                query_texts=[query], n_results=n, where=notes_where or None
            )
            all_chunks.extend(self._parse_results(notes_results, "notes"))

        if cmgs_where is not None or filters is None and exclude_categories is None:
            cmgs_results = self._cmgs.query(
                query_texts=[query], n_results=n, where=cmgs_where or None
            )
            all_chunks.extend(self._parse_results(cmgs_results, "cmgs"))

        all_chunks.sort(key=lambda c: (c.source_rank, -c.relevance_score))
        return all_chunks[:n]

    def _build_where(
        self,
        base_filters: dict | None,
        exclude: list[str] | None,
        collection: str,
    ) -> dict | None:
        conditions: list[dict] = []

        if base_filters:
            for key, value in base_filters.items():
                conditions.append({key: value})

        if exclude:
            if collection == "notes":
                for cat in exclude:
                    conditions.append({"categories": {"$nin": [cat]}})
            else:
                for cat in exclude:
                    conditions.append({"section": {"$nin": [cat]}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _parse_results(self, raw: dict, collection: str) -> list[RetrievedChunk]:
        if not raw["documents"] or not raw["documents"][0]:
            return []
        chunks: list[RetrievedChunk] = []
        for i, doc in enumerate(raw["documents"][0]):
            meta = raw["metadatas"][0][i]
            distance = raw["distances"][0][i] if raw.get("distances") else 0.0
            source_type = meta.get("source_type", "unknown")
            chunks.append(
                RetrievedChunk(
                    content=doc,
                    source_type=source_type,
                    source_file=meta.get("source_file", ""),
                    source_rank=SOURCE_RANK.get(source_type, 99),
                    category=meta.get("section") or meta.get("categories"),
                    cmg_number=meta.get("cmg_number"),
                    chunk_type=meta.get("chunk_type"),
                    relevance_score=-distance,
                )
            )
        return chunks
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/quiz/test_retriever.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/quiz/__init__.py tests/quiz/conftest.py tests/quiz/test_retriever.py src/python/quiz/retriever.py
git commit -m "feat: add RAG retriever with dual-collection queries and source hierarchy"
```

---

### Task 10: Tracker (TDD)

**Files:**
- Create: `tests/quiz/test_tracker.py`
- Create: `src/python/quiz/tracker.py`

- [ ] **Step 1: Write failing tracker tests**

Create `tests/quiz/test_tracker.py`:

```python
import pytest

from quiz.tracker import Tracker


@pytest.fixture
def tracker(tmp_path):
    return Tracker(db_path=tmp_path / "mastery.db")


def test_record_answer_creates_category(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14.1")
    mastery = tracker.get_mastery()
    assert len(mastery) == 1
    assert mastery[0].category == "Cardiac"


def test_record_answer_correct_increments(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14.1")
    tracker.record_answer("q2", "Cardiac", "scenario", "correct", 20.0, "CMG 14.1")
    mastery = tracker.get_mastery()
    assert mastery[0].correct == 2
    assert mastery[0].total_attempts == 2


def test_record_answer_partial_and_incorrect(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "partial", 15.0, "CMG 14.1")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14.1")
    mastery = tracker.get_mastery()
    assert mastery[0].partial == 1
    assert mastery[0].incorrect == 1


def test_mastery_percent_calculation(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "partial", 15.0, "CMG 14")
    tracker.record_answer("q3", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    mastery = tracker.get_mastery()
    assert mastery[0].mastery_percent == pytest.approx(50.0)


def test_mastery_status_strong(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q3", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    assert tracker.get_mastery()[0].status == "strong"


def test_mastery_status_developing(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "partial", 15.0, "CMG 14")
    assert tracker.get_mastery()[0].status == "developing"


def test_mastery_status_weak(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    assert tracker.get_mastery()[0].status == "weak"


def test_self_graded_excluded_from_mastery(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", None, 12.0, "CMG 14")
    mastery = tracker.get_mastery()
    assert len(mastery) == 0


def test_self_graded_still_in_history(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", None, 12.0, "CMG 14")
    history = tracker.get_recent_history()
    assert len(history) == 1
    assert history[0].score is None


def test_get_weak_categories(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "recall", "incorrect", 30.0, "CMG 7")
    weak = tracker.get_weak_categories(n=1)
    assert weak == ["Trauma"]


def test_get_streak(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q3", "Cardiac", "recall", "partial", 15.0, "CMG 14")
    assert tracker.get_streak() == 0


def test_get_streak_active(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    assert tracker.get_streak() == 2


def test_get_accuracy(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Cardiac", "recall", "incorrect", 30.0, "CMG 14")
    assert tracker.get_accuracy() == pytest.approx(50.0)


def test_blacklist_add_and_get(tracker):
    tracker.add_to_blacklist("Paediatrics")
    assert tracker.get_blacklist() == ["Paediatrics"]


def test_blacklist_remove(tracker):
    tracker.add_to_blacklist("Paediatrics")
    tracker.remove_from_blacklist("Paediatrics")
    assert tracker.get_blacklist() == []


def test_blacklist_duplicate_ignored(tracker):
    tracker.add_to_blacklist("Paediatrics")
    tracker.add_to_blacklist("Paediatrics")
    assert tracker.get_blacklist() == ["Paediatrics"]


def test_get_recent_history(tracker):
    tracker.record_answer("q1", "Cardiac", "recall", "correct", 10.0, "CMG 14")
    tracker.record_answer("q2", "Trauma", "scenario", "incorrect", 30.0, "CMG 7")
    history = tracker.get_recent_history(limit=10)
    assert len(history) == 2
    assert history[0].category == "Cardiac"
    assert history[1].category == "Trauma"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/quiz/test_tracker.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/python/quiz/tracker.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import CategoryMastery, QuizAttempt


class Tracker:
    def __init__(self, db_path: str | Path = "data/mastery.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                section TEXT
            );
            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY,
                question_id TEXT NOT NULL,
                category_id INTEGER REFERENCES categories(id),
                question_type TEXT,
                score TEXT,
                elapsed_seconds REAL,
                source_citation TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY,
                category_name TEXT UNIQUE NOT NULL
            );
        """)

    def record_answer(
        self,
        question_id: str,
        category: str,
        question_type: str,
        score: str | None,
        elapsed_seconds: float,
        source_citation: str,
    ) -> None:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,)
        )
        if cur.lastrowid and cur.lastrowid > 0:
            cat_id = cur.lastrowid
        else:
            row = self._conn.execute(
                "SELECT id FROM categories WHERE name = ?", (category,)
            ).fetchone()
            cat_id = row["id"]

        self._conn.execute(
            """INSERT INTO quiz_history
               (question_id, category_id, question_type, score, elapsed_seconds, source_citation)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (question_id, cat_id, question_type, score, elapsed_seconds, source_citation),
        )
        self._conn.commit()

    def get_mastery(self) -> list[CategoryMastery]:
        rows = self._conn.execute("""
            SELECT c.name,
                   COUNT(*) FILTER (WHERE h.score IS NOT NULL) AS total,
                   COUNT(*) FILTER (WHERE h.score = 'correct') AS correct,
                   COUNT(*) FILTER (WHERE h.score = 'partial') AS partial,
                   COUNT(*) FILTER (WHERE h.score = 'incorrect') AS incorrect
            FROM categories c
            JOIN quiz_history h ON h.category_id = c.id
            GROUP BY c.name
        """).fetchall()

        results = []
        for row in rows:
            total = row["total"]
            if total == 0:
                continue
            correct = row["correct"]
            partial = row["partial"]
            incorrect = row["incorrect"]
            percent = (correct + partial * 0.5) / total * 100
            status = "strong" if percent > 75 else "developing" if percent >= 50 else "weak"
            results.append(
                CategoryMastery(
                    category=row["name"],
                    total_attempts=total,
                    correct=correct,
                    partial=partial,
                    incorrect=incorrect,
                    mastery_percent=round(percent, 1),
                    status=status,
                )
            )
        return results

    def get_weak_categories(self, n: int = 3) -> list[str]:
        mastery = self.get_mastery()
        mastery.sort(key=lambda m: m.mastery_percent)
        return [m.category for m in mastery[:n]]

    def get_streak(self) -> int:
        rows = self._conn.execute(
            "SELECT score FROM quiz_history WHERE score IS NOT NULL ORDER BY id DESC"
        ).fetchall()
        streak = 0
        for row in rows:
            if row["score"] == "correct":
                streak += 1
            else:
                break
        return streak

    def get_accuracy(self) -> float:
        row = self._conn.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE score = 'correct') AS correct
            FROM quiz_history
            WHERE score IS NOT NULL
        """).fetchone()
        if not row or row["total"] == 0:
            return 0.0
        return round(row["correct"] / row["total"] * 100, 1)

    def get_recent_history(self, limit: int = 20) -> list[QuizAttempt]:
        rows = self._conn.execute("""
            SELECT h.id, h.question_id, c.name AS category, h.question_type,
                   h.score, h.elapsed_seconds, h.source_citation, h.created_at
            FROM quiz_history h
            JOIN categories c ON h.category_id = c.id
            ORDER BY h.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [
            QuizAttempt(
                id=row["id"],
                question_id=row["question_id"],
                category=row["category"],
                question_type=row["question_type"],
                score=row["score"],
                elapsed_seconds=row["elapsed_seconds"],
                source_citation=row["source_citation"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add_to_blacklist(self, category_name: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO blacklist (category_name) VALUES (?)",
            (category_name,),
        )
        self._conn.commit()

    def remove_from_blacklist(self, category_name: str) -> None:
        self._conn.execute(
            "DELETE FROM blacklist WHERE category_name = ?", (category_name,)
        )
        self._conn.commit()

    def get_blacklist(self) -> list[str]:
        rows = self._conn.execute("SELECT category_name FROM blacklist").fetchall()
        return [row["category_name"] for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/quiz/test_tracker.py -v`

Expected: All 16 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/quiz/test_tracker.py src/python/quiz/tracker.py
git commit -m "feat: add SQLite mastery tracker with history, streak, and blacklist"
```

---

### Task 11: Quiz Agent — Generation and Evaluation (TDD)

**Files:**
- Create: `tests/quiz/test_agent.py`
- Create: `src/python/quiz/agent.py`

- [ ] **Step 1: Write failing agent tests**

Create `tests/quiz/test_agent.py`:

```python
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
        mock_llm.complete.return_value = json.dumps({
            "question_text": "What adrenaline dose for cardiac arrest?",
            "question_type": "drug_dose",
            "source_citation": "ACTAS CMG 14.1",
            "category": "Cardiac",
        })

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

    def test_topic_mode_filters_by_topic(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps({
            "question_text": "Test?",
            "question_type": "recall",
            "source_citation": "CMG 14",
            "category": "Cardiac",
        })

        generate_question(
            mode="topic", topic="Cardiac",
            llm=mock_llm, retriever=mock_retriever, tracker=mock_tracker,
        )
        mock_retriever.retrieve.assert_called_once()
        call_kwargs = mock_retriever.retrieve.call_args
        assert "Cardiac" in str(call_kwargs)

    def test_gap_driven_uses_weak_categories(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_tracker.get_weak_categories.return_value = ["Trauma", "Paediatrics"]
        mock_retriever.retrieve.return_value = _make_chunks(category="Trauma")
        mock_llm.complete.return_value = json.dumps({
            "question_text": "Test?",
            "question_type": "recall",
            "source_citation": "CMG 7",
            "category": "Trauma",
        })

        result = generate_question(
            mode="gap_driven",
            llm=mock_llm, retriever=mock_retriever, tracker=mock_tracker,
        )
        mock_tracker.get_weak_categories.assert_called_once()

    def test_random_mode(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_tracker = MagicMock()

        mock_retriever.retrieve.return_value = _make_chunks()
        mock_llm.complete.return_value = json.dumps({
            "question_text": "Test?",
            "question_type": "recall",
            "source_citation": "CMG 14",
            "category": "Cardiac",
        })

        result = generate_question(
            mode="random",
            llm=mock_llm, retriever=mock_retriever, tracker=mock_tracker,
        )
        assert result.question_text


class TestEvaluateAnswer:
    def test_correct_answer(self):
        mock_llm = MagicMock()
        question = _make_question()

        mock_llm.complete.return_value = json.dumps({
            "score": "correct",
            "correct_elements": ["1mg IV/IO", "every 3-5 minutes"],
            "missing_or_wrong": [],
            "source_quote": "Adrenaline 1mg IV/IO every 3-5 minutes during cardiac arrest.",
            "feedback_summary": "Correct.",
        })

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

        mock_llm.complete.return_value = json.dumps({
            "score": "partial",
            "correct_elements": ["adrenaline"],
            "missing_or_wrong": ["missed dose amount"],
            "source_quote": "Adrenaline 1mg IV/IO every 3-5 minutes.",
            "feedback_summary": "Partially correct.",
        })

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

    def test_evaluation_includes_source_quote(self):
        mock_llm = MagicMock()
        question = _make_question()

        mock_llm.complete.return_value = json.dumps({
            "score": "incorrect",
            "correct_elements": [],
            "missing_or_wrong": ["wrong dose"],
            "source_quote": "Adrenaline 1mg IV/IO every 3-5 minutes.",
            "feedback_summary": "Incorrect.",
        })

        result = evaluate_answer(
            question=question,
            user_answer="5mg",
            elapsed_seconds=10.0,
            llm=mock_llm,
        )
        assert "1mg" in result.source_quote
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/quiz/test_agent.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `src/python/quiz/agent.py`**

```python
from __future__ import annotations

import json
import random
import uuid

from .models import Question, Evaluation, RetrievedChunk
from .retriever import Retriever
from .tracker import Tracker

GENERATION_SYSTEM_PROMPT = """You are a clinical quiz generator for ACT Ambulance Service paramedics.
Generate one question from the provided source material.

Rules:
- The question must be answerable from the source text alone
- Never fabricate clinical information
- Vary question types: recall, definition, scenario, drug_dose
- Use Australian English (adrenaline, haemorrhage, colour)
- Tone: direct, clinical

Respond with valid JSON only:
{
  "question_text": "...",
  "question_type": "recall|definition|scenario|drug_dose",
  "source_citation": "e.g. ACTAS CMG 14.1",
  "category": "e.g. Cardiac"
}"""

EVALUATION_SYSTEM_PROMPT = """You are evaluating a paramedic student's answer against clinical source material.

Rules:
- Compare the answer against the source material ONLY — never general knowledge
- Score conservatively: "partial" if anything material is wrong or missing
- Cite the exact source text as source_quote
- Use Australian English
- Tone: supportive expert, straightforward, not chatty

Respond with valid JSON only:
{
  "score": "correct|partial|incorrect",
  "correct_elements": ["..."],
  "missing_or_wrong": ["..."],
  "source_quote": "exact quote from source",
  "feedback_summary": "2-3 sentence clinical feedback"
}"""


def generate_question(
    mode: str,
    llm,
    retriever: Retriever,
    tracker: Tracker,
    topic: str | None = None,
    blacklist: list[str] | None = None,
    difficulty: str = "medium",
) -> Question:
    query, filters = _resolve_mode(mode, topic, tracker)

    chunks = retriever.retrieve(
        query=query,
        n=5,
        filters=filters,
        exclude_categories=blacklist,
    )

    if not chunks:
        raise ValueError("No relevant chunks found for question generation")

    source_text = "\n\n".join(f"[Source: {c.source_type}]\n{c.content}" for c in chunks)

    messages = [
        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Source material:\n\n{source_text}\n\nDifficulty: {difficulty}"},
    ]

    response_text = llm.complete(messages)
    parsed = json.loads(response_text)

    question = Question(
        id=str(uuid.uuid4()),
        question_text=parsed["question_text"],
        question_type=parsed.get("question_type", "recall"),
        source_chunks=chunks,
        source_citation=parsed.get("source_citation", chunks[0].source_file),
        difficulty=difficulty,
        category=parsed.get("category", chunks[0].category or "General"),
    )
    return question


def evaluate_answer(
    question: Question,
    user_answer: str | None,
    elapsed_seconds: float,
    llm,
) -> Evaluation:
    if user_answer is None:
        source = question.source_chunks[0] if question.source_chunks else None
        return Evaluation(
            score=None,
            source_quote=source.content if source else "",
            source_citation=question.source_citation,
            feedback_summary=None,
            response_time_seconds=elapsed_seconds,
        )

    source_text = "\n\n".join(c.content for c in question.source_chunks)

    messages = [
        {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Question: {question.question_text}\n\n"
            f"Source material:\n{source_text}\n\n"
            f"Student answer: {user_answer}"
        )},
    ]

    response_text = llm.complete(messages)
    parsed = json.loads(response_text)

    return Evaluation(
        score=parsed.get("score", "incorrect"),
        correct_elements=parsed.get("correct_elements", []),
        missing_or_wrong=parsed.get("missing_or_wrong", []),
        source_quote=parsed.get("source_quote", ""),
        source_citation=question.source_citation,
        feedback_summary=parsed.get("feedback_summary"),
        response_time_seconds=elapsed_seconds,
    )


def _resolve_mode(
    mode: str, topic: str | None, tracker: Tracker
) -> tuple[str, dict | None]:
    if mode == "topic":
        if not topic:
            raise ValueError("Topic mode requires a topic")
        return topic, None
    elif mode == "gap_driven":
        weak = tracker.get_weak_categories(n=1)
        query = weak[0] if weak else random.choice(["Cardiac", "Trauma", "Respiratory"])
        return query, None
    elif mode == "random":
        query = random.choice(["Cardiac", "Trauma", "Respiratory", "Paediatrics", "Pharmacology", "Obstetrics", "Mental Health", "Infectious Disease"])
        return query, None
    else:
        raise ValueError(f"Unknown mode: {mode}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/quiz/test_agent.py -v`

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/quiz/test_agent.py src/python/quiz/agent.py
git commit -m "feat: add quiz agent with question generation and answer evaluation"
```

---

### Task 12: Quiz Router (TDD)

**Files:**
- Create: `tests/quiz/test_router.py`
- Create: `src/python/quiz/router.py`
- Modify: `src/python/quiz/__init__.py`

- [ ] **Step 1: Write failing router tests**

Create `tests/quiz/test_router.py`:

```python
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from quiz.models import Question, RetrievedChunk, Evaluation, CategoryMastery, SessionConfig


@pytest.fixture
def mock_deps():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_tracker = MagicMock()

    with (
        patch("quiz.router._get_llm", return_value=mock_llm),
        patch("quiz.router._get_retriever", return_value=mock_retriever),
        patch("quiz.router._get_tracker", return_value=mock_tracker),
    ):
        yield {"llm": mock_llm, "retriever": mock_retriever, "tracker": mock_tracker}


@pytest.fixture
def client(mock_deps):
    from main import app
    return TestClient(app)


def _make_question():
    return Question(
        id="q-1",
        question_text="What is the adrenaline dose?",
        question_type="drug_dose",
        source_chunks=[RetrievedChunk(
            content="Adrenaline 1mg IV.",
            source_type="cmg",
            source_file="cmg_14.json",
            source_rank=0,
            category="Cardiac",
            cmg_number="14",
            chunk_type="protocol",
            relevance_score=0.95,
        )],
        source_citation="ACTAS CMG 14.1",
        difficulty="medium",
        category="Cardiac",
    )


class TestSessionStart:
    def test_start_session_returns_200(self, client):
        response = client.post("/quiz/session/start", json={
            "mode": "random",
            "topic": None,
            "difficulty": "medium",
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["mode"] == "random"


class TestGenerateQuestion:
    def test_generate_returns_question(self, client, mock_deps):
        with patch("quiz.router.generate_question", return_value=_make_question()):
            client.post("/quiz/session/start", json={"mode": "random"})
            response = client.post("/quiz/question/generate", json={"session_id": "any"})
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
            response = client.post("/quiz/question/evaluate", json={
                "question_id": "q-1",
                "user_answer": "1mg IV",
                "elapsed_seconds": 45.0,
            })
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
            response = client.post("/quiz/question/evaluate", json={
                "question_id": "q-1",
                "user_answer": None,
                "elapsed_seconds": 12.0,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["score"] is None


class TestMastery:
    def test_get_mastery(self, client, mock_deps):
        mock_tracker = mock_deps["tracker"]
        mock_tracker.get_mastery.return_value = [
            CategoryMastery(
                category="Cardiac", total_attempts=5, correct=3, partial=1,
                incorrect=1, mastery_percent=70.0, status="developing",
            )
        ]
        response = client.get("/quiz/mastery")
        assert response.status_code == 200
        assert len(response.json()) == 1


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/quiz/test_router.py -v`

Expected: FAIL — `ModuleNotFoundError` or import errors

- [ ] **Step 3: Create `src/python/quiz/router.py`**

```python
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm.base import LLMClient
from llm.factory import create_client, load_config

from .agent import generate_question as _generate_question
from .agent import evaluate_answer as _evaluate_answer
from .models import Evaluation, SessionConfig
from .retriever import Retriever
from .store import get_question, get_session, store_question, store_session
from .tracker import Tracker

router = APIRouter(prefix="/quiz", tags=["quiz"])

_llm: LLMClient | None = None
_retriever: Retriever | None = None
_tracker: Tracker | None = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        config = load_config()
        _llm = create_client(config)
    return _llm


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def _get_tracker() -> Tracker:
    global _tracker
    if _tracker is None:
        _tracker = Tracker()
    return _tracker


class StartSessionRequest(BaseModel):
    mode: str
    topic: Optional[str] = None
    difficulty: str = "medium"


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
    )
    store_session(session_id, config)
    return {
        "session_id": session_id,
        "mode": req.mode,
        "blacklist": blacklist,
    }


@router.post("/question/generate")
def generate(req: GenerateQuestionRequest) -> dict:
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    question = _generate_question(
        mode=session.mode,
        topic=session.topic,
        blacklist=session.blacklist,
        difficulty=session.difficulty,
        llm=_get_llm(),
        retriever=_get_retriever(),
        tracker=_get_tracker(),
    )
    store_question(question)

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

    evaluation = _evaluate_question(
        question=question,
        user_answer=req.user_answer,
        elapsed_seconds=req.elapsed_seconds,
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
    }


def _evaluate_question(
    question, user_answer, elapsed_seconds
) -> Evaluation:
    return _evaluate_answer(
        question=question,
        user_answer=user_answer,
        elapsed_seconds=elapsed_seconds,
        llm=_get_llm(),
    )


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
    return [h.model_dump() for h in tracker.get_recent_history(limit=limit)]


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
```

- [ ] **Step 4: Update `src/python/quiz/__init__.py`**

```python
from .models import Question, Evaluation, RetrievedChunk, CategoryMastery, QuizAttempt, SessionConfig
from .agent import generate_question, evaluate_answer
from .retriever import Retriever
from .tracker import Tracker
```

- [ ] **Step 5: Wire router into `src/python/main.py`**

Add after the `app.add_middleware(...)` block:

```python
from quiz.router import router as quiz_router
app.include_router(quiz_router)
```

The full `main.py` becomes:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="StudyBot Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from quiz.router import router as quiz_router
app.include_router(quiz_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=7777, reload=False)
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `python -m pytest tests/quiz/test_router.py -v`

Expected: All 7 tests PASS.

Run: `python -m pytest tests/ -v`

Expected: All tests across the project PASS (including existing pipeline and health tests).

- [ ] **Step 7: Commit**

```bash
git add tests/quiz/test_router.py src/python/quiz/router.py src/python/quiz/__init__.py src/python/main.py
git commit -m "feat: add quiz API router with session, question, mastery, and blacklist endpoints"
```

---

### Task 13: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 2: Verify the FastAPI app starts**

Run: `python -c "from main import app; print('Routes:', [r.path for r in app.routes])"`

Expected: Output includes `/health`, `/quiz/session/start`, `/quiz/question/generate`, `/quiz/question/evaluate`, `/quiz/mastery`, `/quiz/streak`, `/quiz/history`, `/quiz/blacklist`.

- [ ] **Step 3: Verify existing tests still pass**

Run: `python -m pytest tests/python/ tests/pipeline/ -v`

Expected: All existing tests PASS — no regressions.
