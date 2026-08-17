import { XCircleIcon } from "../icons";

export default function BookingCancelledCard({ data }) {
  return (
    <div className="chat-card cancel-card">
      <div className="chat-card__header">
        <span className="chat-card__icon">
          <XCircleIcon />
        </span>
        <span className="chat-card__title">Booking cancelled</span>
      </div>
      <p className="chat-card__hint" style={{ marginTop: 0 }}>
        PNR {data.pnr} has been cancelled and any held seats were released.
      </p>
    </div>
  );
}
