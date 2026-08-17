# Development Challenges Faced

Building a fully agentic airline booking system presented several unique challenges:

### 1. LLM Rate Limits and API Quotas
**The Problem:** Agentic loops (where the LLM calls tools repeatedly in a single turn) consume a massive amount of tokens. Free-tier accounts on Groq, OpenAI, and Gemini were constantly hitting RateLimitErrors (`429`) or Quota Exceeded errors.
**The Solution:** We built a custom multi-provider fallback gateway (`app/services/llm/orchestrator.py`). If Groq rate-limits, the exact same tool-calling payload is sanitized and sent to OpenAI. If OpenAI fails, it falls back to Gemini.

### 2. Provider-Specific Quirks (The Gemini `thought_signature` bug)
**The Problem:** Gemini requires a strict `thoughtSignature` for tool calls to maintain reasoning continuity. When falling back from OpenAI (which doesn't use signatures) to Gemini mid-conversation, Gemini would reject the request with a `400 Bad Request` because historical tool calls lacked signatures.
**The Solution:** We implemented a sanitization layer (`gemini_adapter.py`). If a historical tool call lacks a signature (because it came from another provider), the adapter flattens that specific tool call into a plain text transcript (e.g., `Action: called search_flights...`) instead of sending it as a native unsigned function call, safely bypassing the validation crash.

### 3. Flight API Limitations (AviationStack Paid Tiers)
**The Problem:** The AviationStack free tier does not allow access to the "autocomplete" endpoint, causing the app to crash with a `403 Forbidden` when users typed city names instead of 3-letter IATA codes. Furthermore, AviationStack only provides schedules, not prices.
**The Solution:** 
- **IATA Resolution:** Replaced the API autocomplete call with a fast LLM prompt that translates city names to IATA codes dynamically.
- **Pricing:** Built an AI-driven synthetic pricing model that takes a real schedule/duration from AviationStack and uses the LLM to estimate a plausible real-world INR fare.

### 4. UI Deduplication in Agentic Loops
**The Problem:** The AI agent sometimes loops and calls the `search_flights` tool multiple times in the background before answering the user. The frontend would blindly render all the resulting "Flight Options" UI cards, resulting in duplicated widgets on the screen.
**The Solution:** Updated the React `ChatBubble` to hash the data of incoming cards and strictly deduplicate them, ensuring that if the LLM hallucinates multiple identical tool calls, the user only ever sees one clean UI card.

### 5. Pricing Currency Consistency and Display
**The Problem:** The app's flight data sources can return prices in different currencies (for example, Duffel may return USD/GBP/EUR depending on account settings), but the frontend was hardcoded to display all prices as ₹. This created a mismatch between the actual API response and the UI, making the booking flow misleading.
**The Solution:** We normalized the API contract so each flight option includes its real `currency` alongside `price`, and the frontend formats values using that currency instead of assuming INR. This keeps the response truthful and the UI aligned with the real fare source.

### 6. Managing Stateful Chat
**The Problem:** Traditional LLM chat is stateless text. Booking a flight is highly stateful (picking a flight, freezing the price, collecting passenger details one by one). 
**The Solution:** Implemented a Redis-backed `chat_session.py` that keeps a strict JSON object of the booking state. This state is injected into the LLM's system prompt on every turn as "Ground Truth", preventing the LLM from forgetting passenger details or hallucinating booked flights.