from unittest.mock import MagicMock, patch

import pytest

from llm.zai_provider import ZaiProvider
from llm.base import LLMError, ErrorCategory
from llm.models import _DEFAULTS


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
        model=_DEFAULTS["zai"]["low"],
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
    assert _DEFAULTS["zai"]["low"] in models
    assert _DEFAULTS["zai"]["medium"] in models
