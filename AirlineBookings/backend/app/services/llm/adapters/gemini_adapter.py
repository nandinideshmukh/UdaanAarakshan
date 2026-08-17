"""
Gemini adapter. The one thing this file must never do: invent a
`thought_signature`. Gemini's "thinking" models attach an opaque signature
to some functionCall parts to preserve reasoning continuity across a
multi-turn tool-calling conversation — if you pass back anything other
than the EXACT byte-for-byte value Gemini gave you (or omit it entirely
when Gemini didn't give you one), Gemini rejects the request with:

    Invalid value at 'contents[N].parts[0].thought_signature' (TYPE_BYTES),
    Base64 decoding failed for "default_signature"

That specific error is what happens when code (elsewhere, historically)
fabricated a placeholder string. The rules enforced here:

  - A tool call's thought_signature is read from
    LLMToolCall.provider_metadata["gemini"]["thought_signature"] and
    copied through EXACTLY — never re-encoded, decoded, or replaced.
  - If that key is absent, the outgoing Part simply has no
    thought_signature field at all. Never a default/placeholder string.
  - Before sending, any signature that IS present is validated as
    plausible base64 — if it isn't, we raise InvalidRequestError instead
    of sending it (and the gateway will NOT blindly retry the same
    payload unchanged, since this error isn't marked retryable).
"""

from __future__ import annotations

import base64
import binascii

import httpx

from app.config import settings
from app.services.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    LLMTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.services.llm.adapters.base import ProviderAdapter
from app.services.llm.types import LLMMessage, LLMResponse, LLMToolCall

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.6-flash"
REQUEST_TIMEOUT = 30.0


def _is_plausible_base64(value: str) -> bool:
    """Validates a thought_signature is well-formed base64 before we send it —
    catches corruption early with a clear error instead of letting Gemini reject it."""
    if not isinstance(value, str) or not value:
        return False
    try:
        base64.b64decode(value, validate=True)
        return True
    except (binascii.Error, ValueError):
        return False


def _to_gemini_tools(tools: list[dict]) -> list[dict]:
    declarations = []
    for tool in tools:
        parameters = tool.get("input_schema") or tool.get("parameters") or {"type": "object", "properties": {}}
        declarations.append(
            {"name": tool["name"], "description": tool.get("description", ""), "parameters": parameters}
        )
    return [{"functionDeclarations": declarations}]


def _to_gemini_contents(messages: list[LLMMessage]) -> list[dict]:
    contents: list[dict] = []
    call_id_to_name: dict[str, str] = {}
    faked_calls: set[str] = set()

    for msg in messages:
        if msg.role == "user":
            contents.append({"role": "user", "parts": [{"text": msg.content or ""}]})

        elif msg.role == "assistant":
            parts = []
            if msg.content:
                parts.append({"text": msg.content})
            for tc in msg.tool_calls:
                call_id_to_name[tc.id] = tc.name
                part: dict = {"functionCall": {"name": tc.name, "args": tc.arguments}}

                signature = tc.provider_metadata.get("gemini", {}).get("thought_signature")

                if signature is not None:
                    if not _is_plausible_base64(signature):
                        raise InvalidRequestError(
                            f"Refusing to send malformed thought_signature for tool call '{tc.name}' "
                            "(not valid base64) — not retrying unchanged.",
                            provider="gemini",
                        )
                    # Copied through EXACTLY as received — never modified.
                    part["thoughtSignature"] = signature
                    parts.append(part)
                else:
                    import json
                    faked_calls.add(tc.id)
                    parts.append({"text": f"Action: called {tc.name} with arguments {json.dumps(tc.arguments)}"})
            if parts:
                contents.append({"role": "model", "parts": parts})

        elif msg.role == "tool" and msg.tool_result:
            name = call_id_to_name.get(msg.tool_result.tool_call_id, msg.tool_result.name)
            if msg.tool_result.tool_call_id in faked_calls:
                import json
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": f"Result from {name}: {json.dumps(msg.tool_result.content)}"}],
                    }
                )
            else:
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"functionResponse": {"name": name, "response": msg.tool_result.content}}],
                    }
                )

    return contents


def _from_gemini_response(data: dict, model: str) -> LLMResponse:
    text_parts: list[str] = []
    tool_calls: list[LLMToolCall] = []

    candidates = data.get("candidates") or []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for i, part in enumerate(parts):
            if "text" in part and part["text"].strip():
                text_parts.append(part["text"].strip())
            elif "functionCall" in part:
                fc = part["functionCall"]
                provider_metadata = {}
                # Rule: only store a signature if Gemini ACTUALLY returned
                # one on this part. Never default/fabricate.
                signature = part.get("thoughtSignature")
                if signature is not None:
                    provider_metadata["gemini"] = {"thought_signature": signature}
                tool_calls.append(
                    LLMToolCall(
                        id=f"gemini_call_{fc['name']}_{i}",
                        name=fc["name"],
                        arguments=fc.get("args", {}),
                        provider_metadata=provider_metadata,
                    )
                )

    message = LLMMessage(role="assistant", content=" ".join(text_parts) or None, tool_calls=tool_calls)
    return LLMResponse(message=message, provider="gemini", model=model, raw=data)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
        err = (body.get("error") or {}) if isinstance(body, dict) else {}
    except Exception:
        err = {}
    msg = err.get("message") or resp.text[:300]

    if resp.status_code in (401, 403):
        raise AuthenticationError(msg, provider="gemini", raw=err)
    if resp.status_code == 429:
        raise RateLimitError(msg, provider="gemini", raw=err)
    if resp.status_code == 400:
        # This is exactly the bucket the historical thought_signature bug
        # fell into — surface it as non-retryable so callers don't loop
        # on a malformed payload.
        raise InvalidRequestError(msg, provider="gemini", raw=err)
    if resp.status_code >= 500:
        raise ProviderUnavailableError(msg, provider="gemini", raw=err)
    raise LLMError(msg, provider="gemini", raw=err)


class GeminiAdapter(ProviderAdapter):
    name = "gemini"

    async def send(
        self, system_prompt: str, messages: list[LLMMessage], tools: list[dict], max_tokens: int = 1536
    ) -> LLMResponse:
        if not settings.GEMINI_API_KEY:
            raise AuthenticationError("GEMINI_API_KEY not configured", provider="gemini")

        model = DEFAULT_MODEL
        url = f"{GEMINI_BASE}/{model}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": _to_gemini_contents(messages),
            "tools": _to_gemini_tools(tools),
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(str(e), provider="gemini") from e
        except httpx.HTTPError as e:
            raise ProviderUnavailableError(str(e), provider="gemini") from e

        _raise_for_status(resp)
        return _from_gemini_response(resp.json(), model=model)
