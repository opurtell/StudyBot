"""Vision LLM module for flowchart extraction."""

from __future__ import annotations

import hashlib
import logging
from typing import Literal

from .models import resolve_provider_for_model

logger = logging.getLogger(__name__)

# SHA-256 keyed cache to avoid re-billing on re-runs
_cache: dict[str, str] = {}

# Providers that support vision (based on current API capabilities)
VISION_CAPABLE_PROVIDERS = {"anthropic", "google", "openai"}

# Mermaid graph directions
GraphDirection = Literal["TD", "TB", "LR", "RL"]
DEFAULT_GRAPH_DIRECTION: GraphDirection = "TD"


class VisionNotSupportedError(Exception):
    """Raised when the selected model/provider does not support vision."""

    def __init__(self, model_id: str, provider: str) -> None:
        self.model_id = model_id
        self.provider = provider
        message = (
            f"Model {model_id} via {provider} does not support vision inputs. "
            f"Please select a vision-capable model in Settings."
        )
        super().__init__(message)


def _create_default_prompt() -> str:
    """Create the default flowchart extraction prompt.

    Returns:
        Default prompt for vision LLM flowchart extraction
    """
    return (
        "You are a clinical flowchart extraction tool. Analyse this flowchart image "
        "and produce a Mermaid.js graph that faithfully represents the clinical decision "
        f"logic. Use 'graph {DEFAULT_GRAPH_DIRECTION}' (top-down) layout. "
        "Label each node with the exact clinical text visible in the image. "
        "Preserve all decision branches, outcomes, and loops. "
        "Output ONLY the Mermaid code block, no explanation."
    )


def _call_vision_api(image_bytes: bytes, model_id: str, prompt: str) -> str:
    """Call the vision API for the given model.

    This is a stub implementation that returns a placeholder. The full
    implementation would integrate with the provider's vision API.

    Args:
        image_bytes: Image data as bytes
        model_id: Model identifier
        prompt: Prompt to send with the image

    Returns:
        Mermaid.js syntax string

    Raises:
        VisionNotSupportedError: If the provider doesn't support vision
    """
    # Stub implementation - returns placeholder
    # Full implementation would call the actual vision API
    logger.warning(
        "Vision API call is stub implementation. "
        "Full API integration requires provider-specific vision support."
    )

    return f"%% Vision extraction for {model_id}\n{prompt}\ngraph {DEFAULT_GRAPH_DIRECTION}\n    Stub[\"Vision API integration pending\"]\n"


def describe_flowchart(
    image_bytes: bytes,
    model_id: str,
    prompt: str | None = None,
) -> str:
    """Send a flowchart image to a vision-capable LLM and receive Mermaid text.

    Cache keyed by SHA-256(image_bytes) + model_id to avoid re-billing.

    Args:
        image_bytes: Image data as bytes
        model_id: Model identifier (e.g., "claude-sonnet-4.6")
        prompt: Optional custom prompt. If None, uses default clinical prompt.

    Returns:
        Mermaid.js syntax string representing the flowchart

    Raises:
        VisionNotSupportedError: If the model/provider doesn't support vision.
    """
    # Check cache first
    cache_key = hashlib.sha256(image_bytes).hexdigest() + f":{model_id}"
    if cache_key in _cache:
        logger.info("Vision cache hit for %s", cache_key[:16])
        return _cache[cache_key]

    # Resolve provider from model_id
    provider = resolve_provider_for_model(model_id)
    if provider is None:
        # Default to anthropic if unknown
        provider = "anthropic"

    # Check if provider supports vision
    if provider not in VISION_CAPABLE_PROVIDERS:
        raise VisionNotSupportedError(model_id, provider)

    # Use default prompt if not provided
    if prompt is None:
        prompt = _create_default_prompt()

    # Call vision API (stub implementation)
    result = _call_vision_api(image_bytes, model_id, prompt)

    # Cache result
    _cache[cache_key] = result
    logger.info("Vision cache miss for %s - cached result", cache_key[:16])

    return result


def clear_cache() -> None:
    """Clear the vision cache.

    Useful for testing or when you want to force re-extraction.
    """
    _cache.clear()
    logger.info("Vision cache cleared")


def get_cache_size() -> int:
    """Get the current size of the vision cache.

    Returns:
        Number of cached entries
    """
    return len(_cache)


def supports_vision(model_id: str) -> bool:
    """Check if a model supports vision inputs.

    Args:
        model_id: Model identifier

    Returns:
        True if the model's provider supports vision, False otherwise
    """
    provider = resolve_provider_for_model(model_id)
    if provider is None:
        # Unknown models default to not supporting vision
        return False
    return provider in VISION_CAPABLE_PROVIDERS
