"""
All persisted data (bookings, feedback, search/ranked results) is stored as
JSON in Upstash Redis — no database, no blob storage, no separate service.

This mirrors the diagram's "File Storage (JSON based)" box directly: each
record is just a JSON value under a key like 'bookings:{booking_id}'.
Records are set with a long TTL (default 30 days) instead of forever,
since Redis is being used as a lightweight store rather than a database —
raise JSON_STORE_TTL_SECONDS or drop the TTL if you want it permanent.
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

JSON_STORE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


async def save_json(key: str, data: dict, ttl_seconds: int = JSON_STORE_TTL_SECONDS) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{BASE}/set/{key}",
            headers=HEADERS,
            json={"value": json.dumps(data), "EX": ttl_seconds},
        )


async def read_json(key: str) -> dict | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE}/get/{key}", headers=HEADERS)
        result = resp.json().get("result")
        return _decode_cached_result(result)


async def list_keys(pattern: str) -> list[str]:
    """e.g. list_keys('bookings:*') to list all booking records."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{BASE}/keys/{pattern}", headers=HEADERS)
        return resp.json().get("result", [])
