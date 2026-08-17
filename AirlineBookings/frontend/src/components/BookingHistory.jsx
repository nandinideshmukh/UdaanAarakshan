import { useEffect, useState } from "react";
import { api } from "../api";

function formatMoney(value, currency = "INR") {
  const normalizedCurrency = (currency || "INR").toUpperCase();
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: normalizedCurrency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function BookingHistory() {
  const [bookings, setBookings] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listBookings()
      .then(setBookings)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="panel">
      <h1 className="page-title">Booking history</h1>
      <p className="page-subtitle">Everything you've booked through the agent.</p>

      {error && <div className="error-banner">{error}</div>}

      {!bookings && !error && <p style={{ color: "#6b6558" }}>Loading…</p>}

      {bookings && bookings.length === 0 && (
        <p style={{ color: "#6b6558" }}>No bookings yet — plan a trip to get started.</p>
      )}

      {bookings &&
        bookings.map((b) => (
          <div className="booking-list-item" key={b.booking_id}>
            <span>
              {b.flight.airline} {b.flight.flight_number}
            </span>
            <span>{formatMoney(b.flight.price, b.flight.currency)}</span>
            <span className="tag">{b.status}</span>
          </div>
        ))}
    </div>
  );
}
