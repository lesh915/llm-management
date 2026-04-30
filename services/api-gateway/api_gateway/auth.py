"""API 게이트웨이 인증 미들웨어.

두 가지 인증 방식 지원:
1. API Key — X-API-Key 헤더 (간단한 서비스간 인증)
2. JWT Bearer token — Authorization: Bearer <token>

GATEWAY_API_KEY 또는 JWT_SECRET이 설정된 경우에만 인증 강제.
개발 환경에서는 두 값 모두 비어 있으면 인증 없이 통과.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader

from .config import GATEWAY_API_KEY, JWT_SECRET, JWT_ALG, JWT_EXPIRE

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    """JWT 액세스 토큰 발급."""
    try:
        from jose import jwt
    except ImportError:
        raise RuntimeError("python-jose가 설치되지 않았습니다.")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE),
        **(extra or {}),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _verify_jwt(token: str) -> dict:
    from jose import jwt, JWTError
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"유효하지 않은 토큰: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    api_key: str | None = Depends(_api_key_header),
) -> dict:
    """
    요청 인증 후 사용자 정보 딕셔너리 반환.

    인증이 설정되지 않은 환경(개발)에서는 anonymous 사용자로 통과.
    """
    # 인증 설정이 없으면 통과 (개발 환경)
    if not GATEWAY_API_KEY and JWT_SECRET == "change-me-in-production":
        return {"sub": "anonymous", "role": "admin"}

    # API Key 인증
    if GATEWAY_API_KEY and api_key:
        if api_key == GATEWAY_API_KEY:
            return {"sub": "api-key-client", "role": "service"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 API 키",
        )

    # JWT Bearer 인증
    if credentials:
        return _verify_jwt(credentials.credentials)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다. X-API-Key 또는 Bearer 토큰을 제공하세요.",
        headers={"WWW-Authenticate": "Bearer"},
    )
