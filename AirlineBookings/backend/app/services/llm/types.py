"""
Provider-neutral internal representation for LLM conversations with tool
use. Every orchestrator (agentic_orchestrator.py, chat_orchestrator.py)
builds and consumes ONLY these types — never a provider's raw wire format.

The critical design point is `provider_metadata` on LLMToolCall: it's a
namespaced dict (e.g. {"gemini": {"thought_signature": "..."}}) so
provider-specific data can ride alongside a tool call without ever being
misread as a generic field, and so it can be stripped per-provider before
a request is sent to a DIFFERENT provider (see sanitize.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "tool"]


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Namespaced per-provider metadata, e.g. {"gemini": {"thought_signature": "..."}}.
    # NEVER populate a provider's key with a fabricated/placeholder value —
    # only ever copy through exactly what that provider returned.
    provider_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class LLMToolResult:
    tool_call_id: str
    name: str
    content: dict[str, Any]


@dataclass
class LLMMessage:
    role: Role
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tool_result: LLMToolResult | None = None  # set only when role == "tool"
    provider_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class LLMResponse:
    message: LLMMessage
    provider: str
    model: str
    raw: dict[str, Any] | None = None  # for debugging only — never logged verbatim
