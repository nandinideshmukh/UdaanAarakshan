import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # --- Core ---
    ENV: str = os.getenv("ENV", "production")
    # Same-origin deployment: frontend and API share one Vercel domain, so
    # the browser never sends cross-origin requests. This only needs to
    # allow your own domain (for local dev + preview deployments) — it's
    # not a public API meant to be called from other sites.
    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173",  # Vite dev server
        ).split(",")
        if o.strip()
    ]

    # --- Auth ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"

    # --- LLM providers (Groq, Gemini, OpenAI — no Anthropic) ---
    # The gateway (services/llm/orchestrator.py) picks whichever of these is
    # configured, in this priority order, with automatic fallback.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_PROVIDER_PRIORITY: list[str] = [
        p.strip() for p in os.getenv("LLM_PROVIDER_PRIORITY", "groq,gemini,openai").split(",") if p.strip()
    ]

    # --- Real flight data (Duffel API) ---
    # Optional — if unset, search_agent falls back to LLM-generated flight
    # data (clearly less realistic, but keeps the app usable without signup).
    # Note: Amadeus's self-service developer portal was fully decommissioned
    # July 17, 2026 (only Amadeus Enterprise, sales-contract-only, remains) —
    # Duffel is the replacement here: still self-serve, free test sandbox key.
    DUFFEL_API_KEY: str = os.getenv("DUFFEL_API_KEY", "")
    DUFFEL_VERSION: str = os.getenv("DUFFEL_VERSION", "v2")

    # --- Real flight SCHEDULE data (AviationStack) — optional second tier ---
    # AviationStack has no pricing data at all (it's a flight-tracking API,
    # not a fares/offers API) — search_agent.py pairs its real
    # airline/flight-number/schedule data with a synthetic pricing model.
    # Tried after Duffel (which has real prices) if Duffel isn't configured.
    AVIATIONSTACK_API_KEY: str = os.getenv("AVIATIONSTACK_API_KEY", "")

    # --- Upstash Redis (cache + rate limiting) ---
    UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL", "")
    UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

    # --- Upstash QStash (message queue) ---
    QSTASH_TOKEN: str = os.getenv("QSTASH_TOKEN", "")
    QSTASH_CURRENT_SIGNING_KEY: str = os.getenv("QSTASH_CURRENT_SIGNING_KEY", "")
    QSTASH_NEXT_SIGNING_KEY: str = os.getenv("QSTASH_NEXT_SIGNING_KEY", "")
    # Public base URL of THIS deployment, so QStash knows where to call back
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")

    # --- Email ---
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() == "true"
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "bookings@example.com")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
