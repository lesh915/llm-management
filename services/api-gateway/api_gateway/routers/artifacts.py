"""artifact-service 프록시 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..auth import get_current_user
from ..config import ARTIFACT_SERVICE_URL
from ..proxy import reverse_proxy

router = APIRouter()
_auth = Depends(get_current_user)


@router.api_route("/agents", methods=["GET", "POST"])
@router.api_route("/agents/{path:path}", methods=["GET", "POST", "PATCH", "DELETE", "PUT"])
async def proxy_agents(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "agents"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, ARTIFACT_SERVICE_URL, full_path)


@router.api_route("/artifacts/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_artifacts(request: Request, path: str = "", _: dict = _auth) -> Response:
    return await reverse_proxy(request, ARTIFACT_SERVICE_URL, f"artifacts/{path}")
