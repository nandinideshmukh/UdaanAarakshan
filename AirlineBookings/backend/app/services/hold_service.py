"""
Hold Booking / Price Freeze — locks a specific flight's price for a window
(default 24h, configurable) before the traveler commits to full payment.
Backed by Redis with a TTL matching the hold window, so it naturally
expires without any cleanup job.
"""

from datetime import datetime, timedelta, timezone

from app.models.schemas import FlightOption, HoldResponse
from app.services.cache_client import cache_get, cache_set
from app.services.pnr_service import generate_pnr

DEFAULT_HOLD_HOURS = 24


async def create_hold(request_id: str, flight: FlightOption, hold_hours: int = DEFAULT_HOLD_HOURS) -> HoldResponse:
    pnr = generate_pnr()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hold_hours)

    hold = HoldResponse(
        pnr=pnr,
        request_id=request_id,
        flight=flight,
        held_price=flight.price,
        expires_at=expires_at,
    )

    ttl_seconds = hold_hours * 3600
    await cache_set(f"hold:{request_id}", hold.model_dump(mode="json"), ttl_seconds=ttl_seconds)
    await cache_set(f"pnr:{pnr}", {"request_id": request_id}, ttl_seconds=ttl_seconds)
    return hold


async def get_hold(request_id: str) -> HoldResponse | None:
    data = await cache_get(f"hold:{request_id}")
    if not data:
        return None
    hold = HoldResponse(**data)
    if hold.expires_at < datetime.now(timezone.utc):
        return None  # expired — Redis TTL will clean it up shortly
    return hold


async def resolve_pnr(pnr: str) -> str | None:
    data = await cache_get(f"pnr:{pnr.upper()}")
    return data["request_id"] if data else None
