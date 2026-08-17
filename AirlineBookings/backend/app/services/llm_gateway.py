"""
LLM Gateway — single entrypoint the orchestrators call instead of talking
to a specific provider. Picks whichever provider is configured (checked in
settings.LLM_PROVIDER_PRIORITY order, default "groq,gemini,openai") and
automatically falls back to the next configured provider if the first one
errors out — so a transient outage or rate limit on one provider doesn't
take the whole booking flow down.

This is deliberately the ONLY place in the codebase that knows about
multiple providers — every agent just calls call_llm_with_tools() and
gets back the same normalized {"content": [...]} shape no matter which
provider actually served the request.
"""

from app.config import settings
from app.services.llm_client import call_groq_with_tools

_PROVIDER_KEY_CHECK = {
    "groq": lambda: bool(settings.GROQ_API_KEY),
    "gemini": lambda: bool(settings.GEMINI_API_KEY),
    "openai": lambda: bool(settings.OPENAI_API_KEY),
}


def configured_providers() -> list[str]:
    """Providers in priority order that actually have an API key set."""
    return [p for p in settings.LLM_PROVIDER_PRIORITY if _PROVIDER_KEY_CHECK.get(p, lambda: False)()]


async def _call_provider(provider: str, system_prompt: str, messages: list[dict], tools: list[dict]) -> dict:
    if provider == "groq":
        return await call_groq_with_tools(system_prompt, messages, tools)
    if provider == "gemini":
        from app.services.gemini_client import call_gemini_with_tools

        return await call_gemini_with_tools(system_prompt, messages, tools)
    if provider == "openai":
        from app.services.openai_client import call_openai_with_tools

        return await call_openai_with_tools(system_prompt, messages, tools)
    raise ValueError(f"Unknown provider: {provider}")


async def call_llm_with_tools(system_prompt: str, messages: list[dict], tools: list[dict]) -> dict:
    providers = configured_providers()
    if not providers:
        raise ValueError(
            "No LLM provider configured — set at least one of GROQ_API_KEY, "
            "GEMINI_API_KEY, OPENAI_API_KEY in your environment."
        )

    last_error: Exception | None = None
    for provider in providers:
        try:
            return await _call_provider(provider, system_prompt, messages, tools)
        except Exception as e:  # noqa: BLE001 — deliberately broad: try the next provider
            print(f"LLM gateway: provider '{provider}' failed ({e}), trying next configured provider")
            last_error = e
            continue

    raise last_error or ValueError("All configured LLM providers failed")
