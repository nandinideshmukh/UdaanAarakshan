from fastapi import APIRouter, Request

from app.services.email_client import send_confirmation_email

router = APIRouter()


@router.post("/email-worker")
async def email_worker(request: Request):
    """
    Consumer endpoint that QStash calls back with the payload published in
    email_agent.queue_confirmation_email(). In production, verify the
    Upstash-Signature header against QSTASH_CURRENT_SIGNING_KEY /
    QSTASH_NEXT_SIGNING_KEY before trusting the body.
    """
    payload = await request.json()
    await send_confirmation_email(
        to=payload["to"],
        subject=payload["subject"],
        html=payload["html"],
    )
    return {"status": "sent"}
