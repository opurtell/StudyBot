from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from .base import LLMError, ErrorCategory
from .models import load_model_registry


@dataclass
class _GoogleGenAICompatClient:
    client: Any
    types: Any | None = None
    is_legacy: bool = False


def _create_google_client(api_key: str) -> _GoogleGenAICompatClient:
    try:
        genai_module = import_module("google.genai")
        types_module = import_module("google.genai.types")
        client = genai_module.Client(api_key=api_key)
        return _GoogleGenAICompatClient(
            client=client,
            types=types_module,
            is_legacy=False,
        )
    except ImportError:
        legacy_module = import_module("google.generativeai")
        legacy_module.configure(api_key=api_key)
        return _GoogleGenAICompatClient(client=legacy_module, is_legacy=True)


class GoogleProvider:
    def __init__(self, api_key: str, default_model: str = "gemini-2.5-pro"):
        self._client = _create_google_client(api_key)
        self._default_model = default_model

    def complete(self, messages: list[dict], model: str | None = None) -> str:
        model_name = model or self._default_model
        try:
            # Extract system message if present
            system_message = next(
                (m["content"] for m in messages if m["role"] == "system"), None
            )

            # Format remaining messages as contents
            contents = []
            for m in messages:
                if m["role"] == "system":
                    continue
                # Gemini uses 'user' and 'model'
                role = "user" if m["role"] == "user" else "model"
                if self._client.is_legacy:
                    contents.append({"role": role, "parts": [m["content"]]})
                else:
                    types = self._client.types
                    contents.append(
                        types.Content(role=role, parts=[types.Part(text=m["content"])])
                    )

            if self._client.is_legacy:
                client = self._client.client.GenerativeModel(
                    model_name=model_name, system_instruction=system_message
                )
                response = client.generate_content(contents)
            else:
                config = None
                if system_message:
                    config = self._client.types.GenerateContentConfig(
                        system_instruction=system_message
                    )
                response = self._client.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )

            if not response.text:
                return ""

            return response.text
        except Exception as e:
            error_msg = str(e)
            category = ErrorCategory.UNKNOWN
            
            # Identify rate limit/quota errors from string (common in google-generativeai)
            if "429" in error_msg or "quota" in error_msg.lower() or "limit" in error_msg.lower():
                category = ErrorCategory.RATE_LIMIT
            elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                category = ErrorCategory.AUTH
                
            raise LLMError(error_msg, category) from e

    def get_provider(self) -> str:
        return "google"

    def list_models(self) -> list[str]:
        registry = load_model_registry()
        return list(registry.get("google", {}).values())
