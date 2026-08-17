"""
Upstash QStash replaces RabbitMQ/SQS. It works by:
  1. You publish a job with a target URL (a route on THIS same deployment).
  2. QStash calls that URL back (with retries + DLQ) whenever it's ready.
This is what decouples the Email Agent from the Email Worker in the diagram.
"""

import httpx

from app.config import settings

QSTASH_PUBLISH_URL = "https://qstash.upstash.io/v2/publish"


async def enqueue_email_job(payload: dict) -> dict:
    target = f"{settings.PUBLIC_BASE_URL}/api/webhooks/email-worker"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{QSTASH_PUBLISH_URL}/{target}",
            headers={
                "Authorization": f"Bearer {settings.QSTASH_TOKEN}",
                "Content-Type": "application/json",
                "Upstash-Retries": "3",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
