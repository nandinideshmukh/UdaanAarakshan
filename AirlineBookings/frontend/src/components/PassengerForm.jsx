import { useState } from "react";

export default function PassengerForm({ onSubmit, loading, error }) {
  const [form, setForm] = useState({
    full_name: "",
    date_of_birth: "",
    passport_number: "",
    nationality: "",
    contact_email: "",
    contact_phone: "",
    redress_number: "",
  });

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit({ ...form, redress_number: form.redress_number || null });
  }

  return (
    <div className="panel">
      <h1 className="page-title">Passenger details</h1>
      <p className="page-subtitle">
        Enter details exactly as they appear on the passport — required for check-in.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="full_name">Full name</label>
          <input
            id="full_name"
            type="text"
            placeholder="As shown on passport"
            value={form.full_name}
            onChange={(e) => update("full_name", e.target.value)}
            required
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="dob">Date of birth</label>
            <input
              id="dob"
              type="date"
              value={form.date_of_birth}
              onChange={(e) => update("date_of_birth", e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="nationality">Nationality</label>
            <input
              id="nationality"
              type="text"
              placeholder="Indian"
              value={form.nationality}
              onChange={(e) => update("nationality", e.target.value)}
              required
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="passport">Passport / ID number</label>
          <input
            id="passport"
            type="text"
            value={form.passport_number}
            onChange={(e) => update("passport_number", e.target.value)}
            required
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="cemail">Contact email</label>
            <input
              id="cemail"
              type="email"
              value={form.contact_email}
              onChange={(e) => update("contact_email", e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="cphone">Contact phone</label>
            <input
              id="cphone"
              type="text"
              placeholder="+91 98765 43210"
              value={form.contact_phone}
              onChange={(e) => update("contact_phone", e.target.value)}
              required
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="redress">Redress number (optional)</label>
          <input
            id="redress"
            type="text"
            placeholder="If issued by a security agency"
            value={form.redress_number}
            onChange={(e) => update("redress_number", e.target.value)}
          />
        </div>

        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Saving…" : "Continue to seat selection"}
        </button>
      </form>
    </div>
  );
}
