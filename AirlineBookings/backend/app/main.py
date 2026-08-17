from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agent, auth, chat, feedback, reservation, trip, webhooks

app = FastAPI(
    title="AI Agentic Flight Search & Booking API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Every request that hits Vercel serverless is stateless — routers below
# must not rely on in-memory state surviving between calls. Use Redis/DB.
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(trip.router, prefix="/api/trip", tags=["trip"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(reservation.router, prefix="/api/reservation", tags=["reservation"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
