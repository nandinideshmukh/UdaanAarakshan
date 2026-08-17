"""
Real flight SCHEDULE data via AviationStack (https://aviationstack.com) —
airline, flight number, real routes, real scheduled times. AviationStack
is a flight-tracking API, not a fares/booking API, so it has NO pricing
data at all.

Pricing here is LLM-estimated: the real schedule (airline, route,
duration, cabin) is handed to whichever LLM provider is configured, and
it estimates a plausible fare grounded in that real context — the same
reasoning approach used elsewhere in this app, rather than a fixed
formula. If the LLM call fails for any reason, a deterministic formula
(same inputs -> same price every time) is used as a safety net so a
transient LLM/provider outage doesn't break this whole tier.

Falls back gracefully (raises AviationStackUnavailable) if
AVIATIONSTACK_API_KEY isn't set, the account's plan doesn't include the
Future Flight Schedules endpoint (paid-tier-only on AviationStack), or any
call fails — search_agent.py catches this and moves to the next tier
(fully LLM-generated schedule + price).

Free signup: https://aviationstack.com (note: Future Flight Schedules,
the endpoint this module needs, requires a paid plan — the free tier only
covers real-time/current flight status, not future-dated search).
"""

import hashlib
import json
import re
from datetime import datetime

import httpx

from app.config import settings
from app.services.llm.text import call_llm_text
from app.services.llm_client import extract_json

BASE = "https://api.aviationstack.com/v1"
REQUEST_TIMEOUT = 20.0

# Fallback-only pricing (used if the LLM fare-estimation call fails).
# Rough per-minute-of-flight-time price bands by cabin, derived from real
# scheduled duration. Not real pricing — just consistent and
# duration-sensitive rather than random.
_CABIN_MULTIPLIER = {"economy": 1.0, "premium_economy": 1.6, "business": 3.2, "first": 5.0}
_BASE_FARE = 2200.0
_PER_MINUTE = 9.5


class AviationStackUnavailable(Exception):
    """Raised whenever AviationStack can't be used — caller should fall back."""


async def _resolve_iata(keyword: str) -> str:
    keyword = keyword.strip()
    if len(keyword) == 3 and keyword.isalpha():
        return keyword.upper()

    # Use the LLM to dynamically resolve city names to IATA codes instead of hardcoding
    # or relying on AviationStack's paid-only autocomplete endpoint.
    prompt = (
        f"What is the primary 3-letter IATA airport code for '{keyword}'? "
        "Return ONLY a raw JSON object with exactly one key 'iata_code' and the 3-letter string value. "
        "No markdown fences, no text before or after."
    )
    try:
        raw = await call_llm_text(prompt)
        data = extract_json(raw)
        if "iata_code" in data and isinstance(data["iata_code"], str) and len(data["iata_code"]) == 3:
            return data["iata_code"].upper()
    except Exception as e:
        print(f"LLM IATA resolution failed for '{keyword}': {e}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(
            f"{BASE}/airports",
            params={"access_key": settings.AVIATIONSTACK_API_KEY, "search": keyword},
        )
        if resp.status_code >= 400:
            raise AviationStackUnavailable(f"Airport lookup failed for '{keyword}': {resp.status_code}")
        body = resp.json()
        if "error" in body:
            raise AviationStackUnavailable(f"Airport lookup error for '{keyword}': {body['error']}")
        data = body.get("data") or []
        if not data:
            raise AviationStackUnavailable(f"No airport found for '{keyword}'")
        code = data[0].get("iata_code")
        if not code:
            raise AviationStackUnavailable(f"Airport lookup for '{keyword}' returned no IATA code")
        return code


def _parse_minutes(dep_iso: str, arr_iso: str) -> int:
    try:
        dep = datetime.fromisoformat(dep_iso.replace("Z", "+00:00"))
        arr = datetime.fromisoformat(arr_iso.replace("Z", "+00:00"))
        minutes = int((arr - dep).total_seconds() / 60)
        return minutes if minutes > 0 else 90  # guard against bad/overnight parsing edge cases
    except (ValueError, AttributeError):
        return 90


def _formula_price(flight_number: str, duration_minutes: int, cabin_class: str) -> float:
    """Deterministic fallback (same inputs -> same price every time) — used only if LLM pricing fails."""
    seed = int(hashlib.md5(flight_number.encode()).hexdigest(), 16) % 1000
    variance = 0.85 + (seed / 1000) * 0.5  # spreads prices +-~15-35% for route/flight variety
    multiplier = _CABIN_MULTIPLIER.get(cabin_class, 1.0)
    price = (_BASE_FARE + _PER_MINUTE * duration_minutes) * multiplier * variance
    return round(price, -1)  # round to nearest 10


async def _estimate_prices_via_llm(
    flights: list[dict], source: str, destination: str, cabin_class: str
) -> dict[str, float]:
    """
    Asks the configured LLM to estimate a realistic INR fare for each real
    flight, grounded in its actual airline/duration/route — one batched
    call for all flights, not one per flight. Returns {flight_number: price}.
    Raises on failure — caller falls back to _formula_price per flight.
    """
    flight_summaries = [
        {
            "flight_number": f["flight_number"],
            "airline": f["airline"],
            "duration_minutes": f["duration_minutes"],
            "departure_time": f["departure_time"],
        }
        for f in flights
    ]

    prompt = f"""These are REAL scheduled flights from {source} to {destination}, cabin class: {cabin_class}.
Estimate a realistic fare in INR for each, based on the airline's typical market
positioning (budget vs full-service carrier), flight duration, and typical fares
for this kind of route in India.

Flights:
{json.dumps(flight_summaries, indent=2)}

Return ONLY a raw JSON array — no markdown fences, no explanation, no text before or after.
Each object must have exactly: {{"flight_number": "...", "price": <number>}}"""

    raw = await call_llm_text(prompt)
    data = extract_json(raw)
    return {d["flight_number"]: float(d["price"]) for d in data if "flight_number" in d and "price" in d}


async def search_aviationstack_flights(
    source: str,
    destination: str,
    depart_date: str,
    cabin_class: str = "economy",
    max_results: int = 6,
) -> list[dict]:
    """Returns flight options in the same shape as the FlightOption schema, or raises AviationStackUnavailable."""
    if not settings.AVIATIONSTACK_API_KEY:
        raise AviationStackUnavailable("AVIATIONSTACK_API_KEY not configured")

    origin_code = await _resolve_iata(source)
    dest_code = await _resolve_iata(destination)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(
            f"{BASE}/flightsFuture",
            params={
                "access_key": settings.AVIATIONSTACK_API_KEY,
                "iataCode": origin_code,
                "type": "departure",
                "date": depart_date,
            },
        )
        if resp.status_code >= 400:
            raise AviationStackUnavailable(f"Schedule search failed: {resp.status_code} {resp.text[:300]}")

        body = resp.json()
        if "error" in body:
            err = body["error"]
            raise AviationStackUnavailable(f"AviationStack error: {err.get('message', err)}")

        flights = body.get("data") or []

        options = []
        for f in flights:
            arrival = f.get("arrival") or {}
            if (arrival.get("iataCode") or "").upper() != dest_code:
                continue  # this endpoint filters by origin only — filter destination client-side

            departure = f.get("departure") or {}
            airline = f.get("airline") or {}
            flight_info = f.get("flight") or {}

            dep_time = departure.get("scheduledTime") or departure.get("time") or ""
            arr_time = arrival.get("scheduledTime") or arrival.get("time") or ""
            flight_number = f"{airline.get('iataCode', '')}{flight_info.get('number', '')}"
            duration_minutes = _parse_minutes(dep_time, arr_time) if dep_time and arr_time else 120

            options.append(
                {
                    "airline": airline.get("name") or airline.get("iataCode", "Unknown"),
                    "flight_number": flight_number or f"UNK{len(options)}",
                    "duration_minutes": duration_minutes,
                    "stops": 0,  # this endpoint only returns direct scheduled segments
                    "departure_time": re.sub(r"^.*T", "", dep_time)[:5] if dep_time else "00:00",
                    "arrival_time": re.sub(r"^.*T", "", arr_time)[:5] if arr_time else "00:00",
                }
            )
            if len(options) >= max_results:
                break

        if not options:
            raise AviationStackUnavailable("No matching scheduled flights found for this route/date")

        # Price the real schedule via LLM, grounded in real airline/duration/route.
        # If the LLM fails, raise an error to ensure price consistency rather than
        # falling back to unrealistic formula-based prices.
        try:
            price_map = await _estimate_prices_via_llm(options, source, destination, cabin_class)
        except Exception as e:
            raise AviationStackUnavailable(f"LLM fare estimation failed, aborting rather than using fake prices: {e}")

        for opt in options:
            opt["price"] = price_map.get(opt["flight_number"])
            opt["currency"] = "INR"
            if opt["price"] is None:
                raise AviationStackUnavailable(f"LLM failed to price flight {opt['flight_number']}")

        return options
