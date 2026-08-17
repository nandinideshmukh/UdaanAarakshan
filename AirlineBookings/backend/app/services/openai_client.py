"""
OpenAI provider adapter. Wire format is identical to Groq (both are
OpenAI Chat Completions API) — this just points at a different base URL
with a different key, reusing the same tool-schema conversion and
response normalization helpers from llm_client.py.
"""

import json

import httpx

from app.config import settings
from app.services.llm_client import REQUEST_TIMEOUT, _normalize_groq_response, _to_groq_tools

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


async def call_openai_with_tools(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    model: str = DEFAULT_OPENAI_MODEL,
    max_tokens: int = 1536,
) -> dict:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "tools": _to_groq_tools(tools),  # identical schema shape to Groq
        "tool_choice": "auto",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(OPENAI_URL, headers=headers, json=payload)
        if response.status_code == 401:
            raise ValueError("OPENAI_API_KEY invalid or expired (401).")
        if response.status_code >= 400:
            print(f"OpenAI tool-use error {response.status_code}: {response.text}")
        response.raise_for_status()
        return _normalize_groq_response(response.json())


async def call_openai(prompt: str, model: str = DEFAULT_OPENAI_MODEL, temperature: float = 0.2) -> str:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(OPENAI_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
