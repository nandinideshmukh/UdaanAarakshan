"""
Structured logging for every LLM gateway call. Deliberately logs only
metadata (provider, model, timing, whether a tool was called, whether
fallback triggered and why) — never prompt content, tool arguments, or
API keys, since those can carry sensitive traveler/booking data.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def log_attempt(request_id: str, provider: str, model: str, attempt: int):
    start = time.monotonic()
    outcome = {"tool_call": False, "error_type": None}
    try:
        yield outcome
    finally:
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        print(
            f"[llm] request_id={request_id} provider={provider} model={model} "
            f"attempt={attempt} tool_call={outcome['tool_call']} "
            f"latency_ms={latency_ms} error_type={outcome['error_type']}"
        )


def log_fallback(request_id: str, from_provider: str, to_provider: str | None, reason: str):
    print(
        f"[llm] request_id={request_id} fallback_triggered=true "
        f"from={from_provider} to={to_provider or 'NONE (exhausted)'} reason={reason}"
    )
