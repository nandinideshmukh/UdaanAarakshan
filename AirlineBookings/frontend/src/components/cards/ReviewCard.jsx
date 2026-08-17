const LABELS = {
  base_fare: "Base fare",
  seat_fee: "Seat",
  baggage_fee: "Baggage",
  service_fee: "Services",
  tax: "Taxes",
};

export default function ReviewCard({ data }) {
  return (
    <div className="chat-card">
      <div className="chat-card__header">
        <span className="chat-card__title">Review before booking</span>
      </div>

      {data.passengers.map((p, i) => (
        <div key={i}>
          <div className="review-row review-row--name">
            <span>{p.passenger_name}</span>
            <span className="tag tag--accent">{p.fare_category}</span>
          </div>
          {Object.entries(LABELS).map(([key, label]) =>
            p[key] > 0 ? (
              <div className="review-row" key={key}>
                <span>{label}</span>
                <span>₹{p[key].toLocaleString()}</span>
              </div>
            ) : null
          )}
          <div className="review-row" style={{ fontWeight: 600, color: "var(--ink)" }}>
            <span>Subtotal</span>
            <span>₹{p.total.toLocaleString()}</span>
          </div>
        </div>
      ))}

      <div className="review-row review-row--total">
        <span>Total</span>
        <span>₹{data.grand_total.toLocaleString()}</span>
      </div>

      <p className="chat-card__hint">Reply "yes, book it" to confirm — nothing is charged until then.</p>
    </div>
  );
}
