from fastapi import APIRouter, Depends, HTTPException
from httpx import HTTPStatusError

from app.agents.chat_orchestrator import handle_chat_message
from app.core.security import get_current_user
from app.models.schemas import ChatCard, ChatRequest, ChatResponse

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest, user_id: str = Depends(get_current_user)):
    """
    The whole booking journey — search, flight selection, multi-passenger
    details, seats, ancillaries, and final booking — happens through this
    single endpoint, one user message at a time. No separate forms/steps.
    """
    try:
        reply, cards, session_id = await handle_chat_message(payload.session_id, payload.message)
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider request failed: {e.response.status_code} {e.response.text[:300]}",
        ) from e

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        cards=[ChatCard(**c) for c in cards],
    )
