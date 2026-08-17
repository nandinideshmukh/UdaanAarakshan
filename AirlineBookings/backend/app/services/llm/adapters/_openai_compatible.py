"""
OpenAI and Groq both speak the same Chat Completions wire format — this
module holds the shared request/response conversion so OpenAIAdapter and
GroqAdapter are both thin wrappers (different base URL, key, default
model) rather than duplicated logic.

Per the architecture rules: this format NEVER carries Gemini's
thought_signature — messages are sanitized (sanitize.py) before reaching
here, and even if a tool_call's provider_metadata still had a "gemini" key
somehow, this module simply never reads it, only "openai"/"groq" keys.
"""

from __future__ import annotations

import json

import httpx

from app.services.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    LLMTimeoutError,
    ModelUnavailableError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.llm.types import LLMMessage, LLMResponse, LLMToolCall, LLMToolResult

REQUEST_TIMEOUT = 30.0


def to_wire_tools(tools: list[dict]) -> list[dict]:
    """Anthropic-style {"name","description","input_schema"} -> OpenAI function-calling schema."""
    wire_tools = []
    for tool in tools:
        parameters = tool.get("input_schema") or tool.get("parameters") or {}
        wire_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": parameters,
                },
            }
        )
    return wire_tools


def to_wire_messages(system_prompt: str, messages: list[LLMMessage], own_namespace: str) -> list[dict]:
    wire: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        if msg.role in ("user",):
            wire.append({"role": "user", "content": msg.content or ""})

        elif msg.role == "assistant":
            entry: dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in msg.tool_calls
                ]
            wire.append(entry)

        elif msg.role == "tool" and msg.tool_result:
            wire.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_result.tool_call_id,
                    "content": json.dumps(msg.tool_result.content),
                }
            )
    return wire


def from_wire_response(data: dict, provider: str, model: str) -> LLMResponse:
    choices = data.get("choices") or []
    if not choices:
        return LLMResponse(message=LLMMessage(role="assistant", content=None), provider=provider, model=model, raw=data)

    wire_msg = choices[0].get("message", {})
    content = wire_msg.get("content")

    tool_calls = []
    for tc in wire_msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}
        tool_calls.append(LLMToolCall(id=tc.get("id", f"call_{fn.get('name')}"), name=fn.get("name"), arguments=args))

    message = LLMMessage(role="assistant", content=content, tool_calls=tool_calls)
    return LLMResponse(message=message, provider=provider, model=model, raw=data)


def raise_for_status(resp: httpx.Response, provider: str) -> None:
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
        err = body.get("error", {})
    except Exception:
        err = {}
    msg = err.get("message") or resp.text[:300]
    code = err.get("code", "")

    if resp.status_code == 401 or resp.status_code == 403:
        raise AuthenticationError(msg, provider=provider, raw=err)
    if resp.status_code == 429:
        raise RateLimitError(msg, provider=provider, raw=err)
    if resp.status_code == 404 and ("model" in msg.lower() or "decommission" in msg.lower()):
        raise ModelUnavailableError(msg, provider=provider, raw=err)
    if resp.status_code >= 500:
        raise ProviderUnavailableError(msg, provider=provider, raw=err)
    if resp.status_code == 400:
        raise InvalidRequestError(msg, provider=provider, raw=err)
    raise LLMError(msg, provider=provider, raw=err)


async def send_openai_compatible(
    url: str,
    api_key: str,
    provider: str,
    system_prompt: str,
    messages: list[LLMMessage],
    tools: list[dict],
    model: str,
    max_tokens: int,
) -> LLMResponse:
    if not api_key:
        raise AuthenticationError(f"{provider} API key not configured", provider=provider)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "messages": to_wire_messages(system_prompt, messages, own_namespace=provider),
        "tools": to_wire_tools(tools),
        "tool_choice": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(str(e), provider=provider) from e
    except httpx.HTTPError as e:
        raise ProviderUnavailableError(str(e), provider=provider) from e

    raise_for_status(resp, provider)
    return from_wire_response(resp.json(), provider=provider, model=model)
