import { useEffect, useState } from "react";

function formatRemaining(ms) {
  if (ms <= 0) return "Expired";
  const totalMinutes = Math.floor(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${minutes.toString().padStart(2, "0")}m remaining`;
}

export default function HoldCard({ data }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  const remaining = new Date(data.expires_at).getTime() - now;

  return (
    <div className="chat-card hold-card">
      <div className="chat-card__header">
        <span className="chat-card__title">Price locked</span>
      </div>
      <div className="hold-card__pnr">{data.pnr}</div>
      <div className="hold-card__row">
        <span>Fare frozen at</span>
        <strong>₹{data.held_price.toLocaleString()}</strong>
      </div>
      <div className="hold-card__row">
        <span>Hold expires</span>
        <strong>{formatRemaining(remaining)}</strong>
      </div>
    </div>
  );
}
