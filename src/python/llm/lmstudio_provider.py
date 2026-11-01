"""LM Studio provider — talks to a local OpenAI-compatible server on the user's machine.

LM Studio exposes an OpenAI-compatible REST API (default http://127.0.0.1:1234/v1),
so the existing ``openai`` SDK is reused with the base URL pointed at localhost.
No API key is required; the SDK still needs a non-empty placeholder.
"""

from __future__ import annotations

import re

import openai
import requests

from .base import ErrorCategory, LLMError
from .local_tuning import needs_structured_output
from .models import load_model_registry

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"

# The server ignores the key, but the SDK refuses to construct a client without one.
_PLACEHOLDER_KEY = "lm-studio"

# Local generation on laptop silicon can take a while to load a model into memory
# and stream a long answer, so allow far more headroom than the hosted providers.
_TIMEOUT_SECONDS = 600.0

# Reasoning models spend part of this budget thinking before they emit any answer, and
# local tokens cost nothing, so the ceiling is far higher than the hosted providers' 1024.
_MAX_TOKENS = 4096

# Reasoning is suppressed by default. Every model tested accepted the parameter, and it is
# worth a lot on this workload: it cut gemma-4-e4b from 38 s to ~7 s and qwen3.6-35b-a3b
# from 39 s to ~7 s per evaluation, with no loss of grading accuracy. The app never shows
# chain of thought, so paying for it buys nothing. Set "low"/"medium"/"high" to opt back in.
DEFAULT_REASONING_EFFORT = "none"

# Some models inline their chain of thought in the reply rather than reporting it
# separately; the quiz agent must never see it.
_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)

_UNREACHABLE_HINT = (
    "Could not reach LM Studio at {base_url}. Open LM Studio, go to the Developer "
    "tab, and make sure the local server is running."
)


def normalise_base_url(base_url: str | None) -> str:
    """Return a usable LM Studio base URL, tolerating a missing /v1 suffix."""
    url = (base_url or "").strip().rstrip("/")
    if not url:
        return DEFAULT_BASE_URL
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


class LMStudioProvider:
    def __init__(
        self,
        api_key: str = "",
        default_model: str = DEFAULT_MODEL,
        base_url: str = "",
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    ):
        self._base_url = normalise_base_url(base_url)
        self._default_model = default_model or DEFAULT_MODEL
        self._reasoning_effort = (reasoning_effort or "").strip().lower()
        # Servers other than LM Studio may reject the parameter; drop it after one refusal
        # rather than failing every subsequent call.
        self._send_reasoning_effort = bool(self._reasoning_effort)
        self._client = openai.OpenAI(
            api_key=api_key or _PLACEHOLDER_KEY,
            base_url=self._base_url,
            timeout=_TIMEOUT_SECONDS,
            max_retries=1,
        )

    def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        response_schema: dict | None = None,
    ) -> str:
        model_name = model or self._default_model
        try:
            response = self._create(model_name, messages, response_schema)
            choice = response.choices[0]
            answer = _strip_reasoning(choice.message.content)
            if not answer:
                raise LLMError(
                    self._empty_answer_hint(model_name, choice.finish_reason),
                    ErrorCategory.UNKNOWN,
                )
            return answer
        except LLMError:
            raise
        except openai.APIConnectionError as e:
            raise LLMError(
                _UNREACHABLE_HINT.format(base_url=self._base_url),
                ErrorCategory.TIMEOUT,
            ) from e
        except openai.NotFoundError as e:
            raise LLMError(
                f"LM Studio has no model named '{model_name}'. Load it in LM Studio "
                f"or pick a different model in Settings.",
                ErrorCategory.UNKNOWN,
            ) from e
        except Exception as e:
            raise LLMError(str(e), ErrorCategory.UNKNOWN) from e

    def _create(
        self,
        model_name: str,
        messages: list[dict],
        response_schema: dict | None = None,
    ):
        """Request a completion, retrying bare if the server rejects the extra parameters.

        The schema is applied only to models that need it — constrained decoding costs
        `gpt-oss-20b` four grading points, so it is never sent by default.
        """
        kwargs = {"model": model_name, "max_tokens": _MAX_TOKENS, "messages": messages}
        extra: dict = {}
        if self._send_reasoning_effort:
            extra["reasoning_effort"] = self._reasoning_effort
        if response_schema and needs_structured_output(model_name):
            extra["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": response_schema,
                },
            }

        if extra:
            try:
                return self._client.chat.completions.create(**kwargs, extra_body=extra)
            except openai.BadRequestError:
                # An OpenAI-compatible server that is not LM Studio may not know these
                # parameters. Stop sending the reasoning hint and fall back to a plain
                # request rather than failing every call from here on.
                self._send_reasoning_effort = False
        return self._client.chat.completions.create(**kwargs)

    @staticmethod
    def _empty_answer_hint(model_name: str, finish_reason: str | None) -> str:
        if finish_reason == "length":
            return (
                f"{model_name} used its entire {_MAX_TOKENS} token budget on internal "
                f"reasoning without producing an answer. This model ignores the request "
                f"to disable reasoning — choose a different model in Settings."
            )
        return f"{model_name} returned an empty response."

    def get_provider(self) -> str:
        return "lmstudio"

    def get_base_url(self) -> str:
        return self._base_url

    def get_model(self) -> str:
        """The model this client will use when the caller does not name one."""
        return self._default_model

    def list_models(self) -> list[str]:
        """Model IDs available on the running server, falling back to the registry."""
        try:
            return [m["id"] for m in list_server_models(self._base_url)]
        except LLMError:
            registry = load_model_registry()
            return list(registry.get("lmstudio", {}).values())


def _strip_reasoning(content: str | None) -> str:
    """Remove any inline chain-of-thought block and surrounding whitespace."""
    if not content:
        return ""
    return _THINK_BLOCK.sub("", content).strip()


# Model types LM Studio reports that cannot serve chat completions.
_NON_CHAT_TYPES = {"embeddings"}


def _list_via_native_api(base_url: str) -> list[dict] | None:
    """Read LM Studio's own /api/v0/models, which reports model type and load state.

    Returns None if the endpoint is unavailable, so the caller can fall back to the
    OpenAI-compatible listing.
    """
    native_url = base_url[: -len("/v1")] + "/api/v0/models"
    try:
        response = requests.get(native_url, timeout=10)
        response.raise_for_status()
        entries = response.json().get("data", [])
    except (requests.RequestException, ValueError):
        return None

    models: list[dict] = []
    for entry in entries:
        model_id = entry.get("id")
        model_type = entry.get("type", "llm")
        if not model_id or model_type in _NON_CHAT_TYPES:
            continue
        models.append(
            {
                "id": model_id,
                "type": model_type,
                "loaded": entry.get("state") == "loaded",
            }
        )
    return models


def list_server_models(base_url: str | None = None) -> list[dict]:
    """Chat-capable models a running LM Studio server can serve.

    Each entry has ``id``, ``type`` ("llm" or "vlm") and ``loaded``. Embedding models
    are excluded — they cannot answer quiz prompts.

    Raises:
        LLMError: If the server is unreachable or returns an error.
    """
    url = normalise_base_url(base_url)

    native = _list_via_native_api(url)
    if native is not None:
        return native

    # Fall back to the OpenAI-compatible listing, which carries no type information.
    client = openai.OpenAI(api_key=_PLACEHOLDER_KEY, base_url=url, timeout=10.0, max_retries=0)
    try:
        return [{"id": m.id, "type": "llm", "loaded": False} for m in client.models.list().data]
    except openai.APIConnectionError as e:
        raise LLMError(_UNREACHABLE_HINT.format(base_url=url), ErrorCategory.TIMEOUT) from e
    except Exception as e:
        raise LLMError(str(e), ErrorCategory.UNKNOWN) from e
