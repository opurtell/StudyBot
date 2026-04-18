from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from paths import PROJECT_ROOT

_ENV_PATH = PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

_DEFAULTS: dict[str, dict[str, str]] = {
    "zai": {
        "low": "glm-4.7-flash",
        "medium": "glm-4.7",
        "high": "glm-5",
    },
    "anthropic": {
        "low": "claude-haiku-4-5-20251001",
        "medium": "claude-sonnet-4.6",
        "high": "claude-opus-4.6",
    },
    "google": {
        "low": "gemini-3.1-flash-lite-preview",
        "medium": "gemini-3-flash-preview",
        "high": "gemini-2.5-pro",
    },
    "openai": {
        "low": "gpt-5.4-nano",
        "medium": "gpt-5.4-mini",
        "high": "gpt-5.4",
    },
}

_ENV_KEYS: dict[str, dict[str, str]] = {
    "zai": {
        "low": "ZAI_MODEL_LOW",
        "medium": "ZAI_MODEL_MEDIUM",
        "high": "ZAI_MODEL_HIGH",
    },
    "anthropic": {
        "low": "ANTHROPIC_MODEL_LOW",
        "medium": "ANTHROPIC_MODEL_MEDIUM",
        "high": "ANTHROPIC_MODEL_HIGH",
    },
    "google": {
        "low": "GOOGLE_MODEL_LOW",
        "medium": "GOOGLE_MODEL_MEDIUM",
        "high": "GOOGLE_MODEL_HIGH",
    },
    "openai": {
        "low": "OPENAI_MODEL_LOW",
        "medium": "OPENAI_MODEL_MEDIUM",
        "high": "OPENAI_MODEL_HIGH",
    },
}

PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic",
    "google": "Google",
    "zai": "Z.ai",
    "openai": "OpenAI",
}

TIER_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}


def _ensure_env() -> None:
    if not _ENV_PATH.exists() and _ENV_EXAMPLE_PATH.exists():
        shutil.copy2(_ENV_EXAMPLE_PATH, _ENV_PATH)


def load_model_registry() -> dict[str, dict[str, str]]:
    _ensure_env()
    load_dotenv(_ENV_PATH, override=True)

    registry: dict[str, dict[str, str]] = {}
    for provider, tiers in _ENV_KEYS.items():
        registry[provider] = {}
        for tier, env_key in tiers.items():
            registry[provider][tier] = os.getenv(env_key, _DEFAULTS[provider][tier])
    return registry


def save_model_registry(registry: dict[str, dict[str, str]]) -> None:
    _ensure_env()
    existing_lines = _ENV_PATH.read_text().splitlines() if _ENV_PATH.exists() else []
    managed_keys = {
        env_key
        for provider_tiers in _ENV_KEYS.values()
        for env_key in provider_tiers.values()
    }
    preserved_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            preserved_lines.append(line)
            continue
        key, sep, _ = line.partition("=")
        if sep and key.strip() in managed_keys:
            continue
        preserved_lines.append(line)

    lines: list[str] = [line for line in preserved_lines if line.strip()]
    if lines:
        lines.append("")
    for provider in ("zai", "anthropic", "google", "openai"):
        label = PROVIDER_LABELS.get(provider, provider)
        lines.append(f"# {label} models")
        for tier in ("low", "medium", "high"):
            env_key = _ENV_KEYS[provider][tier]
            value = registry.get(provider, {}).get(tier, _DEFAULTS[provider][tier])
            lines.append(f"{env_key}={value}")
        lines.append("")

    _ENV_PATH.write_text("\n".join(lines).rstrip() + "\n")
    load_dotenv(_ENV_PATH, override=True)


def resolve_provider_for_model(model_id: str) -> str | None:
    registry = load_model_registry()
    for provider, tiers in registry.items():
        if model_id in tiers.values():
            return provider
    return None


def all_model_ids() -> list[str]:
    registry = load_model_registry()
    ids: list[str] = []
    for tiers in registry.values():
        ids.extend(tiers.values())
    return ids
