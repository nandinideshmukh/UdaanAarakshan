import { CheckIcon } from "../icons";

export default function BookingConfirmationCard({ data }) {
  return (
    <div className="chat-card confirmation-card">
      <div className="chat-card__header">
        <span className="chat-card__icon" style={{ background: "var(--success-soft)", color: "var(--success)" }}>
          <CheckIcon />
        </span>
        <span className="chat-card__title">Booking confirmed</span>
      </div>

      <div className="confirmation-card__flight">{data.flight.airline} {data.flight.flight_number}</div>
      <div className="confirmation-card__pnr">PNR {data.pnr}</div>

      {data.passengers.map((p, i) => (
        <div className="passenger-row" key={i}>
          <div className="passenger-row__index">{i + 1}</div>
          <div>
            <div className="passenger-row__name">{p.passenger.full_name}</div>
            <div className="passenger-row__meta">
              {p.seat && <span className="tag tag--muted">Seat {p.seat.row}{p.seat.letter}</span>}
              <span className="tag tag--muted">₹{p.fare_total.toLocaleString()}</span>
            </div>
          </div>
        </div>
      ))}

      <div className="review-row review-row--total">
        <span>Total paid</span>
        <span>₹{data.total_fare.toLocaleString()}</span>
      </div>
      <p className="chat-card__hint">Booking ID: {data.booking_id} — a confirmation email is on its way.</p>
    </div>
  );
}
