"""
Real flight data via Amadeus Self-Service API (test.api.amadeus.com by
default — free sandbox tier, real airline schedules/pricing but not
live bookable inventory). Falls back gracefully if AMADEUS_CLIENT_ID/
AMADEUS_CLIENT_SECRET aren't set, or if any call fails — the caller
(search_agent.py) catches AmadeusUnavailable and uses LLM-generated
flight data instead so the app keeps working without an Amadeus signup.

Get free credentials at https://developers.amadeus.com/register
"""

import time

import httpx

from app.config import settings

REQUEST_TIMEOUT = 20.0

_token_cache: dict = {"access_token": None, "expires_at": 0}


class AmadeusUnavailable(Exception):
    """Raised whenever Amadeus can't be used — caller should fall back."""


def _base_url() -> str:
    return "https://api.amadeus.com" if settings.AMADEUS_HOSTNAME == "production" else "https://test.api.amadeus.com"


async def _get_access_token() -> str:
    if not settings.AMADEUS_CLIENT_ID or not settings.AMADEUS_CLIENT_SECRET:
        raise AmadeusUnavailable("AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET not configured")

    if _token_cache["access_token"] and _token_cache["expires_at"] > time.time() + 30:
        return _token_cache["access_token"]

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(
            f"{_base_url()}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.AMADEUS_CLIENT_ID,
                "client_secret": settings.AMADEUS_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code >= 400:
            raise AmadeusUnavailable(f"Amadeus auth failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + data.get("expires_in", 1800)
        return _token_cache["access_token"]


async def _resolve_iata(keyword: str) -> str:
    """Best-effort city/airport name -> IATA code. Already-3-letter input is used as-is."""
    keyword = keyword.strip()
    if len(keyword) == 3 and keyword.isalpha():
        return keyword.upper()

    token = await _get_access_token()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(
            f"{_base_url()}/v1/reference-data/locations",
            params={"keyword": keyword, "subType": "CITY,AIRPORT", "page[limit]": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code >= 400:
            raise AmadeusUnavailable(f"Location lookup failed for '{keyword}': {resp.status_code}")
        data = resp.json().get("data") or []
        if not data:
            raise AmadeusUnavailable(f"No airport/city found for '{keyword}'")
        return data[0]["iataCode"]


_CABIN_MAP = {
    "economy": "ECONOMY",
    "premium_economy": "PREMIUM_ECONOMY",
    "business": "BUSINESS",
    "first": "FIRST",
}


def _duration_to_minutes(iso_duration: str) -> int:
    """Parses ISO-8601 duration like 'PT2H10M' into total minutes."""
    hours, minutes = 0, 0
    num = ""
    in_time = False
    for ch in iso_duration:
        if ch == "T":
            in_time = True
        elif ch.isdigit():
            num += ch
        elif ch == "H" and in_time:
            hours = int(num or 0)
            num = ""
        elif ch == "M" and in_time:
            minutes = int(num or 0)
            num = ""
    return hours * 60 + minutes


async def search_amadeus_flights(
    source: str,
    destination: str,
    depart_date: str,
    cabin_class: str = "economy",
    adults: int = 1,
    max_results: int = 6,
) -> list[dict]:
    """Returns flight options in the same shape as FlightOption schema, or raises AmadeusUnavailable."""
    token = await _get_access_token()
    origin_code = await _resolve_iata(source)
    dest_code = await _resolve_iata(destination)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(
            f"{_base_url()}/v2/shopping/flight-offers",
            params={
                "originLocationCode": origin_code,
                "destinationLocationCode": dest_code,
                "departureDate": depart_date,
                "adults": adults,
                "travelClass": _CABIN_MAP.get(cabin_class, "ECONOMY"),
                "currencyCode": "INR",
                "max": max_results,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code >= 400:
            raise AmadeusUnavailable(f"Flight search failed: {resp.status_code} {resp.text[:300]}")

        body = resp.json()
        offers = body.get("data") or []
        carriers = body.get("dictionaries", {}).get("carriers", {})

        options = []
        for offer in offers:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            first_seg, last_seg = segments[0], segments[-1]
            carrier_code = first_seg["carrierCode"]

            options.append(
                {
                    "airline": carriers.get(carrier_code, carrier_code),
                    "flight_number": f"{carrier_code}{first_seg['number']}",
                    "price": round(float(offer["price"]["total"]), 2),
                    "duration_minutes": _duration_to_minutes(itinerary["duration"]),
                    "stops": len(segments) - 1,
                    "departure_time": first_seg["departure"]["at"][11:16],
                    "arrival_time": last_seg["arrival"]["at"][11:16],
                }
            )
        return options
