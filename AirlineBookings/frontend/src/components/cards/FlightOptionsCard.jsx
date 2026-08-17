function formatMoney(value, currency = "INR") {
  const normalizedCurrency = (currency || "INR").toUpperCase();
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: normalizedCurrency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function FlightOptionsCard({ data, onPick }) {
  const options = data?.options || [];

  if (options.length === 0) {
    return (
      <div className="chat-card">
        <p className="chat-card__empty">No flights found for that search.</p>
      </div>
    );
  }

  return (
    <div className="chat-card">
      <div className="chat-card__header">
        <span className="chat-card__title">{options.length} flight{options.length === 1 ? "" : "s"} found</span>
      </div>
      <div>
        {options.map((f, i) => (
          <button key={`${f.flight_number}-${i}`} className="flight-row" onClick={() => onPick(f)} type="button">
            <div className="flight-row__main">
              <span className="flight-row__airline">{f.airline} {f.flight_number}</span>
              <span className="flight-row__meta">
                {f.departure_time} → {f.arrival_time} · {f.stops === 0 ? "Direct" : `${f.stops} stop${f.stops > 1 ? "s" : ""}`} · {Math.floor(f.duration_minutes / 60)}h {f.duration_minutes % 60}m
              </span>
            </div>
            <span className="flight-row__price">{formatMoney(f.price, f.currency)}</span>
          </button>
        ))}
      </div>
      <p className="chat-card__hint">Tap a flight, or just tell me which one you want.</p>
    </div>
  );
}
