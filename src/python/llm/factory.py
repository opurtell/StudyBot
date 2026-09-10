from __future__ import annotations

import json
from pathlib import Path

from paths import EXAMPLE_SETTINGS_PATH as _EXAMPLE_CONFIG_PATH
from paths import SETTINGS_PATH as _DEFAULT_CONFIG_PATH

from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
from .lmstudio_provider import LMStudioProvider
from .models import load_model_registry, resolve_provider_for_model
from .openai_provider import OpenAIProvider
from .zai_provider import ZaiProvider

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "openai": OpenAIProvider,
    "zai": ZaiProvider,
    "lmstudio": LMStudioProvider,
}

# Providers pointed at a user-configurable endpoint rather than a fixed vendor host.
_BASE_URL_PROVIDERS = {"lmstudio"}


def _build(provider: str, provider_config: dict, model: str):
    kwargs = {
        "api_key": provider_config.get("api_key", ""),
        "default_model": model,
    }
    if provider in _BASE_URL_PROVIDERS:
        kwargs["base_url"] = provider_config.get("base_url", "")
        if "reasoning_effort" in provider_config:
            kwargs["reasoning_effort"] = provider_config["reasoning_effort"]
    return _PROVIDERS[provider](**kwargs)


def create_client(config: dict):
    active = config["active_provider"]
    if active not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {active}")
    provider_config = config["providers"][active]
    return _build(active, provider_config, provider_config["default_model"])


def create_client_for_model(config: dict, model_id: str):
    provider = resolve_provider_for_model(model_id)
    if provider is None:
        provider = config.get("active_provider", "anthropic")
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return _build(provider, config["providers"][provider], model_id)


_DEFAULT_PROVIDERS = {
    "anthropic": {"api_key": "", "default_model": "claude-haiku-4-5-20251001"},
    "google": {"api_key": "", "default_model": "gemini-3.1-flash-lite-preview"},
    "zai": {"api_key": "", "default_model": "glm-4.7-flash"},
    "openai": {"api_key": "", "default_model": "gpt-5.4-nano"},
    "lmstudio": {
        "api_key": "",
        "default_model": "openai/gpt-oss-20b",
        "base_url": "http://127.0.0.1:1234/v1",
    },
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
