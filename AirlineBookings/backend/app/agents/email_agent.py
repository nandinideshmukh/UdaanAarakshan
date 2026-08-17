from app.models.schemas import BookingConfirmation
from app.services.queue_client import enqueue_email_job


async def queue_confirmation_email(confirmation: BookingConfirmation) -> None:
    seat_line = (
        f"<p>Seat: {confirmation.seat.row}{confirmation.seat.letter}</p>"
        if confirmation.seat
        else ""
    )
    payload = {
        "to": confirmation.passenger.contact_email,
        "subject": f"Booking Confirmed — PNR {confirmation.pnr}",
        "html": (
            f"<h2>You're booked!</h2>"
            f"<p>PNR: <strong>{confirmation.pnr}</strong></p>"
            f"<p>Flight {confirmation.flight.flight_number} on "
            f"{confirmation.flight.airline}</p>"
            f"<p>Passenger: {confirmation.passenger.full_name}</p>"
            f"{seat_line}"
            f"<p>Total fare: Rs {confirmation.fare_total:,.2f}</p>"
            f"<p>Booking ID: {confirmation.booking_id}</p>"
        ),
    }
    # This returns immediately — QStash calls /api/webhooks/email-worker later
    await enqueue_email_job(payload)


# ---------------------------------------------------------------------------
# Group booking confirmation email (additive)
# ---------------------------------------------------------------------------

from app.models.schemas import GroupBookingConfirmation  # noqa: E402


async def queue_group_confirmation_email(confirmation: GroupBookingConfirmation) -> None:
    passenger_rows = "".join(
        f"<li>{p.passenger.full_name}"
        + (f" — Seat {p.seat.row}{p.seat.letter}" if p.seat else "")
        + f" — Rs {p.fare_total:,.2f}</li>"
        for p in confirmation.passengers
    )
    payload = {
        "to": confirmation.passengers[0].passenger.contact_email,
        "subject": f"Booking Confirmed — PNR {confirmation.pnr}",
        "html": (
            f"<h2>You're booked!</h2>"
            f"<p>PNR: <strong>{confirmation.pnr}</strong></p>"
            f"<p>Flight {confirmation.flight.flight_number} on {confirmation.flight.airline}</p>"
            f"<ul>{passenger_rows}</ul>"
            f"<p>Total fare: Rs {confirmation.total_fare:,.2f}</p>"
            f"<p>Booking ID: {confirmation.booking_id}</p>"
        ),
    }
    await enqueue_email_job(payload)
