import { useState } from "react";
import FlightBoard from "./FlightBoard";

function formatMoney(value, currency = "INR") {
  const normalizedCurrency = (currency || "INR").toUpperCase();
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: normalizedCurrency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function ReviewPanel({
  ranked,
  approved,
  onRefine,
  onApprove,
  onBook,
  refining,
  approving,
  booking,
  error,
}) {
  const [feedback, setFeedback] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [passengerName, setPassengerName] = useState("");
  const [passengerEmail, setPassengerEmail] = useState("");

  function handleRefine(e) {
    e.preventDefault();
    if (!feedback.trim()) return;
    onRefine(feedback.trim());
    setFeedback("");
  }

  function handleBook(e) {
    e.preventDefault();
    onBook({
      selected_flight: ranked.best_picks[selectedIndex],
      passenger_name: passengerName,
      passenger_email: passengerEmail,
    });
  }

  return (
    <div className="panel">
      <h1 className="page-title">Review the Comparator's picks</h1>
      <p className="page-subtitle">
        Nothing books until you approve. Send feedback to re-rank, or approve to continue.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <FlightBoard flights={ranked.best_picks} reasoning={ranked.reasoning} />

      {approved ? (
        <div className="approval-banner">
          <span>✓ Approved — choose a flight below to book</span>
        </div>
      ) : (
        <form onSubmit={handleRefine} style={{ marginTop: 22 }}>
          <div className="field">
            <label htmlFor="feedback">Not quite right? Tell the agent why</label>
            <textarea
              id="feedback"
              placeholder="e.g. I'd rather pay more for a direct flight, or prefer morning departures"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
          </div>
          <div className="btn-row">
            <button className="btn btn-secondary" type="submit" disabled={refining || !feedback.trim()}>
              {refining ? "Re-ranking…" : "Refine ranking"}
            </button>
            <button
              className="btn btn-primary"
              type="button"
              onClick={onApprove}
              disabled={approving}
            >
              {approving ? "Approving…" : "Approve these picks"}
            </button>
          </div>
        </form>
      )}

      {approved && (
        <form onSubmit={handleBook} style={{ marginTop: 22 }}>
          <div className="field">
            <label htmlFor="pick">Book which one?</label>
            <select
              id="pick"
              value={selectedIndex}
              onChange={(e) => setSelectedIndex(Number(e.target.value))}
            >
              {ranked.best_picks.map((f, i) => (
                <option key={f.flight_number} value={i}>
                  {f.airline} {f.flight_number} — {formatMoney(f.price, f.currency)}
                </option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="pname">Passenger name</label>
              <input
                id="pname"
                type="text"
                value={passengerName}
                onChange={(e) => setPassengerName(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="pemail">Passenger email</label>
              <input
                id="pemail"
                type="email"
                value={passengerEmail}
                onChange={(e) => setPassengerEmail(e.target.value)}
                required
              />
            </div>
          </div>
          <button className="btn btn-primary" type="submit" disabled={booking}>
            {booking ? "Booking…" : "Confirm booking"}
          </button>
        </form>
      )}
    </div>
  );
}
