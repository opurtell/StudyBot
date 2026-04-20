from __future__ import annotations

import json
from pathlib import Path

from paths import EXAMPLE_SETTINGS_PATH as _EXAMPLE_CONFIG_PATH
from paths import SETTINGS_PATH as _DEFAULT_CONFIG_PATH

from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
from .models import load_model_registry, resolve_provider_for_model
from .openai_provider import OpenAIProvider
from .zai_provider import ZaiProvider

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "openai": OpenAIProvider,
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


def create_client_for_model(config: dict, model_id: str):
    provider = resolve_provider_for_model(model_id)
    if provider is None:
        provider = config.get("active_provider", "anthropic")
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    provider_config = config["providers"][provider]
    return _PROVIDERS[provider](
        api_key=provider_config["api_key"],
        default_model=model_id,
    )


_DEFAULT_PROVIDERS = {
    "anthropic": {"api_key": "", "default_model": "claude-haiku-4-5-20251001"},
    "google": {"api_key": "", "default_model": "gemini-3.1-flash-lite-preview"},
    "zai": {"api_key": "", "default_model": "glm-4.7-flash"},
    "openai": {"api_key": "", "default_model": "gpt-5.4-nano"},
}


def load_config(path: str | Path = _DEFAULT_CONFIG_PATH) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        config_path = _EXAMPLE_CONFIG_PATH
    with open(config_path) as f:
        config = json.load(f)
    # Ensure all providers exist (handles old configs missing new providers)
    providers = config.setdefault("providers", {})
    for key, defaults in _DEFAULT_PROVIDERS.items():
        if key not in providers:
            providers[key] = dict(defaults)
    return config
