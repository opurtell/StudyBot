import json
import os
from unittest.mock import MagicMock, patch

import pytest

from llm.anthropic_provider import AnthropicProvider
from llm.factory import create_client, create_client_for_model, load_config
from llm.google_provider import GoogleProvider
from llm.models import load_model_registry, save_model_registry, resolve_provider_for_model
from llm.zai_provider import ZaiProvider

SAMPLE_CONFIG = {
    "providers": {
        "anthropic": {"api_key": "sk-test", "default_model": "claude-haiku-4-5-20251001"},
        "google": {"api_key": "g-test", "default_model": "gemini-3.1-flash-lite-preview"},
        "zai": {"api_key": "z-test", "default_model": "glm-4.7-flash"},
    },
    "active_provider": "anthropic",
    "quiz_model": "claude-haiku-4-5-20251001",
    "clean_model": "claude-opus-4.6",
}


def test_create_client_anthropic():
    client = create_client(SAMPLE_CONFIG)
    assert isinstance(client, AnthropicProvider)


def test_create_client_google():
    config = {**SAMPLE_CONFIG, "active_provider": "google"}
    with patch("llm.google_provider._create_google_client", return_value=MagicMock()):
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
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps(SAMPLE_CONFIG))
    loaded = load_config(config_path)
    assert loaded["active_provider"] == "anthropic"


def test_create_client_for_model_anthropic():
    client = create_client_for_model(SAMPLE_CONFIG, "claude-haiku-4-5-20251001")
    assert isinstance(client, AnthropicProvider)


def test_create_client_for_model_google():
    with patch("llm.google_provider._create_google_client", return_value=MagicMock()):
        client = create_client_for_model(SAMPLE_CONFIG, "gemini-2.5-pro")
    assert isinstance(client, GoogleProvider)


def test_create_client_for_model_zai():
    client = create_client_for_model(SAMPLE_CONFIG, "glm-4.7-flash")
    assert isinstance(client, ZaiProvider)


def test_create_client_for_model_unknown_falls_back_to_active_provider():
    client = create_client_for_model(SAMPLE_CONFIG, "unknown-model-xyz")
    assert isinstance(client, AnthropicProvider)


def test_load_model_registry_defaults(tmp_path, monkeypatch):
    monkeypatch.chattr = None
    for key in ("ZAI_MODEL_LOW", "ZAI_MODEL_MEDIUM", "ZAI_MODEL_HIGH",
                "ANTHROPIC_MODEL_LOW", "ANTHROPIC_MODEL_MEDIUM", "ANTHROPIC_MODEL_HIGH",
                "GOOGLE_MODEL_LOW", "GOOGLE_MODEL_MEDIUM", "GOOGLE_MODEL_HIGH"):
        monkeypatch.delenv(key, raising=False)

    import llm.models as m
    monkeypatch.setattr(m, "_ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(m, "_ENV_EXAMPLE_PATH", tmp_path / ".env.example")

    registry = m.load_model_registry()
    assert registry["anthropic"]["low"] == "claude-haiku-4-5-20251001"
    assert registry["google"]["high"] == "gemini-2.5-pro"
    assert registry["zai"]["medium"] == "glm-4.7"


def test_resolve_provider_for_model():
    assert resolve_provider_for_model("claude-opus-4.6") == "anthropic"
    assert resolve_provider_for_model("gemini-2.5-pro") == "google"
    assert resolve_provider_for_model("glm-5") == "zai"
    assert resolve_provider_for_model("does-not-exist") is None


def test_save_model_registry(tmp_path, monkeypatch):
    import llm.models as m
    env_path = tmp_path / ".env"
    monkeypatch.setattr(m, "_ENV_PATH", env_path)

    registry = {
        "zai": {"low": "glm-test-low", "medium": "glm-test-mid", "high": "glm-test-high"},
        "anthropic": {"low": "claude-test-low", "medium": "claude-test-mid", "high": "claude-test-high"},
        "google": {"low": "gemini-test-low", "medium": "gemini-test-mid", "high": "gemini-test-high"},
    }
    m.save_model_registry(registry)
    content = env_path.read_text()
    assert "ZAI_MODEL_LOW=glm-test-low" in content
    assert "ANTHROPIC_MODEL_HIGH=claude-test-high" in content


def test_save_model_registry_preserves_unrelated_env_entries(tmp_path, monkeypatch):
    import llm.models as m

    env_path = tmp_path / ".env"
    env_path.write_text("ANTHROPIC_API_KEY=existing-key\nCUSTOM_FLAG=yes\n")
    monkeypatch.setattr(m, "_ENV_PATH", env_path)

    registry = {
        "zai": {"low": "glm-test-low", "medium": "glm-test-mid", "high": "glm-test-high"},
        "anthropic": {"low": "claude-test-low", "medium": "claude-test-mid", "high": "claude-test-high"},
        "google": {"low": "gemini-test-low", "medium": "gemini-test-mid", "high": "gemini-test-high"},
    }

    m.save_model_registry(registry)

    content = env_path.read_text()
    assert "ANTHROPIC_API_KEY=existing-key" in content
    assert "CUSTOM_FLAG=yes" in content
