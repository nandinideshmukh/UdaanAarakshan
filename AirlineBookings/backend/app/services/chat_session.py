"""
Backs the chatbot flow. Two things are kept per session_id in Redis:

1. History — the last N (role, content) text turns, for conversational
   context (kept short so the prompt doesn't grow unbounded).
2. State — explicit structured memory of the booking-in-progress: last
   search results, selected flight, hold/PNR, and passengers collected so
   far. This is fed into the system prompt each turn as ground truth,
   rather than relying on the model to remember it from prose history —
   more reliable for things like "book the first one" or "add my wife too".

Session TTL is generous (2h) since a real booking flow (search, pick,
add passengers, seats, ancillaries, confirm) can take a while.
"""

from app.services.cache_client import cache_get, cache_set

SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_HISTORY_TURNS = 20

EMPTY_STATE = {
    "search_results": [],       # last flight options found, list of dicts
    "selected_flight": None,     # the flight dict the traveler picked
    "hold": None,                # {pnr, held_price, expires_at}
    "passenger_count": None,     # expected total passengers, set via set_passenger_count
    "passengers": [],            # list of PassengerBooking-shaped dicts
    "reviewed": False,           # True once review_booking has shown the full price breakdown
    "booked": False,
    "booking": None,             # GroupBookingConfirmation dict, once confirmed
    "cancelled": False,
}


async def get_state(session_id: str) -> dict:
    data = await cache_get(f"chatstate:{session_id}")
    # Merge over EMPTY_STATE so sessions started before a schema change
    # (e.g. new fields added) don't KeyError on missing keys.
    return {**EMPTY_STATE, **data} if data else dict(EMPTY_STATE)


async def save_state(session_id: str, state: dict) -> None:
    await cache_set(f"chatstate:{session_id}", state, ttl_seconds=SESSION_TTL_SECONDS)


async def get_history(session_id: str) -> list[dict]:
    data = await cache_get(f"chathistory:{session_id}")
    return data["messages"] if data else []


async def append_history(session_id: str, role: str, content: str) -> None:
    history = await get_history(session_id)
    history.append({"role": role, "content": content})
    history = history[-MAX_HISTORY_TURNS:]
    await cache_set(f"chathistory:{session_id}", {"messages": history}, ttl_seconds=SESSION_TTL_SECONDS)
