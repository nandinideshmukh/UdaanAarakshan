"""
The LLM Orchestrator layer: Application (agents/*_orchestrator.py) -> here
-> Provider Adapter -> Gemini/OpenAI/Groq.

This is the ONLY place that knows there's more than one provider. It:
  - Picks a fallback chain (configurable via settings.LLM_PROVIDER_PRIORITY,
    or pass one explicitly per call).
  - Sanitizes messages for each provider before sending (strips other
    providers' metadata — see sanitize.py).
  - Normalizes every adapter's errors into LLMError already, so this
    module just needs to catch LLMError and try the next provider.
  - Logs each attempt and any fallback (metadata only, never prompt content).

Application code (the orchestrators) only ever imports `call_llm_with_tools`
from here and works entirely in LLMMessage/LLMToolCall/LLMResponse types.
"""

from __future__ import annotations

from app.config import settings
from app.services.llm.adapters.base import ProviderAdapter
from app.services.llm.adapters.gemini_adapter import GeminiAdapter
from app.services.llm.adapters.groq_adapter import GroqAdapter
from app.services.llm.adapters.openai_adapter import OpenAIAdapter
from app.services.llm.errors import LLMError, UnknownProviderError
from app.services.llm.logging_utils import log_attempt, log_fallback, new_request_id
from app.services.llm.sanitize import sanitize_for_provider
from app.services.llm.types import LLMMessage, LLMResponse

ADAPTERS: dict[str, ProviderAdapter] = {
    "gemini": GeminiAdapter(),
    "openai": OpenAIAdapter(),
    "groq": GroqAdapter(),
}

_PROVIDER_KEY_CHECK = {
    "groq": lambda: bool(settings.GROQ_API_KEY),
    "gemini": lambda: bool(settings.GEMINI_API_KEY),
    "openai": lambda: bool(settings.OPENAI_API_KEY),
}


def configured_providers(chain: list[str] | None = None) -> list[str]:
    """Providers from `chain` (or settings.LLM_PROVIDER_PRIORITY) that actually have a key set."""
    order = chain or settings.LLM_PROVIDER_PRIORITY
    return [p for p in order if p in ADAPTERS and _PROVIDER_KEY_CHECK.get(p, lambda: False)()]


async def call_llm_with_tools(
    system_prompt: str,
    messages: list[LLMMessage],
    tools: list[dict],
    chain: list[str] | None = None,
    max_tokens: int = 1536,
) -> LLMResponse:
    """
    Tries each configured provider in order (fresh from the top of the
    chain every call — not "sticky" to whichever succeeded last, since a
    previously-failing provider may have recovered). On failure, logs the
    fallback reason and tries the next. Messages are re-sanitized for each
    provider attempted, so switching providers mid-conversation correctly
    strips any Gemini-only metadata before it reaches OpenAI/Groq, and
    correctly omits (never fabricates) a thought_signature when switching
    back to Gemini after using another provider in between.
    """
    providers = configured_providers(chain)
    if not providers:
        raise UnknownProviderError(
            "No LLM provider configured — set at least one of GEMINI_API_KEY, "
            "OPENAI_API_KEY, GROQ_API_KEY in your environment."
        )

    request_id = new_request_id()
    last_error: LLMError | None = None

    for attempt, provider in enumerate(providers, start=1):
        adapter = ADAPTERS[provider]
        sanitized = sanitize_for_provider(messages, provider)

        with log_attempt(request_id, provider, adapter.__class__.__name__, attempt) as outcome:
            try:
                response = await adapter.send(system_prompt, sanitized, tools, max_tokens=max_tokens)
                outcome["tool_call"] = bool(response.message.tool_calls)
                return response
            except LLMError as e:
                outcome["error_type"] = e.__class__.__name__
                next_provider = providers[attempt] if attempt < len(providers) else None
                log_fallback(request_id, provider, next_provider, reason=str(e))
                last_error = e
                continue

    raise last_error or UnknownProviderError("All configured LLM providers failed")
