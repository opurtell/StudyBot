from typing import Protocol


class LLMError(Exception):
    def __init__(self, message: str, category: str):
        super().__init__(message)
        self.category = category


class ErrorCategory:
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        response_schema: dict | None = None,
    ) -> str:
        """Complete a chat exchange.

        ``response_schema`` offers the JSON shape the caller wants back. It is a hint,
        not a demand: a provider may ignore it. Only the LM Studio provider acts on it,
        and only for local models that cannot produce parseable JSON unaided —
        constrained decoding measurably degrades some models, so it is opt-in per model.
        """
        ...
    def get_provider(self) -> str: ...
    def list_models(self) -> list[str]: ...
