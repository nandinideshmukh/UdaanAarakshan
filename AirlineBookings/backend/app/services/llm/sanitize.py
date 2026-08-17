"""
Before ANY message list is handed to an adapter, it passes through here.
This is the explicit, defensive enforcement of the core rule: a provider
only ever sees its OWN provider_metadata namespace (if any), never
another provider's — most importantly, Gemini's `thought_signature` must
never reach OpenAI or Groq, and must never be fabricated if it's missing
when reconstructing a request back to Gemini.

This isn't just "adapters happen to only read their own key" (which would
also work) — it's enforced structurally here so a bug in one adapter
can't leak another provider's metadata by accident.
"""

from __future__ import annotations

import copy

from app.services.llm.types import LLMMessage


def sanitize_for_provider(messages: list[LLMMessage], provider: str) -> list[LLMMessage]:
    sanitized: list[LLMMessage] = []
    for msg in messages:
        new_msg = copy.deepcopy(msg)
        new_msg.provider_metadata = {
            k: v for k, v in new_msg.provider_metadata.items() if k == provider
        }
        for tc in new_msg.tool_calls:
            tc.provider_metadata = {k: v for k, v in tc.provider_metadata.items() if k == provider}
        sanitized.append(new_msg)
    return sanitized
