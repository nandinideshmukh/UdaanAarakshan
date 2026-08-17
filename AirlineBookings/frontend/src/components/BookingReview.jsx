export default function BookingReview({ hold, passenger, seat, ancillaries, onConfirm, loading, error }) {
  const extraBagsTotal = (ancillaries?.baggage?.extra_checked_bags || 0) * 800;
  const carryOnTotal = ancillaries?.baggage?.extra_carry_on ? 400 : 0;
  const priorityTotal = ancillaries?.services?.priority_boarding ? 300 : 0;
  const wifiTotal = ancillaries?.services?.wifi ? 500 : 0;
  const seatTotal = seat?.price || 0;
  const fareTotal = hold.held_price + seatTotal + extraBagsTotal + carryOnTotal + priorityTotal + wifiTotal;

  return (
    <div className="panel">
      <h1 className="page-title">Review your booking</h1>
      <p className="page-subtitle">Confirm everything looks right before booking.</p>

      {error && <div className="error-banner">{error}</div>}

      <div className="review-block">
        <div className="review-row">
          <span>PNR</span>
          <strong>{hold.pnr}</strong>
        </div>
        <div className="review-row">
          <span>Flight</span>
          <strong>{hold.flight.airline} {hold.flight.flight_number}</strong>
        </div>
        <div className="review-row">
          <span>Passenger</span>
          <strong>{passenger.full_name}</strong>
        </div>
        <div className="review-row">
          <span>Seat</span>
          <strong>{seat ? `${seat.row}${seat.letter}` : "Not selected"}</strong>
        </div>
        <div className="review-row">
          <span>Baggage</span>
          <strong>
            {ancillaries.baggage.extra_checked_bags} extra bag(s)
            {ancillaries.baggage.extra_carry_on ? ", extra carry-on" : ""}
          </strong>
        </div>
        <div className="review-row">
          <span>Services</span>
          <strong>
            {[
              ancillaries.services.meal !== "none" ? ancillaries.services.meal : null,
              ancillaries.services.priority_boarding ? "Priority boarding" : null,
              ancillaries.services.wifi ? "Wi-Fi" : null,
            ]
              .filter(Boolean)
              .join(", ") || "None"}
          </strong>
        </div>
        <div className="review-row review-row--total">
          <span>Total fare</span>
          <strong>₹{fareTotal.toLocaleString()}</strong>
        </div>
      </div>

      <button className="btn btn-primary" onClick={onConfirm} disabled={loading} style={{ marginTop: 18 }}>
        {loading ? "Booking…" : "Confirm booking"}
      </button>
    </div>
  );
}
