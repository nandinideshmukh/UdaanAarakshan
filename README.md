# Udaan Aarakshan (Agentic Airline Booking)

![Architecture Diagram](Architecture.png)

Welcome to **Udaan Aarakshan**, a next-generation airline booking platform powered entirely by Agentic AI. 

Unlike traditional airline websites that force users through 5 to 7 static web pages (Search -> Select -> Passengers -> Seats -> Baggage -> Payment), this application provides a **Seamless Single-Page Chat Interface**. The user simply chats naturally with the AI, and the AI autonomously triggers backend tools to progress the booking, rendering dynamic, interactive UI widgets (Flight Boards, Seat Maps) directly inside the chat window.

## Core Architecture & Novelty

This project was built from scratch without bulky frameworks (like LangChain or LangGraph) to maximize control, lower token usage, and demonstrate deep architectural understanding.

### 1. Custom Multi-Provider LLM Gateway
Agentic tool-calling loops consume massive amounts of tokens, often hitting free-tier rate limits. This project implements a custom LLM orchestration layer that abstracts API shapes. If the primary provider (Groq) hits a `RateLimitError` mid-conversation, the gateway seamlessly translates the payload and falls back to **OpenAI**, and then to **Gemini**, preventing the app from crashing.

### 2. Zero-Framework Context Management (State Machine)
Instead of blindly appending massive chat transcripts (which causes LLM hallucination), context is managed via a strict **Dual-Layer Memory System**:
*   **The Ground Truth:** A strict JSON state object in Redis tracks the exact booking progress.
*   **Transactional Rollbacks:** The loop takes a `copy.deepcopy()` of the state before every turn. If an API rate-limits mid-turn, the backend instantly rolls back to the pristine backup, preventing corrupted "ghost" data (like half-added passengers) from leaking to the UI.

### 3. Three-Tier Data Fallback & Dynamic Pricing
To ensure the app always returns flights during demos, it uses a 3-tier safety net:
1.  **Tier 1 (Duffel API):** Real flights, real prices.
2.  **Tier 2 (AviationStack API + LLM Pricing):** Real flight schedules. Because AviationStack does not provide prices, the LLM dynamically evaluates the airline brand (e.g., Budget vs. Premium) and flight duration to estimate a highly realistic market fare.
3.  **Tier 3 (LLM Synthetic):** Fully hallucinated flights and prices if all APIs fail.

## Detailed Documentation

For a deep dive into how the systems work, please refer to the files in the `docs/` directory:

*   [Agent Flow & Decision Logic](docs/Agent_Flow.md) - Mermaid ReAct loop diagram.
*   [Technical Architecture](docs/technical.md) - Tech stack, gateway failover, and pricing mechanism test results.
*   [Memory & Context Management](docs/memory.md) - How the zero-framework transactional rollback works.
*   [Backend Overview](docs/backend_README.md) - FastAPI structure and Orchestrators.
*   [Frontend Overview](docs/frontend_README.md) - React structure and dynamic card rendering.
*   [Tools Index](docs/tools.md) - Exhaustive inputs/outputs for the AI's backend tools.
*   [Development Challenges](docs/Challenges.md) - API constraints, the Gemini signature bug, and UI deduplication.

## Tech Stack
*   **Frontend:** React, Vite, CSS
*   **Backend:** Python, FastAPI, Pydantic
*   **Database/Cache:** Upstash Redis
*   **Deployment:** Vercel (Monorepo setup)
