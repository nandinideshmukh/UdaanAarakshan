"""
Integration test for the gateway's fallback chain (orchestrator.py) using
mocked HTTP responses — verifies it actually tries providers in order and
falls back correctly, end to end through call_llm_with_tools().
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


class FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data
        self.text = str(json_data)

    def json(self):
        return self._json


def run():
    from app.config import settings
    from app.services.llm.orchestrator import call_llm_with_tools
    from app.services.llm.types import LLMMessage

    settings.GROQ_API_KEY = "fake-groq-key"
    settings.OPENAI_API_KEY = "fake-openai-key"
    settings.GEMINI_API_KEY = ""  # unconfigured — must be skipped entirely
    settings.LLM_PROVIDER_PRIORITY = ["gemini", "openai", "groq"]

    calls = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, headers=None, json=None, **kwargs):
            calls.append(url)
            if "openai.com" in url:
                return FakeResponse(500, {"error": {"message": "openai down"}})
            if "groq.com" in url:
                return FakeResponse(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "function": {"name": "search_flights", "arguments": '{"source":"BOM"}'},
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                )
            raise AssertionError(f"unexpected URL: {url}")

    httpx.AsyncClient = FakeClient

    async def main():
        response = await call_llm_with_tools(
            system_prompt="test",
            messages=[LLMMessage(role="user", content="find a flight")],
            tools=[{"name": "search_flights", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        )
        assert response.provider == "groq", f"expected groq to serve after openai failed, got {response.provider}"
        assert response.message.tool_calls[0].name == "search_flights"
        assert not any("gemini" in c or "generativelanguage" in c for c in calls), "gemini never called — no key configured"
        assert any("openai.com" in c for c in calls), "openai should have been tried first (it's configured)"
        assert any("groq.com" in c for c in calls), "groq should have been tried as fallback"
        print("PASS: gateway correctly skips unconfigured gemini, tries openai, falls back to groq on failure")

    asyncio.run(main())


if __name__ == "__main__":
    run()
