# OpenAI Provider Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenAI as a fourth LLM provider with GPT-5.4, GPT-5.4-mini, and GPT-5.4-nano models.

**Architecture:** Follows the existing provider pattern — new `OpenAIProvider` class implementing the `LLMClient` protocol, registered in the model registry and factory. Frontend types updated to include the new provider. No new abstractions.

**Tech Stack:** Python `openai` SDK, FastAPI backend, React/TypeScript frontend

---

### Task 1: Add `openai` dependency

**Files:**
- Modify: `pyproject.toml:9-21`

- [ ] **Step 1: Add `openai` to `pyproject.toml` dependencies**

Add `"openai"` to the `dependencies` list in `pyproject.toml` after the existing `"zhipuai"` entry:

```toml
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "chromadb",
  "langchain-text-splitters",
  "pydantic",
  "pyyaml",
  "anthropic",
  "google-genai",
  "zhipuai",
  "openai",
  "python-dotenv",
  "python-multipart",
]
```

- [ ] **Step 2: Install the dependency**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && pip install openai`
Expected: `Successfully installed openai-...`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add openai SDK dependency"
```

---

### Task 2: Create `OpenAIProvider` class

**Files:**
- Create: `src/python/llm/openai_provider.py`
- Test: `tests/llm/test_openai_provider.py`

- [ ] **Step 1: Write the provider test file**

Create `tests/llm/test_openai_provider.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from llm.openai_provider import OpenAIProvider
from llm.base import LLMError, ErrorCategory
from llm.models import _DEFAULTS


@pytest.fixture
def mock_openai():
    with patch("llm.openai_provider.openai") as mock_mod:
        mock_client = MagicMock()
        mock_mod.OpenAI.return_value = mock_client
        mock_mod.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_mod.AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_mod.APIConnectionError = type("APIConnectionError", (Exception,), {})
        yield mock_client


def test_complete_returns_text(mock_openai):
    mock_choice = MagicMock()
    mock_choice.message.content = "Test response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai.chat.completions.create.return_value = mock_response

    provider = OpenAIProvider(api_key="test-key")
    result = provider.complete([{"role": "user", "content": "Hello"}])

    assert result == "Test response"
    mock_openai.chat.completions.create.assert_called_once_with(
        model=_DEFAULTS["openai"]["low"],
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}],
    )


def test_complete_uses_custom_model(mock_openai):
    mock_choice = MagicMock()
    mock_choice.message.content = "Response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai.chat.completions.create.return_value = mock_response

    provider = OpenAIProvider(api_key="test-key", default_model="gpt-5.4-mini")
    provider.complete([{"role": "user", "content": "Hi"}], model="gpt-5.4")

    mock_openai.chat.completions.create.assert_called_once_with(
        model="gpt-5.4",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hi"}],
    )


def test_complete_wraps_rate_limit_error(mock_openai):
    mock_openai.chat.completions.create.side_effect = Exception("rate limited")

    provider = OpenAIProvider(api_key="test-key")
    with pytest.raises(LLMError) as exc_info:
        provider.complete([{"role": "user", "content": "Hi"}])
    assert exc_info.value.category == ErrorCategory.UNKNOWN


def test_get_provider_returns_openai():
    provider = OpenAIProvider(api_key="test-key")
    assert provider.get_provider() == "openai"


def test_list_models():
    provider = OpenAIProvider(api_key="test-key")
    models = provider.list_models()
    assert _DEFAULTS["openai"]["low"] in models
    assert _DEFAULTS["openai"]["high"] in models
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/llm/test_openai_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm.openai_provider'`

- [ ] **Step 3: Write the provider implementation**

Create `src/python/llm/openai_provider.py`:

```python
import openai

from .base import LLMError, ErrorCategory
from .models import load_model_registry


class OpenAIProvider:
    def __init__(self, api_key: str, default_model: str = "gpt-5.4-nano"):
        self._client = openai.OpenAI(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model_name = model or self._default_model
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                max_tokens=1024,
                messages=messages,
            )
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            raise LLMError(str(e), ErrorCategory.RATE_LIMIT) from e
        except openai.AuthenticationError as e:
            raise LLMError(str(e), ErrorCategory.AUTH) from e
        except openai.APIConnectionError as e:
            raise LLMError(str(e), ErrorCategory.TIMEOUT) from e
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "openai"

    def list_models(self) -> list[str]:
        registry = load_model_registry()
        return list(registry.get("openai", {}).values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/llm/test_openai_provider.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/llm/openai_provider.py tests/llm/test_openai_provider.py
git commit -m "feat: add OpenAI provider with GPT-5.4 model support"
```

---

### Task 3: Register OpenAI in the model registry

**Files:**
- Modify: `src/python/llm/models.py`
- Modify: `.env.example`

- [ ] **Step 1: Add OpenAI to `_DEFAULTS` in `models.py`**

Add the following entry to the `_DEFAULTS` dict after the `"google"` entry (line 29):

```python
    "openai": {
        "low": "gpt-5.4-nano",
        "medium": "gpt-5.4-mini",
        "high": "gpt-5.4",
    },
```

- [ ] **Step 2: Add OpenAI to `_ENV_KEYS` in `models.py`**

Add the following entry to the `_ENV_KEYS` dict after the `"google"` entry (line 47):

```python
    "openai": {
        "low": "OPENAI_MODEL_LOW",
        "medium": "OPENAI_MODEL_MEDIUM",
        "high": "OPENAI_MODEL_HIGH",
    },
```

- [ ] **Step 3: Add OpenAI to `PROVIDER_LABELS` in `models.py`**

Add the following entry to the `PROVIDER_LABELS` dict after `"zai"` (line 53):

```python
    "openai": "OpenAI",
```

- [ ] **Step 4: Update `save_model_registry()` write order in `models.py`**

On line 103, the iteration tuple currently reads:

```python
    for provider in ("zai", "anthropic", "google"):
```

Change it to:

```python
    for provider in ("zai", "anthropic", "google", "openai"):
```

- [ ] **Step 5: Add OpenAI model vars to `.env.example`**

Append after the existing `GOOGLE_MODEL_HIGH` line:

```
# OpenAI models
OPENAI_MODEL_LOW=gpt-5.4-nano
OPENAI_MODEL_MEDIUM=gpt-5.4-mini
OPENAI_MODEL_HIGH=gpt-5.4
```

- [ ] **Step 6: Verify existing tests still pass**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/llm/ -v`
Expected: All tests PASS (existing + new OpenAI tests)

- [ ] **Step 7: Commit**

```bash
git add src/python/llm/models.py .env.example
git commit -m "feat: register OpenAI models in provider registry"
```

---

### Task 4: Register OpenAI in the factory and exports

**Files:**
- Modify: `src/python/llm/factory.py`
- Modify: `src/python/llm/__init__.py`

- [ ] **Step 1: Update `factory.py` — import and register**

In `src/python/llm/factory.py`:

Add import on line 9 (after the existing `from .anthropic_provider` line):

```python
from .openai_provider import OpenAIProvider
```

Add to the `_PROVIDERS` dict (after `"zai": ZaiProvider`):

```python
    "openai": OpenAIProvider,
```

- [ ] **Step 2: Update `__init__.py` — no changes needed**

The `__init__.py` only exports `base`, `factory`, and `models` symbols. `OpenAIProvider` is accessed through the factory, not directly imported. No change needed.

- [ ] **Step 3: Verify factory resolves OpenAI models**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -c "from llm.models import resolve_provider_for_model; print(resolve_provider_for_model('gpt-5.4-nano'))"`
Expected: `openai`

- [ ] **Step 4: Commit**

```bash
git add src/python/llm/factory.py
git commit -m "feat: register OpenAI provider in factory"
```

---

### Task 5: Update config and frontend types

**Files:**
- Modify: `config/settings.example.json`
- Modify: `src/renderer/types/api.ts`

- [ ] **Step 1: Add `openai` provider to `config/settings.example.json`**

Add the following entry inside the `"providers"` object, after the `"zai"` entry:

```json
    "openai": { "api_key": "", "default_model": "gpt-5.4-nano" }
```

The full file should be:

```json
{
  "providers": {
    "anthropic": { "api_key": "", "default_model": "claude-haiku-4-5-20251001" },
    "google": { "api_key": "", "default_model": "gemini-3.1-flash-lite-preview" },
    "zai": { "api_key": "", "default_model": "glm-4.7-flash" },
    "openai": { "api_key": "", "default_model": "gpt-5.4-nano" }
  },
  "active_provider": "anthropic",
  "quiz_model": "gemini-3.1-flash-lite-preview",
  "clean_model": "claude-opus-4.6"
}
```

- [ ] **Step 2: Add `openai` to TypeScript types in `api.ts`**

In `src/renderer/types/api.ts`, make three changes:

a) In `SettingsConfig` interface (line 93), add `openai` after `zai`:

```typescript
    openai: { api_key: string; default_model: string };
```

b) In `ProviderKey` type (line 103), add `"openai"`:

```typescript
export type ProviderKey = "anthropic" | "google" | "zai" | "openai";
```

c) In `ModelRegistry` interface (line 111), add `openai`:

```typescript
  openai: ModelTier;
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer && npx tsc --noEmit`
Expected: No errors related to `openai` type additions

- [ ] **Step 4: Commit**

```bash
git add config/settings.example.json src/renderer/types/api.ts
git commit -m "feat: add OpenAI to settings config and frontend types"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run the full Python test suite**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -m pytest tests/llm/ tests/python/ -v --tb=short`
Expected: All tests PASS (excluding known failures documented in `KNOWN_TEST_FAILURES.md`)

- [ ] **Step 2: Verify frontend builds**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/renderer && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Verify provider round-trip in Python**

Run:
```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python -c "
from llm.models import load_model_registry, all_model_ids, resolve_provider_for_model
reg = load_model_registry()
assert 'openai' in reg
assert reg['openai']['low'] == 'gpt-5.4-nano'
assert reg['openai']['medium'] == 'gpt-5.4-mini'
assert reg['openai']['high'] == 'gpt-5.4'
assert resolve_provider_for_model('gpt-5.4') == 'openai'
assert 'gpt-5.4-nano' in all_model_ids()
print('All checks passed')
"
```
Expected: `All checks passed`
