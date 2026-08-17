import uuid
from datetime import date

from app.agents.seatmap_agent import generate_seatmap
from app.models.schemas import BookingConfirmation, BookingRequest, PassengerDetails, Seat
from app.services.json_store import save_json

EXTRA_BAG_PRICE = 800.0
EXTRA_CARRY_ON_PRICE = 400.0
PRIORITY_BOARDING_PRICE = 300.0
WIFI_PRICE = 500.0

# Real airlines price infants/children differently — infants (<2) usually
# fly as a lap infant at a small percentage of adult fare with no seat;
# children get a discount; adults pay full fare. This is age-derived from
# date_of_birth rather than trusting a separate "type" field, since that's
# what a real check is based on and it can't be misreported independently
# of the DOB already being collected.
INFANT_FARE_RATIO = 0.10
CHILD_FARE_RATIO = 0.75
TAX_RATE = 0.18  # airline fare tax/surcharge, modeled as a flat percentage of base fare


def passenger_age_years(dob: date, as_of: date | None = None) -> int:
    as_of = as_of or date.today()
    years = as_of.year - dob.year
    if (as_of.month, as_of.day) < (dob.month, dob.day):
        years -= 1
    return years


def fare_category(dob: date) -> str:
    age = passenger_age_years(dob)
    if age < 2:
        return "infant"
    if age < 12:
        return "child"
    return "adult"


def _fare_ratio(category: str) -> float:
    return {"infant": INFANT_FARE_RATIO, "child": CHILD_FARE_RATIO, "adult": 1.0}[category]


def _resolve_seat(flight_number: str, seat_selection) -> Seat | None:
    if not seat_selection:
        return None
    seatmap = generate_seatmap(flight_number)
    for seat in seatmap.seats:
        if seat.row == seat_selection.row and seat.letter == seat_selection.letter:
            return seat
    return None


def compute_passenger_breakdown(
    base_flight_price: float,
    passenger: PassengerDetails,
    seat: Seat | None,
    baggage,
    services,
) -> dict:
    """
    Full itemized fare breakdown for one passenger — the same calculation
    used both for the pre-payment review (review_booking tool) and the
    final booking (book_group), so what a traveler is shown always matches
    what they're actually charged.
    """
    category = fare_category(passenger.date_of_birth)
    ratio = _fare_ratio(category)

    base_fare = round(base_flight_price * ratio, 2)
    seat_fee = seat.price if (seat and category != "infant") else 0.0  # infants don't occupy a seat
    baggage_fee = baggage.extra_checked_bags * EXTRA_BAG_PRICE + (EXTRA_CARRY_ON_PRICE if baggage.extra_carry_on else 0.0)
    service_fee = (PRIORITY_BOARDING_PRICE if services.priority_boarding else 0.0) + (
        WIFI_PRICE if services.wifi else 0.0
    )

    subtotal = base_fare + seat_fee + baggage_fee + service_fee
    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax, 2)

    return {
        "fare_category": category,
        "base_fare": base_fare,
        "seat_fee": seat_fee,
        "baggage_fee": round(baggage_fee, 2),
        "service_fee": round(service_fee, 2),
        "tax": tax,
        "total": total,
    }


async def book_flight(booking: BookingRequest) -> BookingConfirmation:
    """
    Mock booking only — no real airline/payment provider is called.
    Kept for the original single-passenger /trip/book flow.
    """
    booking_id = str(uuid.uuid4())
    seat = _resolve_seat(booking.selected_flight.flight_number, booking.seat)
    breakdown = compute_passenger_breakdown(
        booking.selected_flight.price, booking.passenger, seat, booking.baggage, booking.services
    )

    confirmation = BookingConfirmation(
        booking_id=booking_id,
        pnr=booking.pnr,
        status="confirmed",  # mock: always succeeds
        flight=booking.selected_flight,
        passenger=booking.passenger,
        seat=seat,
        baggage=booking.baggage,
        services=booking.services,
        fare_total=breakdown["total"],
    )

    await save_json(f"bookings:{booking_id}", confirmation.model_dump(mode="json"))
    await save_json(f"bookings_by_pnr:{booking.pnr}", {"booking_id": booking_id, "group": False})
    return confirmation


# ---------------------------------------------------------------------------
# Multi-passenger group booking (additive — book_flight above is untouched
# and still used by the original single-passenger /trip/book flow)
# ---------------------------------------------------------------------------

from app.models.schemas import (  # noqa: E402
    GroupBookingConfirmation,
    GroupBookingRequest,
    PassengerBookingResult,
)


async def book_group(request: GroupBookingRequest) -> GroupBookingConfirmation:
    """
    Mock booking only, same as book_flight — books every passenger in the
    request under one PNR / booking_id (a real group reservation), with
    age-based fare categories and taxes applied per passenger.
    """
    booking_id = str(uuid.uuid4())
    results: list[PassengerBookingResult] = []
    total_fare = 0.0

    for pb in request.passengers:
        seat = _resolve_seat(request.selected_flight.flight_number, pb.seat)
        breakdown = compute_passenger_breakdown(
            request.selected_flight.price, pb.passenger, seat, pb.baggage, pb.services
        )
        total_fare += breakdown["total"]

        results.append(
            PassengerBookingResult(
                passenger=pb.passenger,
                seat=seat,
                baggage=pb.baggage,
                services=pb.services,
                fare_total=breakdown["total"],
            )
        )

    confirmation = GroupBookingConfirmation(
        booking_id=booking_id,
        pnr=request.pnr,
        status="confirmed",
        flight=request.selected_flight,
        passengers=results,
        total_fare=round(total_fare, 2),
    )

    await save_json(f"bookings:{booking_id}", confirmation.model_dump(mode="json"))
    await save_json(f"bookings_by_pnr:{request.pnr}", {"booking_id": booking_id, "group": True})
    return confirmation
