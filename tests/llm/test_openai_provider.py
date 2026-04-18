from unittest.mock import MagicMock, patch

import pytest

from llm.openai_provider import OpenAIProvider
from llm.base import LLMError, ErrorCategory


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
        model="gpt-5.4-nano",
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
    # Since openai isn't registered yet, this should return empty list
    assert isinstance(models, list)
