from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import FeedbackRequest
from app.services.json_store import save_json

router = APIRouter()


@router.post("")
async def submit_feedback(feedback: FeedbackRequest, user_id: str = Depends(get_current_user)):
    await save_json(
        f"feedback:{feedback.request_id}",
        {**feedback.model_dump(), "user_id": user_id},
    )
    return {"status": "received"}
