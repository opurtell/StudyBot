import openai

from .base import LLMError, ErrorCategory
from .models import load_model_registry


class OpenAIProvider:
    def __init__(self, api_key: str, default_model: str = "gpt-5.4-nano"):
        self._client = openai.OpenAI(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model_name = model or self._default_model
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                max_tokens=1024,
                messages=messages,
            )
            content = response.choices[0].message.content
            return content if content else ""
        except openai.RateLimitError as e:
            raise LLMError(str(e), ErrorCategory.RATE_LIMIT) from e
        except openai.AuthenticationError as e:
            raise LLMError(str(e), ErrorCategory.AUTH) from e
        except openai.APIConnectionError as e:
            raise LLMError(str(e), ErrorCategory.TIMEOUT) from e
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "openai"

    def list_models(self) -> list[str]:
        registry = load_model_registry()
        return list(registry.get("openai", {}).values())
