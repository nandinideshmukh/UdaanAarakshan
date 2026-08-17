"""
Groq adapter. Two things specific to Groq live here:

1. Model: llama-3.3-70b-versatile is decommissioned by Groq on
   August 16, 2026 — requests to it stop being served after that date.
   Groq's recommended replacement for tool-calling/agentic workloads is
   openai/gpt-oss-120b, used below.

2. Groq occasionally fails to emit a clean native tool call (400 with
   code "tool_use_failed", raw attempted generation in
   `failed_generation`) — documented, expected behavior, not a bug here.
   Per Groq's own guidance we retry once (transient generation noise
   usually clears), then fall back to regex-extracting the tool call from
   the raw text so the request still succeeds instead of erroring out.
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.services.llm.adapters._openai_compatible import (
    from_wire_response,
    to_wire_messages,
    to_wire_tools,
)
from app.services.llm.adapters.base import ProviderAdapter
from app.services.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    LLMTimeoutError,
    ModelUnavailableError,
    ProviderUnavailableError,
    RateLimitError,
    ToolCallError,
)
from app.services.llm.types import LLMMessage, LLMResponse, LLMToolCall

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
REQUEST_TIMEOUT = 30.0


def _parse_failed_generation(text: str) -> list[LLMToolCall]:
    """Extracts `<function=name{...}></function>`-style markers from a malformed generation."""
    calls: list[LLMToolCall] = []
    pattern = re.compile(
        r"<function=(?P<name>[^\{\(\[]+?)\s*(?P<body>\{.*?\}|\(.*?\)|\[.*?\])\s*</function>",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        name = match.group("name").strip().rstrip("=").strip()
        body = match.group("body")
        args_text = body[1:-1] if body.startswith("(") and body.endswith(")") else body
        try:
            parsed_args = json.loads(args_text)
        except json.JSONDecodeError:
            parsed_args = {"raw": args_text}
        if isinstance(parsed_args, list) and len(parsed_args) == 1 and isinstance(parsed_args[0], dict):
            parsed_args = parsed_args[0]
        calls.append(LLMToolCall(id=f"tool_use_{name}", name=name, arguments=parsed_args))
    return calls


class GroqAdapter(ProviderAdapter):
    name = "groq"

    async def send(
        self, system_prompt: str, messages: list[LLMMessage], tools: list[dict], max_tokens: int = 1536
    ) -> LLMResponse:
        return await self._send(system_prompt, messages, tools, max_tokens, retry=True)

    async def _send(
        self, system_prompt: str, messages: list[LLMMessage], tools: list[dict], max_tokens: int, retry: bool
    ) -> LLMResponse:
        if not settings.GROQ_API_KEY:
            raise AuthenticationError("GROQ_API_KEY not configured", provider="groq")

        headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": DEFAULT_MODEL,
            "max_tokens": max_tokens,
            "temperature": 0.1,  # more reliable native tool_calls, fewer malformed generations
            "messages": to_wire_messages(system_prompt, messages, own_namespace="groq"),
            "tools": to_wire_tools(tools),
            "tool_choice": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(GROQ_URL, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(str(e), provider="groq") from e
        except httpx.HTTPError as e:
            raise ProviderUnavailableError(str(e), provider="groq") from e

        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
            except Exception:
                err = {}

            if err.get("code") == "tool_use_failed":
                if retry:
                    print("[llm] groq tool_use_failed — retrying once (Groq-recommended recovery)")
                    return await self._send(system_prompt, messages, tools, max_tokens, retry=False)
                if err.get("failed_generation"):
                    calls = _parse_failed_generation(err["failed_generation"])
                    if calls:
                        print("[llm] groq retry also failed — recovered tool call via fallback parser")
                        return LLMResponse(
                            message=LLMMessage(role="assistant", content=None, tool_calls=calls),
                            provider="groq",
                            model=DEFAULT_MODEL,
                            raw=err,
                        )
                raise ToolCallError(err.get("message", "Groq tool call failed"), provider="groq", raw=err)

            msg = err.get("message") or resp.text[:300]
            if resp.status_code in (401, 403):
                raise AuthenticationError(msg, provider="groq", raw=err)
            if resp.status_code == 429:
                raise RateLimitError(msg, provider="groq", raw=err)
            if resp.status_code == 404 and "decommission" in msg.lower():
                raise ModelUnavailableError(msg, provider="groq", raw=err)
            if resp.status_code >= 500:
                raise ProviderUnavailableError(msg, provider="groq", raw=err)
            raise InvalidRequestError(msg, provider="groq", raw=err)

        return from_wire_response(resp.json(), provider="groq", model=DEFAULT_MODEL)
