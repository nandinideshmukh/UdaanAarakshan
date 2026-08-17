import uuid

from app.models.schemas import FlightOption, SearchResult, TripRequest
from app.services.aviationstack_client import AviationStackUnavailable, search_aviationstack_flights
from app.services.duffel_client import DuffelUnavailable, search_duffel_flights
from app.services.llm_client import call_groq, extract_json


async def _search_via_llm(trip: TripRequest) -> list[dict]:
    """Last-resort fallback used when neither Duffel nor AviationStack are
    configured/available — fully synthetic data, kept only so the app
    remains usable without any real flight-data signup at all."""
    prompt = f"""Generate synthetic flight options matching these parameters:
From: {trip.source} to {trip.destination}
Date: {trip.depart_date}
Cabin: {trip.cabin_class}
Max Stops: {trip.max_stops}
Budget: {trip.budget}

Return ONLY a raw JSON array. Do not include markdown code fences, explanations, or any text before or after the JSON.
Each object must contain EXACTLY these keys: airline, flight_number, price, currency, duration_minutes, stops, departure_time, arrival_time.

Example output:
[
  {{"airline": "IndiGo", "flight_number": "6E123", "price": 4500, "currency": "INR", "duration_minutes": 125, "stops": 0, "departure_time": "06:15", "arrival_time": "08:20"}}
]"""
    raw = await call_groq(prompt)
    return extract_json(raw)


async def search_flights(trip: TripRequest) -> SearchResult:
    """
    Three-tier fallback, each stage strictly less "real" than the last:

    1. Duffel — real bookable offers with real prices (best, if configured).
    2. AviationStack — real airlines/flight numbers/schedules, but NO real
       pricing (it's a flight-tracking API, not a fares API) — prices here
       are a synthetic-but-consistent estimate derived from real duration.
    3. LLM-generated — fully synthetic schedule AND price, last resort so
       the app still works with zero real-data signups at all.
    """
    options_data = None

    try:
        options_data = await search_duffel_flights(
            source=trip.source,
            destination=trip.destination,
            depart_date=str(trip.depart_date),
            cabin_class=str(trip.cabin_class),
        )
        if not options_data:
            raise DuffelUnavailable("Duffel returned zero results for this route/date")
    except DuffelUnavailable as e:
        print(f"Duffel unavailable ({e}), trying AviationStack next")

    if options_data is None:
        try:
            options_data = await search_aviationstack_flights(
                source=trip.source,
                destination=trip.destination,
                depart_date=str(trip.depart_date),
                cabin_class=str(trip.cabin_class),
            )
        except AviationStackUnavailable as e:
            print(f"AviationStack unavailable ({e}), falling back to LLM-generated flights")

    if options_data is None:
        options_data = await _search_via_llm(trip)

    # Client-side filtering: Duffel's own filters cover most of this, but
    # AviationStack and the LLM fallback don't self-filter, so apply
    # constraints uniformly regardless of which tier served the data.
    if trip.max_stops is not None:
        options_data = [o for o in options_data if o.get("stops", 0) <= trip.max_stops] or options_data
    if trip.budget is not None:
        within_budget = [o for o in options_data if o.get("price", 0) <= trip.budget]
        if within_budget:
            options_data = within_budget

    options = [FlightOption(**o) for o in options_data]
    return SearchResult(request_id=str(uuid.uuid4()), options=options)
