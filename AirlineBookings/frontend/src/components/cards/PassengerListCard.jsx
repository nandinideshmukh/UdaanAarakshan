export default function PassengerListCard({ data }) {
  const passengers = data?.passengers || [];
  if (passengers.length === 0) return null;

  return (
    <div className="chat-card">
      <div className="chat-card__header">
        <span className="chat-card__title">Passengers ({passengers.length})</span>
      </div>
      {passengers.map((p, i) => (
        <div className="passenger-row" key={i}>
          <div className="passenger-row__index">{i + 1}</div>
          <div>
            <div className="passenger-row__name">{p.passenger.full_name}</div>
            <div className="passenger-row__meta">
              {p.seat ? (
                <span className="tag">Seat {p.seat.row}{p.seat.letter}</span>
              ) : (
                <span className="tag tag--muted">No seat yet</span>
              )}
              {p.baggage?.extra_checked_bags > 0 && (
                <span className="tag tag--muted">+{p.baggage.extra_checked_bags} bag(s)</span>
              )}
              {p.services?.meal && p.services.meal !== "none" && (
                <span className="tag tag--muted">{p.services.meal}</span>
              )}
              {p.services?.priority_boarding && <span className="tag tag--muted">Priority</span>}
              {p.services?.wifi && <span className="tag tag--muted">Wi-Fi</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
