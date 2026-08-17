import { CheckIcon, XCircleIcon } from "../icons";

export default function SingleBookingConfirmationCard({ data }) {
  const cancelled = data.status === "cancelled";
  return (
    <div className={`chat-card ${cancelled ? "cancel-card" : "confirmation-card"}`}>
      <div className="chat-card__header">
        <span
          className="chat-card__icon"
          style={
            cancelled
              ? { background: "var(--danger-soft)", color: "var(--danger)" }
              : { background: "var(--success-soft)", color: "var(--success)" }
          }
        >
          {cancelled ? <XCircleIcon /> : <CheckIcon />}
        </span>
        <span className="chat-card__title">{cancelled ? "Booking cancelled" : "Booking found"}</span>
      </div>

      <div className="confirmation-card__flight">{data.flight.airline} {data.flight.flight_number}</div>
      <div className="confirmation-card__pnr">PNR {data.pnr} · {data.passenger.full_name}</div>

      <div className="review-row">
        <span>Seat</span>
        <span>{data.seat ? `${data.seat.row}${data.seat.letter}` : "—"}</span>
      </div>
      <div className="review-row review-row--total">
        <span>Fare</span>
        <span>₹{data.fare_total.toLocaleString()}</span>
      </div>
    </div>
  );
}
