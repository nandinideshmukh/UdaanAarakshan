# Technical Architecture

AirlineBookings (Udaan Aarakshan) is an Agentic AI application. Instead of hardcoded step-by-step forms, the user chats with an LLM, and the LLM decides which backend tools to call to progress the booking.

## Stack
- **Frontend:** React, Vite, CSS (No heavy component libraries, custom chat UI)
- **Backend:** Python, FastAPI, Pydantic (for strict LLM JSON parsing)
- **State & Memory:** Upstash Redis
- **LLMs:** Groq (primary), OpenAI (fallback 1), Gemini (fallback 2)
- **External APIs:** Duffel (Flights), AviationStack (Schedules)

## The LLM Gateway (Project Novelty)
The defining technical novelty of this project is its **Custom Multi-Provider LLM Gateway**. 

Because agentic loops (where an AI calls multiple tools back-to-back in a single turn) consume a massive amount of tokens, free-tier accounts constantly hit rate limits. To solve this, the application abstracts away the LLM providers. It uses an internal standard (`LLMMessage`, `LLMToolCall`) instead of native API shapes.

1. The application requests a generation.
2. The `orchestrator.py` translates the internal standard to Groq's wire format.
3. If Groq throws a `RateLimitError` or quota exhaustion, the orchestrator catches it, logs the fallback, translates the *exact same* internal standard to OpenAI's wire format, and seamlessly tries again.
4. If OpenAI fails, it translates to Gemini's unique `contents/parts` wire format and tries a third time.

This ensures the user never experiences a broken chat flow just because an AI provider had a temporary outage or rate limit.

## Seamless Single-Page User Experience
Another core novelty is the **Chat-Driven Booking Journey**. Traditional airline websites force users through 5 to 7 different hardcoded web pages (Search -> Select -> Passengers -> Seats -> Baggage -> Payment). 

In this application, **the user gets everything on one page**. The LLM manages the state and dynamically renders interactive UI "Cards" (like a seat map or a flight board) directly inside the chat window. The user simply types what they want, and the AI progresses the booking state behind the scenes.

## Agentic Flow
The core loop lives in `chat_orchestrator.py`:
1. User sends a message.
2. Backend retrieves the session state (selected flights, passengers) from Redis.
3. The LLM is prompted with the state and available tools (`search_flights`, `add_passenger`, `select_seat`, `review_booking`, `confirm_booking`).
4. The LLM decides to call a tool (e.g., `search_flights({"source":"DEL", "destination":"BOM"})`).
5. The backend executes the Python function, saves the result to Redis, and appends a "Card" to the UI response.
6. The backend feeds the tool result *back* to the LLM in the same turn.
7. The LLM decides if it needs to call another tool, or if it has enough info to reply to the user.

## Three-Tier Data Fallback & Dynamic Pricing
To ensure the app never crashes during demos and always returns flights, it uses a 3-tier fallback:
1. **Tier 1 (Duffel):** Real flights, real prices.
2. **Tier 2 (AviationStack + LLM Pricing):** Real flight schedules, but LLM-estimated synthetic pricing.
3. **Tier 3 (LLM Synthetic Fallback via Gateway):** If AviationStack fails or throws an error, the system falls back to generating fully synthetic flights and prices via the Multi-Provider LLM Gateway (Groq -> OpenAI -> Gemini).

### Pricing Mechanism Test Results
We explicitly tested the Tier 2 (AviationStack) dynamic pricing mechanism to ensure the LLM correctly infers realistic market rates . 

**Test Case:** Two identical 130-minute economy flights (one on IndiGo, one on Air India).

**_estimate_prices_via_llm (AI Estimation)**
*   IndiGo: INR 5,100
*   Air India: INR 5,800
*(The AI successfully recognizes Air India as a full-service carrier and prices it slightly higher than IndiGo, a budget carrier).*

**_formula_price (Deterministic Math Fallback)**
* Removed for now 
*   IndiGo: INR 3,300
*   Air India: INR 3,640
*(The math fallback correctly guarantees a baseline duration-based fare if the LLM fails).*
