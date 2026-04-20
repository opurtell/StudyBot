"""Tests for LLM vision module."""

from __future__ import annotations

import os

import pytest


def test_vision_module_importable():
    """Test that the vision module can be imported and has expected exports."""
    from src.python.llm.vision import VisionNotSupportedError, _cache, describe_flowchart

    assert callable(describe_flowchart)
    assert issubclass(VisionNotSupportedError, Exception)
    assert isinstance(_cache, dict)


def test_vision_cache_is_dict():
    """Test that the vision cache is a dictionary."""
    from src.python.llm.vision import _cache

    assert isinstance(_cache, dict)
    # Cache should be empty at import
    assert len(_cache) == 0


def test_vision_not_supported_error_for_unsupported_provider():
    """Test that VisionNotSupportedError is raised for unsupported providers."""
    from src.python.llm.vision import VisionNotSupportedError, describe_flowchart

    # Z.ai models should raise VisionNotSupportedError
    with pytest.raises(VisionNotSupportedError) as exc_info:
        describe_flowchart(b"test_image_bytes", model_id="glm-4.7-flash")

    assert "does not support vision" in str(exc_info.value)
    assert "glm-4.7-flash" in str(exc_info.value)


def test_vision_not_supported_error_message_format():
    """Test that VisionNotSupportedError has helpful message format."""
    from src.python.llm.vision import VisionNotSupportedError, describe_flowchart

    with pytest.raises(VisionNotSupportedError) as exc_info:
        describe_flowchart(b"test", model_id="glm-4.7")

    error_msg = str(exc_info.value)
    assert "glm-4.7" in error_msg
    assert "zai" in error_msg.lower() or "provider" in error_msg.lower()
    assert "vision" in error_msg.lower()


def test_vision_cache_functionality():
    """Test basic cache operations without API calls."""
    from src.python.llm.vision import _cache, clear_cache, get_cache_size

    # Clear cache to start fresh
    clear_cache()
    assert get_cache_size() == 0

    # Test that clear_cache works
    _cache["test_key"] = "test_value"
    assert get_cache_size() == 1
    clear_cache()
    assert get_cache_size() == 0


def test_supports_vision_for_known_providers():
    """Test supports_vision function for known providers."""
    from src.python.llm.vision import supports_vision

    # Anthropic models should support vision
    assert supports_vision("claude-sonnet-4.6") is True
    assert supports_vision("claude-opus-4.6") is True

    # Google models should support vision
    assert supports_vision("gemini-2.5-pro") is True

    # Z.ai models should NOT support vision
    assert supports_vision("glm-4.7") is False
    assert supports_vision("glm-4.7-flash") is False

    # OpenAI models should support vision
    assert supports_vision("gpt-5.4") is True

    # Unknown models should default to False
    assert supports_vision("unknown-model") is False


# Tests below are gated behind AT_VISION_TESTS=1 because they require real API credentials
vision_api_tests = pytest.mark.skipif(
    not os.environ.get("AT_VISION_TESTS"),
    reason="Vision tests require AT_VISION_TESTS=1"
)


@vision_api_tests
def test_describe_flowchart_returns_mermaid():
    """Test that describe_flowchart returns valid Mermaid syntax."""
    from src.python.llm.vision import describe_flowchart

    # This test requires real API credentials and a real image
    # For now, we test with mock bytes - will be properly tested with AT_VISION_TESTS=1
    result = describe_flowchart(b"test_image_bytes", model_id="test-model")
    # Should contain Mermaid graph syntax
    assert "graph TD" in result or "graph LR" in result or "graph TB" in result


@vision_api_tests
def test_describe_flowchart_caches_by_hash():
    """Test that describe_flowchart caches results by image hash."""
    from src.python.llm.vision import _cache, describe_flowchart

    _cache.clear()

    # First call
    result1 = describe_flowchart(b"test_image_bytes", model_id="test-model")
    # Second call with same input should return cached result
    result2 = describe_flowchart(b"test_image_bytes", model_id="test-model")

    assert result1 == result2
    # Cache should have one entry
    assert len(_cache) == 1


@vision_api_tests
def test_describe_flowchart_different_models_different_cache_entries():
    """Test that different models create separate cache entries."""
    from src.python.llm.vision import _cache, describe_flowchart

    _cache.clear()

    # Same image, different model
    result1 = describe_flowchart(b"test_image_bytes", model_id="test-model-1")
    result2 = describe_flowchart(b"test_image_bytes", model_id="test-model-2")

    # Results may differ based on model, but cache should have 2 entries
    assert len(_cache) == 2


@vision_api_tests
def test_describe_flowchart_different_images_different_cache_entries():
    """Test that different images create separate cache entries."""
    from src.python.llm.vision import _cache, describe_flowchart

    _cache.clear()

    # Different images
    result1 = describe_flowchart(b"image_one", model_id="test-model")
    result2 = describe_flowchart(b"image_two", model_id="test-model")

    # Cache should have 2 entries
    assert len(_cache) == 2


@vision_api_tests
def test_describe_flowchart_custom_prompt():
    """Test that custom prompts are passed through correctly."""
    from src.python.llm.vision import describe_flowchart

    custom_prompt = "Extract only the decision points from this flowchart."
    result = describe_flowchart(
        b"test_image_bytes",
        model_id="test-model",
        prompt=custom_prompt
    )

    # Result should still be valid Mermaid
    assert "graph " in result
