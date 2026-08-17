function formatMoney(value, currency = "INR") {
  const normalizedCurrency = (currency || "INR").toUpperCase();
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: normalizedCurrency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function FlightBoard({ flights, reasoning }) {
  return (
    <div>
      <div className="board">
        <div className="board__header">
          <span>Airline / Flight</span>
          <span>Depart → Arrive</span>
          <span>Stops</span>
          <span>Duration</span>
          <span>Price</span>
        </div>
        {flights.map((f, i) => (
          <div className="board__row" key={`${f.flight_number}-${i}`}>
            <span>
              {f.airline} {f.flight_number}
            </span>
            <span>
              {f.departure_time} → {f.arrival_time}
            </span>
            <span>{f.stops === 0 ? "Direct" : f.stops}</span>
            <span>{Math.floor(f.duration_minutes / 60)}h {f.duration_minutes % 60}m</span>
            <span className="board__cell--price">{formatMoney(f.price, f.currency)}</span>
          </div>
        ))}
      </div>

      {reasoning && (
        <div className="reasoning">
          <span className="reasoning__label">Comparator Agent's reasoning</span>
          {reasoning}
        </div>
      )}
    </div>
  );
}
