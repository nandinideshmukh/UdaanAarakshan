"""
Gemini provider adapter. Gemini's REST API shape differs meaningfully from
OpenAI/Groq's (contents/parts instead of messages, functionCall/
functionResponse instead of tool_calls/tool role, systemInstruction
instead of a system message) — this module is the translator so the rest
of the codebase never has to know the difference.

Incoming `messages` follow the same OpenAI-ish shape the orchestrators
build everywhere else (role: user/assistant/tool, assistant carries
tool_calls, tool carries tool_call_id) — converted to Gemini's contents
array here. The response is normalized back to the same Anthropic-style
`{"content": [...]}` blocks every other provider adapter returns, so
orchestrator loops don't need to know which provider actually served
a given turn.
"""

import json

import httpx

from app.config import settings
from app.services.llm_client import REQUEST_TIMEOUT

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


def _to_gemini_tools(tools: list[dict]) -> list[dict]:
    declarations = []
    for tool in tools:
        parameters = tool.get("input_schema") or tool.get("parameters") or {"type": "object", "properties": {}}
        declarations.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": parameters,
            }
        )
    return [{"functionDeclarations": declarations}]


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    import json
    contents: list[dict] = []
    call_id_to_name: dict[str, str] = {}
    faked_calls: set[str] = set()

    for msg in messages:
        role = msg["role"]

        if role == "user":
            contents.append({"role": "user", "parts": [{"text": msg.get("content") or ""}]})

        elif role == "assistant":
            parts = []
            if msg.get("content"):
                parts.append({"text": msg["content"]})
            for tc in msg.get("tool_calls") or []:
                name = tc["function"]["name"]
                call_id_to_name[tc["id"]] = name
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}
                function_call_part = {"functionCall": {"name": name, "args": args}}
                thought_signature = tc.get("thought_signature") or tc.get("thoughtSignature")

                if thought_signature:
                    function_call_part = {"functionCall": {"name": name, "args": args}}
                    function_call_part["thoughtSignature"] = thought_signature
                    parts.append(function_call_part)
                else:
                    faked_calls.add(tc["id"])
                    parts.append({"text": f"Action: called {name} with arguments {json.dumps(args)}"})

            if parts:
                contents.append({"role": "model", "parts": parts})

        elif role == "tool":
            tc_id = msg.get("tool_call_id", "")
            name = call_id_to_name.get(tc_id, "unknown_function")
            try:
                response_payload = json.loads(msg["content"])
            except (json.JSONDecodeError, TypeError):
                response_payload = {"result": msg.get("content")}
            
            if tc_id in faked_calls:
                contents.append(
                    {"role": "user", "parts": [{"text": f"Result from {name}: {json.dumps(response_payload)}"}]}
                )
            else:
                contents.append(
                    {"role": "user", "parts": [{"functionResponse": {"name": name, "response": response_payload}}]}
                )

    return contents


def _normalize_gemini_response(response: dict) -> dict:
    blocks: list[dict] = []
    candidates = response.get("candidates") or []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "text" in part and part["text"].strip():
                blocks.append({"type": "text", "text": part["text"].strip()})
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_block = {
                    "type": "tool_use",
                    "id": f"gemini_call_{fc['name']}_{len(blocks)}",
                    "name": fc["name"],
                    "input": fc.get("args", {}),
                }
                thought_signature = part.get("thoughtSignature") or part.get("thought_signature")
                if thought_signature:
                    tool_block["thought_signature"] = thought_signature
                blocks.append(tool_block)
    return {"content": blocks}


async def call_gemini_with_tools(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    model: str = DEFAULT_GEMINI_MODEL,
    max_tokens: int = 1536,
) -> dict:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")

    url = f"{GEMINI_BASE}/{model}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": _to_gemini_contents(messages),
        "tools": _to_gemini_tools(tools),
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        if response.status_code == 400 and "API key" in response.text:
            raise ValueError("GEMINI_API_KEY invalid.")
        if response.status_code >= 400:
            print(f"Gemini tool-use error {response.status_code}: {response.text}")
        response.raise_for_status()
        return _normalize_gemini_response(response.json())
