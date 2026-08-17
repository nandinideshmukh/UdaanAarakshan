import { useState } from "react";

const MEALS = [
  { value: "none", label: "No preference" },
  { value: "standard", label: "Standard" },
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "halal", label: "Halal" },
  { value: "kosher", label: "Kosher" },
  { value: "gluten_free", label: "Gluten-free" },
];

export default function Ancillaries({ onSubmit, loading, error }) {
  const [extraBags, setExtraBags] = useState(0);
  const [extraCarryOn, setExtraCarryOn] = useState(false);
  const [meal, setMeal] = useState("none");
  const [priorityBoarding, setPriorityBoarding] = useState(false);
  const [wifi, setWifi] = useState(false);
  const [specialAssistance, setSpecialAssistance] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit({
      baggage: { extra_checked_bags: extraBags, extra_carry_on: extraCarryOn },
      services: {
        meal,
        priority_boarding: priorityBoarding,
        wifi,
        special_assistance: specialAssistance || null,
      },
    });
  }

  return (
    <div className="panel">
      <h1 className="page-title">Baggage & in-flight services</h1>
      <p className="page-subtitle">Add extras — all optional, priced at checkout.</p>

      {error && <div className="error-banner">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="addon-block">
          <label>Baggage</label>
          <div className="addon-row">
            <span>Extra checked bags</span>
            <div className="stepper">
              <button
                type="button"
                className="stepper__btn"
                onClick={() => setExtraBags((n) => Math.max(0, n - 1))}
              >
                −
              </button>
              <span className="stepper__value">{extraBags}</span>
              <button
                type="button"
                className="stepper__btn"
                onClick={() => setExtraBags((n) => Math.min(5, n + 1))}
              >
                +
              </button>
            </div>
            <span className="addon-price">₹800 each</span>
          </div>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={extraCarryOn}
              onChange={(e) => setExtraCarryOn(e.target.checked)}
            />
            Extra carry-on bag <span className="addon-price">+₹400</span>
          </label>
        </div>

        <div className="addon-block">
          <label htmlFor="meal">Meal preference</label>
          <select id="meal" value={meal} onChange={(e) => setMeal(e.target.value)}>
            {MEALS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div className="addon-block">
          <label>In-flight services</label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={priorityBoarding}
              onChange={(e) => setPriorityBoarding(e.target.checked)}
            />
            Priority boarding <span className="addon-price">+₹300</span>
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={wifi} onChange={(e) => setWifi(e.target.checked)} />
            In-flight Wi-Fi <span className="addon-price">+₹500</span>
          </label>
        </div>

        <div className="field">
          <label htmlFor="assist">Special assistance (optional)</label>
          <input
            id="assist"
            type="text"
            placeholder="e.g. wheelchair, visual assistance"
            value={specialAssistance}
            onChange={(e) => setSpecialAssistance(e.target.value)}
          />
        </div>

        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Saving…" : "Review & book"}
        </button>
      </form>
    </div>
  );
}
