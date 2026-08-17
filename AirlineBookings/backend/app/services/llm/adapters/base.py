"""
Every provider adapter implements this interface. The gateway
(orchestrator.py) only ever calls `send()` and only ever sees LLMMessage/
LLMResponse — all provider-specific request/response shape translation,
tool-schema conversion, and error normalization happens inside the
adapter and never leaks out.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.llm.types import LLMMessage, LLMResponse


class ProviderAdapter(ABC):
    name: str

    @abstractmethod
    async def send(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[dict],
        max_tokens: int = 1536,
    ) -> LLMResponse:
        """
        `tools` uses the existing Anthropic-style schema convention already
        used throughout this codebase: [{"name", "description", "input_schema"}].
        Each adapter converts that to its own provider's tool-schema format.
        """
        raise NotImplementedError
