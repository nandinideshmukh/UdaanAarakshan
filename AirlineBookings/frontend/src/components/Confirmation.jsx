import { useState } from "react";
import { api } from "../api";

export default function Confirmation({ confirmation, requestId, onStartOver }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  async function submitRating(value) {
    setRating(value);
    try {
      await api.submitFeedback(requestId, value, comment || null);
      setSent(true);
    } catch {
      /* non-critical — booking already succeeded */
    }
  }

  return (
    <div className="panel">
      <div className="confirmation-stamp">
        <div className="tag">Booking confirmed</div>
        <h1 className="page-title" style={{ marginTop: 14 }}>
          {confirmation.flight.airline} {confirmation.flight.flight_number}
        </h1>
        <div className="confirmation-stamp__id">Booking ID: {confirmation.booking_id}</div>
        <p className="page-subtitle" style={{ marginTop: 10 }}>
          A confirmation email is on its way to {confirmation.passenger_email}.
        </p>
      </div>

      {!sent ? (
        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 20 }}>
          <label>How did the agent do?</label>
          <div className="btn-row" style={{ marginBottom: 14 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                className="btn btn-secondary"
                style={{ padding: "8px 14px" }}
                onClick={() => submitRating(n)}
              >
                {n}
              </button>
            ))}
          </div>
          <textarea
            placeholder="Anything the agent should do differently next time? (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
      ) : (
        <div className="approval-banner">Thanks — feedback recorded.</div>
      )}

      <button className="btn btn-ghost" onClick={onStartOver} style={{ marginTop: 18 }}>
        Plan another trip →
      </button>
    </div>
  );
}
