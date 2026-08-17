"""
Generates an interactive seat map for a flight.

Deliberately NOT an LLM call — seat availability is exactly the kind of
fact an LLM should never invent. This is seeded off the flight number so
the same flight always produces the same layout (stable across refreshes),
with a mix of available/occupied/premium/extra-legroom seats and per-seat
pricing, matching a typical narrow-body 3-3 layout.
"""

import hashlib

from app.models.schemas import Seat, SeatMapResponse

ROWS = 24
SEAT_LETTERS = ["A", "B", "C", "D", "E", "F"]
AISLE_AFTER = "C"  # visual aisle between C and D

EXTRA_LEGROOM_ROWS = {1, 12, 13}  # bulkhead + exit row
PREMIUM_ROWS = set(range(1, 5))  # first few rows = premium cabin


def _seed(flight_number: str, row: int, letter: str) -> int:
    key = f"{flight_number}-{row}-{letter}".encode()
    return int(hashlib.md5(key).hexdigest(), 16)


def _category(row: int) -> str:
    if row in PREMIUM_ROWS:
        return "premium"
    if row in EXTRA_LEGROOM_ROWS:
        return "extra_legroom"
    return "standard"


def _price(category: str) -> float:
    return {"premium": 2200.0, "extra_legroom": 1200.0, "standard": 0.0}[category]


def generate_seatmap(flight_number: str) -> SeatMapResponse:
    seats: list[Seat] = []
    for row in range(1, ROWS + 1):
        for letter in SEAT_LETTERS:
            category = _category(row)
            # ~30% deterministically occupied, varies per seat via hash
            occupied = (_seed(flight_number, row, letter) % 100) < 30
            seats.append(
                Seat(
                    row=row,
                    letter=letter,
                    category=category,
                    status="occupied" if occupied else "available",
                    price=_price(category),
                    aisle_side=(letter == AISLE_AFTER or letter == "D"),
                )
            )
    return SeatMapResponse(flight_number=flight_number, rows=ROWS, seats=seats)


# ---------------------------------------------------------------------------
# Real cross-booking race-condition handling
# ---------------------------------------------------------------------------
#
# generate_seatmap() above is a pure, deterministic mock layout — same
# input always gives the same output, which is great for testing but means
# two different travelers booking the same flight would each see the same
# "available" seats, even after one of them actually takes it. The
# functions below layer real persisted state on top so a seat taken by one
# booking is genuinely unavailable to the next — the actual real-world
# race condition airlines have to handle at scale.

SEATS_TAKEN_TTL_SECONDS = 60 * 60 * 24 * 2  # 2 days — comfortably longer than a booking session


async def get_taken_seats(flight_number: str) -> set[tuple[int, str]]:
    from app.services.cache_client import cache_get

    data = await cache_get(f"seats_taken:{flight_number}")
    if not data:
        return set()
    return {(s["row"], s["letter"]) for s in data.get("seats", [])}


async def mark_seats_taken(flight_number: str, seats: list[tuple[int, str]]) -> None:
    from app.services.cache_client import cache_set

    if not seats:
        return
    existing = await get_taken_seats(flight_number)
    existing.update(seats)
    await cache_set(
        f"seats_taken:{flight_number}",
        {"seats": [{"row": r, "letter": l} for r, l in existing]},
        ttl_seconds=SEATS_TAKEN_TTL_SECONDS,
    )


async def release_seats(flight_number: str, seats: list[tuple[int, str]]) -> None:
    """Releases seats back to available — used when a booking is cancelled."""
    from app.services.cache_client import cache_set

    if not seats:
        return
    existing = await get_taken_seats(flight_number)
    existing.difference_update(seats)
    await cache_set(
        f"seats_taken:{flight_number}",
        {"seats": [{"row": r, "letter": l} for r, l in existing]},
        ttl_seconds=SEATS_TAKEN_TTL_SECONDS,
    )


async def generate_seatmap_live(flight_number: str) -> SeatMapResponse:
    """
    Same as generate_seatmap(), but with seats actually taken by other
    confirmed bookings overlaid as occupied. Use this everywhere seat
    availability needs to reflect real concurrent bookings, not just the
    mock base layout — i.e. anywhere a traveler is about to pick or
    confirm a seat.
    """
    seatmap = generate_seatmap(flight_number)
    taken = await get_taken_seats(flight_number)
    if not taken:
        return seatmap
    for seat in seatmap.seats:
        if (seat.row, seat.letter) in taken:
            seat.status = "occupied"
    return seatmap
