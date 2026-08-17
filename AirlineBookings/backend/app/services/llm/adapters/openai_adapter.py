from __future__ import annotations

from app.config import settings
from app.services.llm.adapters._openai_compatible import send_openai_compatible
from app.services.llm.adapters.base import ProviderAdapter
from app.services.llm.types import LLMMessage, LLMResponse

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    async def send(
        self, system_prompt: str, messages: list[LLMMessage], tools: list[dict], max_tokens: int = 1536
    ) -> LLMResponse:
        return await send_openai_compatible(
            url=OPENAI_URL,
            api_key=settings.OPENAI_API_KEY,
            provider="openai",
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            model=DEFAULT_MODEL,
            max_tokens=max_tokens,
        )
