"""
Plain prompt-in / text-out multi-provider call — no tool calling. Used for
things like fare estimation where we just want the model's best-guess
text/JSON output, not an agentic tool loop. Tries the same configured
provider chain as the tool-calling gateway (orchestrator.py), with
fallback to the next provider on failure.

Kept separate from orchestrator.py because tool-calling and plain text
completion are genuinely different request shapes per provider — no
reason to force a fake single-tool loop just to get a text answer.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.services.llm.errors import UnknownProviderError
from app.services.llm.orchestrator import configured_providers


async def _call_groq_text(prompt: str) -> str:
    from app.services.llm_client import call_groq

    return await call_groq(prompt)


async def _call_openai_text(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini_text(prompt: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:"
        f"generateContent?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)


_TEXT_CALLERS = {"groq": _call_groq_text, "openai": _call_openai_text, "gemini": _call_gemini_text}


async def call_llm_text(prompt: str, chain: list[str] | None = None) -> str:
    """Tries each configured provider in order, falling back to the next on any failure."""
    providers = configured_providers(chain)
    if not providers:
        raise UnknownProviderError("No LLM provider configured for a plain text call")

    last_error: Exception | None = None
    for provider in providers:
        try:
            return await _TEXT_CALLERS[provider](prompt)
        except Exception as e:  # noqa: BLE001 — deliberately broad: try the next provider
            print(f"[llm-text] provider '{provider}' failed ({e}), trying next configured provider")
            last_error = e
            continue

    raise last_error or UnknownProviderError("All configured LLM providers failed for a plain text call")
