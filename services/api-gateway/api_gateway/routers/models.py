"""model-registry-service 프록시 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..auth import get_current_user
from ..config import MODEL_REGISTRY_URL
from ..proxy import reverse_proxy

router = APIRouter()
_auth = Depends(get_current_user)


@router.api_route("/models", methods=["GET", "POST"])
@router.api_route("/models/{path:path}", methods=["GET", "POST", "PATCH", "DELETE", "PUT"])
async def proxy_models(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "models"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, MODEL_REGISTRY_URL, full_path)
