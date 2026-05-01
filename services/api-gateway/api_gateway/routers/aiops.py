"""aiops-service 프록시 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..auth import get_current_user
from ..config import AIOPS_SERVICE_URL
from ..proxy import reverse_proxy

router = APIRouter()
_auth = Depends(get_current_user)


@router.api_route("/metrics", methods=["GET", "POST"])
@router.api_route("/metrics/{path:path}", methods=["GET", "POST"])
async def proxy_metrics(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "metrics"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, AIOPS_SERVICE_URL, full_path)


@router.api_route("/events", methods=["GET", "POST"])
@router.api_route("/events/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_events(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "events"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, AIOPS_SERVICE_URL, full_path)


@router.api_route("/rules", methods=["GET", "POST"])
@router.api_route("/rules/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_rules(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "rules"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, AIOPS_SERVICE_URL, full_path)


@router.api_route("/reports/{path:path}", methods=["GET"])
async def proxy_reports(request: Request, path: str = "", _: dict = _auth) -> Response:
    return await reverse_proxy(request, AIOPS_SERVICE_URL, f"reports/{path}")
