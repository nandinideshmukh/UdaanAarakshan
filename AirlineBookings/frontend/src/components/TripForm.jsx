import { useState } from "react";

const CABIN_CLASSES = ["economy", "premium_economy", "business", "first"];

export default function TripForm({ onSearch, loading, error }) {
  const [trip, setTrip] = useState({
    source: "",
    destination: "",
    depart_date: "",
    return_date: "",
    max_stops: "",
    cabin_class: "economy",
    budget: "",
    preferred_airlines: "",
  });

  function update(field, value) {
    setTrip((t) => ({ ...t, [field]: value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    onSearch({
      source: trip.source,
      destination: trip.destination,
      depart_date: trip.depart_date,
      return_date: trip.return_date || null,
      max_stops: trip.max_stops ? Number(trip.max_stops) : null,
      cabin_class: trip.cabin_class,
      budget: trip.budget ? Number(trip.budget) : null,
      preferred_airlines: trip.preferred_airlines
        ? trip.preferred_airlines.split(",").map((a) => a.trim()).filter(Boolean)
        : [],
    });
  }

  return (
    <div className="panel">
      <h1 className="page-title">Plan a trip</h1>
      <p className="page-subtitle">
        The Search Agent will look for flights matching what you enter below.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="field-row">
          <div className="field">
            <label htmlFor="source">From</label>
            <input
              id="source"
              type="text"
              placeholder="BOM"
              value={trip.source}
              onChange={(e) => update("source", e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="destination">To</label>
            <input
              id="destination"
              type="text"
              placeholder="DEL"
              value={trip.destination}
              onChange={(e) => update("destination", e.target.value)}
              required
            />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="depart">Depart</label>
            <input
              id="depart"
              type="date"
              value={trip.depart_date}
              onChange={(e) => update("depart_date", e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="return">Return (optional)</label>
            <input
              id="return"
              type="date"
              value={trip.return_date}
              onChange={(e) => update("return_date", e.target.value)}
            />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="cabin">Cabin</label>
            <select
              id="cabin"
              value={trip.cabin_class}
              onChange={(e) => update("cabin_class", e.target.value)}
            >
              {CABIN_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="stops">Max stops</label>
            <input
              id="stops"
              type="number"
              min="0"
              placeholder="Any"
              value={trip.max_stops}
              onChange={(e) => update("max_stops", e.target.value)}
            />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="budget">Budget (optional)</label>
            <input
              id="budget"
              type="number"
              min="0"
              placeholder="e.g. 15000"
              value={trip.budget}
              onChange={(e) => update("budget", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="airlines">Preferred airlines</label>
            <input
              id="airlines"
              type="text"
              placeholder="IndiGo, Air India"
              value={trip.preferred_airlines}
              onChange={(e) => update("preferred_airlines", e.target.value)}
            />
          </div>
        </div>

        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search flights"}
        </button>
      </form>
    </div>
  );
}
