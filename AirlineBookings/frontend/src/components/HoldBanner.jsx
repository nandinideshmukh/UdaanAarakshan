import { useEffect, useState } from "react";

function formatRemaining(ms) {
  if (ms <= 0) return "Expired";
  const totalMinutes = Math.floor(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${minutes.toString().padStart(2, "0")}m remaining`;
}

export default function HoldBanner({ hold }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  if (!hold) return null;

  const remaining = new Date(hold.expires_at).getTime() - now;
  const expired = remaining <= 0;

  return (
    <div className={"hold-banner" + (expired ? " hold-banner--expired" : "")}>
      <div>
        <span className="hold-banner__label">PNR</span>
        <span className="hold-banner__pnr">{hold.pnr}</span>
      </div>
      <div className="hold-banner__price">
        Fare frozen at <strong>₹{hold.held_price.toLocaleString()}</strong>
      </div>
      <div className="hold-banner__timer">{formatRemaining(remaining)}</div>
    </div>
  );
}
