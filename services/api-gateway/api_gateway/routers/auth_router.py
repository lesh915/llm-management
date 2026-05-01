"""인증 엔드포인트 (토큰 발급)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import create_access_token
from ..config import GATEWAY_API_KEY

router = APIRouter()


class TokenRequest(BaseModel):
    api_key: str
    subject: str = "client"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
async def issue_token(body: TokenRequest) -> TokenResponse:
    """
    API Key를 제출하여 JWT 액세스 토큰 발급.
    GATEWAY_API_KEY가 설정되지 않은 경우 개발 환경용 토큰을 발급.
    """
    if GATEWAY_API_KEY and body.api_key != GATEWAY_API_KEY:
        raise HTTPException(401, "유효하지 않은 API 키")

    token = create_access_token(subject=body.subject)
    return TokenResponse(access_token=token)
