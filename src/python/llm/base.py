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
    def complete(self, messages: list[dict], model: str | None = None) -> str: ...
    def get_provider(self) -> str: ...
    def list_models(self) -> list[str]: ...
