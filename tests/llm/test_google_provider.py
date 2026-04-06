from unittest.mock import MagicMock, patch

import pytest

from llm.google_provider import GoogleProvider
from llm.base import LLMError, ErrorCategory
from llm.models import _DEFAULTS


@pytest.fixture
def mock_google_client():
    mock_client = MagicMock()
    mock_types = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Gemini response"
    mock_client.models.generate_content.return_value = mock_response
    compat_client = MagicMock(
        client=mock_client,
        types=mock_types,
        is_legacy=False,
    )
    with patch("llm.google_provider._create_google_client", return_value=compat_client):
        yield compat_client


def test_complete_returns_text(mock_google_client):
    provider = GoogleProvider(api_key="test-key")
    result = provider.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
    )
    assert result == "Gemini response"


def test_complete_calls_generate_content(mock_google_client):
    provider = GoogleProvider(api_key="test-key")
    provider.complete([{"role": "user", "content": "Hi"}])
    mock_google_client.client.models.generate_content.assert_called_once_with(
        model=_DEFAULTS["google"]["high"],
        contents=[{"role": "user", "parts": ["Hi"]}],
        config=None,
    )


def test_complete_uses_custom_model(mock_google_client):
    provider = GoogleProvider(
        api_key="test-key", default_model=_DEFAULTS["google"]["low"]
    )
    provider.complete([{"role": "user", "content": "Hi"}], model="gemini-2.5-pro")
    mock_google_client.client.models.generate_content.assert_called_once_with(
        model="gemini-2.5-pro",
        contents=[{"role": "user", "parts": ["Hi"]}],
        config=None,
    )


def test_complete_includes_system_instruction(mock_google_client):
    config = object()
    mock_google_client.types.GenerateContentConfig.return_value = config

    provider = GoogleProvider(api_key="test-key")
    provider.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
    )

    mock_google_client.types.GenerateContentConfig.assert_called_once_with(
        system_instruction="You are helpful."
    )
    mock_google_client.client.models.generate_content.assert_called_once_with(
        model=_DEFAULTS["google"]["high"],
        contents=[{"role": "user", "parts": ["Hi"]}],
        config=config,
    )


def test_complete_wraps_error(mock_google_client):
    mock_google_client.client.models.generate_content.side_effect = Exception("API error")
    provider = GoogleProvider(api_key="test-key")
    with pytest.raises(LLMError) as exc_info:
        provider.complete([{"role": "user", "content": "Hi"}])
    assert exc_info.value.category == ErrorCategory.UNKNOWN


def test_get_provider_returns_google(mock_google_client):
    provider = GoogleProvider(api_key="test-key")
    assert provider.get_provider() == "google"


def test_list_models(mock_google_client):
    provider = GoogleProvider(api_key="test-key")
    models = provider.list_models()
    assert _DEFAULTS["google"]["low"] in models
    assert _DEFAULTS["google"]["high"] in models
