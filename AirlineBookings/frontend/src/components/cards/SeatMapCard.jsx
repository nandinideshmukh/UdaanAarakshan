import { useMemo, useState } from "react";

const LETTERS = ["A", "B", "C", "D", "E", "F"];

export default function SeatMapCard({ data, passengerCount, onSelectSeat }) {
  const [passengerIndex, setPassengerIndex] = useState(1);

  const rows = useMemo(() => {
    const byRow = {};
    for (const seat of data.seats) {
      byRow[seat.row] = byRow[seat.row] || {};
      byRow[seat.row][seat.letter] = seat;
    }
    return Object.entries(byRow)
      .map(([row, seats]) => ({ row: Number(row), seats }))
      .sort((a, b) => a.row - b.row);
  }, [data]);

  return (
    <div className="chat-card">
      <div className="chat-card__header">
        <span className="chat-card__title">Seat map — {data.flight_number}</span>
      </div>

      {passengerCount > 1 && (
        <select
          value={passengerIndex}
          onChange={(e) => setPassengerIndex(Number(e.target.value))}
          style={{
            marginBottom: 12,
            padding: "8px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            fontSize: "0.82rem",
          }}
        >
          {Array.from({ length: passengerCount }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>Selecting for passenger {n}</option>
          ))}
        </select>
      )}

      <div className="seatmap-legend">
        <span><i className="seat-swatch seat-swatch--standard" /> Standard</span>
        <span><i className="seat-swatch seat-swatch--extra_legroom" /> Extra legroom</span>
        <span><i className="seat-swatch seat-swatch--premium" /> Premium</span>
        <span><i className="seat-swatch seat-swatch--occupied" /> Taken</span>
      </div>

      <div className="cabin">
        {rows.map(({ row, seats }) => (
          <div className="cabin__row" key={row}>
            <span className="cabin__row-number">{row}</span>
            {LETTERS.map((letter) => {
              const seat = seats[letter];
              if (!seat) return <span key={letter} />;
              return (
                <button
                  key={letter}
                  type="button"
                  className={`seat seat--${seat.category}${seat.status === "occupied" ? " seat--occupied" : ""}`}
                  disabled={seat.status === "occupied"}
                  onClick={() => onSelectSeat(passengerIndex, row, letter)}
                  title={`${row}${letter}${seat.price ? ` (+₹${seat.price})` : ""}`}
                >
                  {seat.status !== "occupied" && letter}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
