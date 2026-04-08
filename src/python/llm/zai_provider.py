from zhipuai import ZhipuAI

from .base import LLMError, ErrorCategory
from .models import load_model_registry


class ZaiProvider:
    def __init__(self, api_key: str, default_model: str = "glm-4.7-flash"):
        self._client = ZhipuAI(api_key=api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model_name = model or self._default_model
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            category = ErrorCategory.UNKNOWN

            if "429" in error_msg or "quota" in error_msg.lower() or "limit" in error_msg.lower():
                category = ErrorCategory.RATE_LIMIT
            elif "401" in error_msg or "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                category = ErrorCategory.AUTH

            raise LLMError(error_msg, category) from e

    def get_provider(self) -> str:
        return "zai"

    def list_models(self) -> list[str]:
        registry = load_model_registry()
        return list(registry.get("zai", {}).values())
