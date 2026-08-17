from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.core.security import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    # Replace with real user lookup + password hash check (e.g. via Postgres)
    user_id = payload.email  # placeholder
    token = create_access_token(user_id)
    return TokenResponse(access_token=token)
