# Agent Tools Documentation

This file documents the tools available to the AI agents inside the backend. The system divides its operations into two distinct tool scopes:
1. **Trip Planning Agent Tools (`tools.py`):** Used by the off-line one-shot comparator/planning agent.
2. **Chatbot Booking Agent Tools (`chat_tools.py`):** Used during the real-time interactive user conversation to guide the booking process step-by-step.

---

## 1. Trip Planning Agent Tools (`backend/app/agents/tools.py`)

These tools are designed for autonomous, off-line flight lookup, availability checking, and submitting recommendations.

### `search_flights`
- **What it does:** Searches for flights matching user requirements using standard, multi-tiered data fallbacks (Duffel API -> AviationStack API -> LLM synthetic data).
- **Input (IP):** 
  - `source` (string, Required): Origin airport or city name.
  - `destination` (string, Required): Destination airport or city name.
  - `depart_date` (string in `YYYY-MM-DD` format, Required).
  - `cabin_class` (string: `"economy"`, `"premium_economy"`, `"business"`, `"first"`, Optional).
  - `max_stops` (integer, Optional).
  - `budget` (number, Optional).
- **Output (OP):** A JSON object containing a `request_id` and a list of `options`. Each flight option includes:
  - `airline` (string)
  - `flight_number` (string)
  - `price` (float)
  - `duration_minutes` (integer)
  - `stops` (integer)
  - `departure_time` (string)
  - `arrival_time` (string)

### `check_seat_availability`
- **What it does:** Returns a high-level count of open seats in each section of the plane. Useful when a passenger group needs to check if they can sit together before confirming.
- **Input (IP):** 
  - `flight_number` (string, Required).
- **Output (OP):** A JSON object mapping seat categories to their available seat counts:
  - `flight_number` (string)
  - `available_by_category` (object, e.g., `{"standard": 24, "extra_legroom": 5, "premium": 12}`)

### `rank_and_finalize`
- **What it does:** Submits the final recommendations list. This ends the planning agent's thought loop.
- **Input (IP):** 
  - `best_picks` (array of flight objects, Required).
  - `reasoning` (string, Required explaining choice rationale).
- **Output (OP):** `{"acknowledged": True}`

---

## 2. Chatbot Booking Agent Tools (`backend/app/agents/chat_tools.py`)

These tools manage the active chat state inside the Redis session, progressing the traveler sequentially from flight selection to ticketing.

### `search_flights` (Chat Version)
- **What it does:** Similar to the planning version, but returns a specific React frontend card schema to show the flight board in the chat log. Saves findings directly under the session's active state.
- **Input/Output (IP/OP):** Identical request shape as the Planning version, but returns a tuple: a backend receipt JSON, and a React card schema `{ "type": "flight_options", "data": { "options": [...] } }`.

### `select_flight`
- **What it does:** Freezes the price of a flight option, issues an official PNR hold, and clears stale price reviews.
- **Input (IP):** 
  - `flight_number` (string, Required).
- **Output (OP):** A tuple of:
  - Backend receipt: `{"pnr": str, "held_price": float, "expires_at": str}`
  - Frontend hold card metadata of type `"hold"`.

### `set_passenger_count`
- **What it does:** Explicitly sets the number of passengers expected for this reservation before collecting details.
- **Input (IP):**
  - `count` (integer between 1 and 9, Required).
- **Output (OP):** `{"passenger_count": count}` (no UI card).

### `add_passenger`
- **What it does:** Appends passenger details to the booking session list and computes their fare category based on date of birth.
- **Input (IP):**
  - `full_name`, `passport_number`, `nationality`, `contact_email`, `contact_phone` (strings, Required).
  - `date_of_birth` (string in `YYYY-MM-DD` format, Required).
  - `redress_number` (string, Optional).
- **Output (OP):** State summary showing current progress (e.g. 2 of 3 passengers added), and a passenger list update UI card.

### `get_seatmap`
- **What it does:** Fetches the full interactive seating grid for the passenger to click through.
- **Input (IP):** `{}` (reads the selected flight directly from the active state).
- **Output (OP):** Detailed seat arrangement matrix, and a visual seat selector card of type `"seatmap"`.

### `select_seat`
- **What it does:** Assigns a specific seat to a passenger. Detects and handles conflicts if a seat has been reserved by another process while the page was open.
- **Input (IP):**
  - `passenger_index` (1-indexed passenger integer, Required).
  - `row` (integer, Required).
  - `letter` (string, Required).
- **Output (OP):** Seat confirmation details (and proposed alternative coordinates if the seat was already occupied).

### `set_ancillaries`
- **What it does:** Configures baggage allowances, in-flight meals, wifi, priority boarding, and special assistance on a per-passenger basis.
- **Input (IP):**
  - `passenger_index` (1-indexed integer, Required).
  - `extra_checked_bags` (integer, Optional), `extra_carry_on` (boolean, Optional).
  - `meal` (one of `"none"`, `"standard"`, `"vegetarian"`, `"vegan"`, `"halal"`, `"kosher"`, `"gluten_free"`, Optional).
  - `priority_boarding`, `wifi` (booleans, Optional).
  - `special_assistance` (string, Optional).
- **Output (OP):** State update confirmation receipt, and an updated passenger list card.

### `review_booking`
- **What it does:** Calculates and serves a full, itemized pricing summary (base rate, tax, seats, bags) before finalizing a charge.
- **Input (IP):** `{}` (reads state data).
- **Output (OP):** Itemized price layout and a review UI card of type `"review"`. **This must run once before a user is allowed to purchase.**

### `confirm_booking`
- **What it does:** Charges the user, releases hold states, issues the ticket, and queues up confirmation emails.
- **Input (IP):** `{}` (requires `reviewed` flag to be set to `True` by `review_booking`).
- **Output (OP):** Confirmation details, and a booking confirmation card of type `"booking_confirmation"`.

### `get_booking_status`
- **What it does:** Searches database registers for an existing flight reservation via its PNR code.
- **Input (IP):**
  - `pnr` (string, Required).
- **Output (OP):** Current booking status, and an itemized single or group reservation card.

### `cancel_booking`
- **What it does:** Irreversibly cancels a live reservation, notifies passengers, and releases seat maps.
- **Input (IP):**
  - `pnr` (string, Required).
- **Output (OP):** Cancellation confirmation, and a booking cancelled card of type `"booking_cancelled"`.