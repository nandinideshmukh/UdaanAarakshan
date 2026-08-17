# AirlineBookings Backend Documentation

This is a Python FastAPI backend that powers an AI agent capable of executing an entire flight booking workflow using real-world flight APIs.

## Main Services (`app/services/`)

### `llm/orchestrator.py` & adapters (`gemini_adapter.py`, `groq_adapter.py`, `openai_adapter.py`)
- **What it does:** The multi-provider LLM Gateway. It handles calling AI models (Groq, OpenAI, Gemini). If one model hits a rate limit or fails, it automatically translates the request and falls back to the next one.
- **Input (IP):** A prompt and a list of available tools.
- **Output (OP):** The AI's text response or a decision to call a tool (like `search_flights`).

### `aviationstack_client.py` & `duffel_client.py`
- **What it does:** Talks to real-world flight APIs to get actual airplane schedules.
- **Input (IP):** Origin IATA code, Destination IATA code, Date.
- **Output (OP):** Lists of actual scheduled flights.

### `chat_session.py`
- **What it does:** Remembers the state of a user's booking in Redis (e.g., remembering which flight they picked while they type in passenger names).
- **Input (IP):** Session ID.
- **Output (OP):** The saved history and current booking state.

## AI Agents (`app/agents/`)

### `chat_orchestrator.py`
- **What it does:** The main brain of the chat experience. It takes the user's message, checks the booking state, and asks the LLM what to do next. It runs a loop where the LLM can call multiple tools (search, check seats) before replying to the user.
- **Input (IP):** The user's text message.
- **Output (OP):** A text reply and UI "cards" to show on the frontend.

### `chat_tools.py`
- **What it does:** The actual actions the AI is allowed to take. Contains functions like `search_flights`, `add_passenger`, `select_seat`, and `confirm_booking`.
- **Input (IP):** JSON arguments decided by the LLM (e.g., `{"source": "DEL", "destination": "BOM"}`).
- **Output (OP):** Mutates the booking state and returns data to the LLM so it knows what happened.

### `search_agent.py`
- **What it does:** Handles the 3-tier flight search fallback. First tries Duffel for real prices. If that fails, it tries AviationStack for real schedules (and uses AI to estimate a realistic price). If that fails, it generates synthetic (fake) flights so the app doesn't crash.
- **Input (IP):** Trip request (source, dest, date).
- **Output (OP):** A list of flight options.

### `seatmap_agent.py`
- **What it does:** Generates airplane seat maps.
- **Input (IP):** Flight number.
- **Output (OP):** A grid of seats with pricing and availability statuses.