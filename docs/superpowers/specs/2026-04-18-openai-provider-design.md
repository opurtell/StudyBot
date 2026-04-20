# OpenAI Provider Integration

**Date:** 2026-04-18
**Status:** Approved

## Summary

Add OpenAI as a fourth LLM provider, exposing GPT-5.4 (high), GPT-5.4-mini (medium), and GPT-5.4-nano (low) as selectable models for quiz generation, evaluation, and pipeline cleaning.

## Models

| Tier | Model ID | Use case |
|------|----------|----------|
| Low | `gpt-5.4-nano` | Fast, latency-sensitive (quiz generation/evaluation) |
| Medium | `gpt-5.4-mini` | Balanced quality and speed |
| High | `gpt-5.4` | Highest quality (OCR cleaning) |

## Architecture

Follows the existing provider pattern exactly — `LLMClient` protocol, model registry, factory dispatch. No new abstractions.

### Backend — New file

**`src/python/llm/openai_provider.py`**

```
class OpenAIProvider:
    __init__(api_key, default_model="gpt-5.4-nano")
    complete(messages, model=None) -> str
    get_provider() -> "openai"
    list_models() -> list[str]
```

- Uses the `openai` Python SDK
- `complete()` calls `client.chat.completions.create(model=..., messages=..., max_tokens=1024)`
- Error mapping:
  - `openai.RateLimitError` → `RATE_LIMIT`
  - `openai.AuthenticationError` → `AUTH`
  - `openai.APIConnectionError` → `TIMEOUT`
  - Everything else → `UNKNOWN`

### Backend — Registry updates

**`src/python/llm/models.py`**

Add to `_DEFAULTS`:
```python
"openai": {
    "low": "gpt-5.4-nano",
    "medium": "gpt-5.4-mini",
    "high": "gpt-5.4",
},
```

Add to `_ENV_KEYS`:
```python
"openai": {
    "low": "OPENAI_MODEL_LOW",
    "medium": "OPENAI_MODEL_MEDIUM",
    "high": "OPENAI_MODEL_HIGH",
},
```

Add to `PROVIDER_LABELS`:
```python
"openai": "OpenAI",
```

Update `save_model_registry()` iteration order to include `"openai"`.

### Backend — Factory update

**`src/python/llm/factory.py`**

- Import `OpenAIProvider`
- Add `"openai": OpenAIProvider` to `_PROVIDERS` dict

### Config files

**`.env.example`** — append:
```
# OpenAI models
OPENAI_MODEL_LOW=gpt-5.4-nano
OPENAI_MODEL_MEDIUM=gpt-5.4-mini
OPENAI_MODEL_HIGH=gpt-5.4
```

**`config/settings.example.json`** — add provider entry:
```json
"openai": { "api_key": "", "default_model": "gpt-5.4-nano" }
```

### Frontend — Type updates

**`src/renderer/types/api.ts`**

- `SettingsConfig.providers`: add `openai: { api_key: string; default_model: string }`
- `ProviderKey`: add `"openai"` to union
- `ModelRegistry`: add `openai: ModelTier`

No Settings page changes needed — provider sections render dynamically from the config/registry.

### Dependency

Add `openai` to the Python requirements file.

## File change summary

| File | Action |
|------|--------|
| `src/python/llm/openai_provider.py` | New |
| `src/python/llm/models.py` | Edit |
| `src/python/llm/factory.py` | Edit |
| `src/python/llm/__init__.py` | Edit |
| `.env.example` | Edit |
| `config/settings.example.json` | Edit |
| `src/renderer/types/api.ts` | Edit |
| `requirements.txt` | Edit |
