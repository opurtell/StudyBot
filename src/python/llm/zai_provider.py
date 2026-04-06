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
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def get_provider(self) -> str:
        return "zai"

    def list_models(self) -> list[str]:
        registry = load_model_registry()
        return list(registry.get("zai", {}).values())
