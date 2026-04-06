import anthropic

from .base import LLMError, ErrorCategory
from .models import load_model_registry


class AnthropicProvider:
    def __init__(self, api_key: str, default_model: str = "claude-haiku-4-5-20251001"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model = model or self._default_model
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=1024,
                messages=messages,
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            raise LLMError(str(e), ErrorCategory.RATE_LIMIT) from e
        except anthropic.AuthenticationError as e:
            raise LLMError(str(e), ErrorCategory.AUTH) from e
        except anthropic.APIConnectionError as e:
            raise LLMError(str(e), ErrorCategory.TIMEOUT) from e
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "anthropic"

    def list_models(self) -> list[str]:
        registry = load_model_registry()
        return list(registry.get("anthropic", {}).values())
