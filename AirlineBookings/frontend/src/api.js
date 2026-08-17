const BASE = "/api";

function authHeaders() {
  const token = sessionStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body wasn't JSON */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: { email, password } }),

  // --- Conversational booking agent — the whole journey, one endpoint ---
  sendChatMessage: (sessionId, message) =>
    request("/chat/message", { method: "POST", body: { session_id: sessionId, message } }),

  // --- Legacy fixed pipeline (still available, untouched) ---
  search: (trip) => request("/trip/search", { method: "POST", body: trip }),
  compare: (requestId, trip) =>
    request(`/trip/compare/${requestId}`, { method: "POST", body: trip }),
  planTrip: (trip) => request("/agent/plan-trip", { method: "POST", body: trip }),
  refine: (requestId, trip, feedback) =>
    request(`/trip/refine/${requestId}`, {
      method: "POST",
      body: { trip, refinement: { feedback } },
    }),
  approve: (requestId) => request(`/trip/approve/${requestId}`, { method: "POST" }),
  holdFlight: (requestId, flight) =>
    request(`/reservation/hold/${requestId}`, { method: "POST", body: flight }),
  getHold: (requestId) => request(`/reservation/hold/${requestId}`),
  lookupPnr: (pnr) => request(`/reservation/pnr/${pnr}`),
  submitPassenger: (requestId, passenger) =>
    request(`/reservation/passenger/${requestId}`, { method: "POST", body: passenger }),
  getPassenger: (requestId) => request(`/reservation/passenger/${requestId}`),
  getSeatMap: (flightNumber) => request(`/reservation/seatmap/${flightNumber}`),
  submitAncillaries: (requestId, selection) =>
    request(`/reservation/ancillaries/${requestId}`, {
      method: "POST",
      body: { request_id: requestId, ...selection },
    }),
  getAncillaries: (requestId) => request(`/reservation/ancillaries/${requestId}`),
  book: (payload) => request("/trip/book", { method: "POST", body: payload }),
  listBookings: () => request("/trip/bookings"),
  submitFeedback: (requestId, rating, comment) =>
    request("/feedback", { method: "POST", body: { request_id: requestId, rating, comment } }),
};
