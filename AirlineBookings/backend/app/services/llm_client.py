"""
Plain prompt-in / text-out Groq calls — used by search_agent.py and
comparator_agent.py for JSON-generation prompts that don't need tool
calling. Real tool-calling (agentic_orchestrator, chat_orchestrator) goes
through app/services/llm/ instead (the multi-provider gateway).
"""

import json
import re
from typing import Any

import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# llama-3.3-70b-versatile is decommissioned by Groq on August 16, 2026.
# Groq's recommended replacement for tool-calling/agentic workloads is
# openai/gpt-oss-120b — used here too for consistency.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

REQUEST_TIMEOUT = 30.0


def extract_json(raw: str) -> Any:
    """
    Parse JSON returned by an LLM.

    Handles:
    - Plain JSON
    - ```json ... ``` fences
    - Extra text surrounding JSON
    """
    if isinstance(raw, (list, dict)):
        return raw

    text = raw.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    if text.startswith("{") or text.startswith("["):
        return json.loads(text)

    object_match = re.search(r"\{.*\}", text, re.DOTALL)
    array_match = re.search(r"\[.*\]", text, re.DOTALL)

    candidates = []
    if object_match:
        candidates.append(object_match.group(0))
    if array_match:
        candidates.append(array_match.group(0))

    if candidates:
        candidate = min(candidates, key=lambda value: text.find(value))
        return json.loads(candidate)

    raise ValueError("No valid JSON found in LLM response")


async def call_groq(
    prompt: str,
    model: str = DEFAULT_GROQ_MODEL,
    temperature: float = 0.2,
) -> str:
    """Plain prompt-in / text-out call — no tools, used for JSON-generation prompts."""
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment variables")

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(GROQ_URL, headers=headers, json=payload)

        if response.status_code == 401:
            raise ValueError("GROQ API key invalid or expired (received 401). Check GROQ_API_KEY.")
        if response.status_code >= 400:
            print(f"Groq error {response.status_code}: {response.text}")
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]
