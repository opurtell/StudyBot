from unittest.mock import MagicMock, patch

import pytest

from llm.anthropic_provider import AnthropicProvider
from llm.base import LLMError, ErrorCategory
from llm.models import _DEFAULTS


@pytest.fixture
def mock_anthropic():
    with patch("llm.anthropic_provider.anthropic") as mock_mod:
        mock_client = MagicMock()
        mock_mod.Anthropic.return_value = mock_client
        mock_mod.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_mod.AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_mod.APIConnectionError = type("APIConnectionError", (Exception,), {})
        yield mock_client


def test_complete_returns_text(mock_anthropic):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response")]
    mock_anthropic.messages.create.return_value = mock_response

    provider = AnthropicProvider(api_key="test-key")
    result = provider.complete([{"role": "user", "content": "Hello"}])

    assert result == "Test response"
    mock_anthropic.messages.create.assert_called_once_with(
        model=_DEFAULTS["anthropic"]["low"],
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
    assert _DEFAULTS["anthropic"]["low"] in models
    assert _DEFAULTS["anthropic"]["high"] in models
