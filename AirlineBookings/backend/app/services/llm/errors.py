"""
Every provider adapter catches its own provider's raw errors (HTTP status
codes, provider-specific error bodies) and re-raises one of these instead
— so the gateway and application code never need to know which provider
they're talking to in order to decide how to react to a failure.
"""

from __future__ import annotations

from typing import Any


class LLMError(Exception):
    def __init__(self, message: str, provider: str | None = None, raw: Any = None, retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.raw = raw
        self.retryable = retryable

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider!r}, retryable={self.retryable}, {super().__str__()!r})"


class LLMTimeoutError(LLMError):
    def __init__(self, message: str = "Request timed out", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class RateLimitError(LLMError):
    def __init__(self, message: str = "Rate limited", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class AuthenticationError(LLMError):
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class InvalidRequestError(LLMError):
    """
    Malformed request — including a Gemini thought_signature that failed
    Base64 validation. NEVER retry the same payload unchanged on this
    error; the caller must either drop the offending field or give up.
    """

    def __init__(self, message: str = "Invalid request", **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class ToolCallError(LLMError):
    def __init__(self, message: str = "Tool call failed", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class ProviderUnavailableError(LLMError):
    def __init__(self, message: str = "Provider unavailable", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class ModelUnavailableError(LLMError):
    """E.g. a model was decommissioned — retrying won't help, the model string itself is wrong."""

    def __init__(self, message: str = "Model unavailable", **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class UnknownProviderError(LLMError):
    def __init__(self, message: str = "Unknown provider", **kwargs):
        super().__init__(message, retryable=False, **kwargs)
