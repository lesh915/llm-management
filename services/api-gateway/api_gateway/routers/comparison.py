"""comparison-engine 프록시 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, WebSocket

from ..auth import get_current_user
from ..config import COMPARISON_ENGINE_URL
from ..proxy import reverse_proxy

router = APIRouter()
_auth = Depends(get_current_user)


@router.api_route("/tasks", methods=["GET", "POST"])
@router.api_route("/tasks/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_tasks(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "tasks"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, COMPARISON_ENGINE_URL, full_path)


@router.api_route("/datasets", methods=["GET", "POST"])
@router.api_route("/datasets/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_datasets(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "datasets"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, COMPARISON_ENGINE_URL, full_path)
