import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const LETTERS = ["A", "B", "C", "D", "E", "F"];

export default function SeatMap({ flightNumber, selectedSeat, onSelect }) {
  const [seatmap, setSeatmap] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getSeatMap(flightNumber)
      .then((data) => {
        if (!cancelled) setSeatmap(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [flightNumber]);

  const rows = useMemo(() => {
    if (!seatmap) return [];
    const byRow = {};
    for (const seat of seatmap.seats) {
      byRow[seat.row] = byRow[seat.row] || {};
      byRow[seat.row][seat.letter] = seat;
    }
    return Object.entries(byRow)
      .map(([row, seats]) => ({ row: Number(row), seats }))
      .sort((a, b) => a.row - b.row);
  }, [seatmap]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!seatmap) return <p style={{ color: "#6b6558" }}>Loading seat map…</p>;

  function seatClass(seat) {
    const isSelected =
      selectedSeat && selectedSeat.row === seat.row && selectedSeat.letter === seat.letter;
    const classes = ["seat", `seat--${seat.category}`];
    if (seat.status === "occupied") classes.push("seat--occupied");
    if (isSelected) classes.push("seat--selected");
    return classes.join(" ");
  }

  return (
    <div>
      <div className="seatmap-legend">
        <span><i className="seat-swatch seat-swatch--standard" /> Standard</span>
        <span><i className="seat-swatch seat-swatch--extra_legroom" /> Extra legroom</span>
        <span><i className="seat-swatch seat-swatch--premium" /> Premium</span>
        <span><i className="seat-swatch seat-swatch--occupied" /> Occupied</span>
        <span><i className="seat-swatch seat-swatch--selected" /> Selected</span>
      </div>

      <div className="cabin">
        <div className="cabin__nose">✈ Front of aircraft</div>
        {rows.map(({ row, seats }) => (
          <div className="cabin__row" key={row}>
            <span className="cabin__row-number">{row}</span>
            {LETTERS.map((letter, i) => {
              const seat = seats[letter];
              if (!seat) return <span key={letter} />;
              return (
                <span key={letter} style={{ display: "contents" }}>
                  <button
                    type="button"
                    className={seatClass(seat)}
                    disabled={seat.status === "occupied"}
                    onClick={() => onSelect(seat)}
                    title={`${row}${letter} — ${seat.category.replace("_", " ")}${seat.price ? ` (+₹${seat.price})` : ""}`}
                  >
                    {letter}
                  </button>
                  {letter === "C" && <span className="cabin__aisle" />}
                </span>
              );
            })}
          </div>
        ))}
      </div>

      {selectedSeat && (
        <div className="approval-banner" style={{ marginTop: 16 }}>
          Seat {selectedSeat.row}{selectedSeat.letter} selected
          {selectedSeat.price > 0 && ` — +₹${selectedSeat.price.toLocaleString()}`}
        </div>
      )}
    </div>
  );
}
