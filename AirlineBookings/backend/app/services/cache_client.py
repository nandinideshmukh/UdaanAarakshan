"""
Upstash Redis over REST — regular redis-py needs a persistent TCP
connection, which doesn't survive between serverless invocations.
Upstash's REST API is stateless HTTP, which fits Vercel functions.
"""

import json

import httpx

from app.config import settings


def _normalize_redis_url(url: str) -> str:
    if not url:
        raise RuntimeError(
            "UPSTASH_REDIS_REST_URL is not configured. "
            "Set it to a full URL like https://<upstash-id>.upstash.io"
        )
    normalized = url.strip().rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise RuntimeError(
            "UPSTASH_REDIS_REST_URL must include a protocol: http:// or https://"
        )
    return normalized


def _decode_cached_result(result: str | dict | None) -> dict | None:
    if result is None:
        return None
    if isinstance(result, str):
        result = json.loads(result)
    if isinstance(result, dict) and "value" in result and "EX" in result:
        return _decode_cached_result(result["value"])
    return result


BASE = _normalize_redis_url(settings.UPSTASH_REDIS_REST_URL)
HEADERS = {"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"}


async def cache_set(key: str, value: dict, ttl_seconds: int = 3600) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{BASE}/set/{key}",
            headers=HEADERS,
            json={"value": json.dumps(value), "EX": ttl_seconds},
        )


async def cache_get(key: str) -> dict | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE}/get/{key}", headers=HEADERS)
        result = resp.json().get("result")
        return _decode_cached_result(result)


async def rate_limit_incr(key: str, window_seconds: int = 60) -> int:
    """Simple fixed-window rate limit counter."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{BASE}/incr/{key}", headers=HEADERS)
        count = resp.json()["result"]
        if count == 1:
            await client.post(f"{BASE}/expire/{key}/{window_seconds}", headers=HEADERS)
        return count
