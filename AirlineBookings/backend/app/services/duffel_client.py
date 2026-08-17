"""
Real flight data via Duffel (https://duffel.com). Replaces Amadeus, whose
self-service developer portal was fully decommissioned on July 17, 2026 —
only Amadeus Enterprise (sales-contract-only) remains, which isn't viable
for self-serve/hobby use. Duffel is still self-serve: sign up and get a
free test key (`duffel_test_...`) in about a minute, no OAuth dance needed
(Amadeus required a client-credentials token exchange; Duffel just uses a
static Bearer API key).

Falls back gracefully if DUFFEL_API_KEY isn't set, or if any call fails —
the caller (search_agent.py) catches DuffelUnavailable and uses
LLM-generated flight data instead so the app keeps working either way.

Get a free test key at https://duffel.com (Sign up -> Dashboard -> API keys)

Field-shape note: parsed defensively against Duffel's documented offer
schema — if Duffel changes field names, this raises DuffelUnavailable and
falls back rather than crashing the request. total_currency comes back as
whatever your Duffel account is configured for (commonly GBP/USD/EUR by
default, not necessarily INR) — the rest of this app labels prices with a
₹ symbol, so if your account's currency isn't INR you'll want to either
request an INR-denominated Duffel account or adjust the display currency.
"""

import re

import httpx

from app.config import settings

DUFFEL_BASE = "https://api.duffel.com"
REQUEST_TIMEOUT = 25.0


class DuffelUnavailable(Exception):
    """Raised whenever Duffel can't be used — caller should fall back."""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.DUFFEL_API_KEY}",
        "Duffel-Version": settings.DUFFEL_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _resolve_iata(keyword: str) -> str:
    """Best-effort city/airport name -> IATA code. Already-3-letter input is used as-is."""
    keyword = keyword.strip()
    if len(keyword) == 3 and keyword.isalpha():
        return keyword.upper()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(
            f"{DUFFEL_BASE}/places/suggestions",
            params={"query": keyword},
            headers=_headers(),
        )
        if resp.status_code >= 400:
            raise DuffelUnavailable(f"Place lookup failed for '{keyword}': {resp.status_code} {resp.text[:200]}")
        data = resp.json().get("data") or []
        if not data:
            raise DuffelUnavailable(f"No airport/city found for '{keyword}'")
        code = data[0].get("iata_code")
        if not code:
            raise DuffelUnavailable(f"Place lookup for '{keyword}' returned no IATA code")
        return code


_CABIN_MAP = {
    "economy": "economy",
    "premium_economy": "premium_economy",
    "business": "business",
    "first": "first",
}


def _duration_to_minutes(iso_duration: str) -> int:
    """Parses ISO-8601 duration like 'PT7H45M' into total minutes."""
    if not iso_duration:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso_duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


async def search_duffel_flights(
    source: str,
    destination: str,
    depart_date: str,
    cabin_class: str = "economy",
    adults: int = 1,
    max_results: int = 6,
) -> list[dict]:
    """Returns flight options in the same shape as the FlightOption schema, or raises DuffelUnavailable."""
    if not settings.DUFFEL_API_KEY:
        raise DuffelUnavailable("DUFFEL_API_KEY not configured")

    origin_code = await _resolve_iata(source)
    dest_code = await _resolve_iata(destination)

    payload = {
        "data": {
            "slices": [{"origin": origin_code, "destination": dest_code, "departure_date": depart_date}],
            "passengers": [{"type": "adult"} for _ in range(adults)],
            "cabin_class": _CABIN_MAP.get(cabin_class, "economy"),
        }
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(
            f"{DUFFEL_BASE}/air/offer_requests",
            params={"return_offers": "true"},
            headers=_headers(),
            json=payload,
        )
        if resp.status_code >= 400:
            raise DuffelUnavailable(f"Flight search failed: {resp.status_code} {resp.text[:300]}")

        body = resp.json()
        offers = (body.get("data") or {}).get("offers") or []

        options = []
        for offer in offers[:max_results]:
            try:
                slice0 = offer["slices"][0]
                segments = slice0["segments"]
                first_seg, last_seg = segments[0], segments[-1]
                carrier = first_seg.get("marketing_carrier") or first_seg.get("operating_carrier") or {}
                airline_name = (offer.get("owner") or {}).get("name") or carrier.get("name") or carrier.get("iata_code", "Unknown")
                flight_no = f"{carrier.get('iata_code', '')}{first_seg.get('marketing_carrier_flight_number', '')}"

                currency = (offer.get("total_currency") or "INR").upper()
                options.append(
                    {
                        "airline": airline_name,
                        "flight_number": flight_no or offer.get("id", "N/A")[:8],
                        "price": round(float(offer["total_amount"]), 2),
                        "currency": currency,
                        "duration_minutes": _duration_to_minutes(slice0.get("duration", "")),
                        "stops": len(segments) - 1,
                        "departure_time": (first_seg.get("departing_at") or "")[11:16],
                        "arrival_time": (last_seg.get("arriving_at") or "")[11:16],
                    }
                )
            except (KeyError, IndexError, TypeError, ValueError):
                continue  # skip any offer that doesn't match the expected shape

        if not options and offers:
            # Got offers back but couldn't parse any — Duffel likely changed
            # a field name. Fall back rather than silently return nothing.
            raise DuffelUnavailable("Received offers but none matched the expected field shape")

        return options
