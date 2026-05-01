"""HTTP 역방향 프록시 유틸리티."""
from __future__ import annotations

import logging

import httpx
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from .config import PROXY_TIMEOUT

logger = logging.getLogger(__name__)


async def reverse_proxy(
    request: Request,
    upstream: str,
    path: str,
) -> Response:
    """
    들어온 요청을 업스트림 서비스로 투명하게 전달합니다.

    - 쿼리 파라미터, 헤더, 바디를 그대로 전달
    - X-Request-ID 헤더를 추가하여 분산 추적 지원
    - 스트리밍 응답 처리
    """
    url = f"{upstream.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    # X-Request-ID 전파
    request_id = request.headers.get("x-request-id", "")
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    if request_id:
        headers["x-request-id"] = request_id

    body = await request.body()

    logger.debug("Proxying %s %s -> %s", request.method, request.url.path, url)

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            upstream_response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )
    except httpx.ConnectError as e:
        logger.error("Upstream connection error: %s -> %s", url, e)
        return Response(
            content=f'{{"error": "업스트림 서비스에 연결할 수 없습니다: {upstream}"}}',
            status_code=502,
            media_type="application/json",
        )
    except httpx.TimeoutException:
        logger.warning("Upstream timeout: %s", url)
        return Response(
            content='{"error": "업스트림 서비스 응답 시간 초과"}',
            status_code=504,
            media_type="application/json",
        )

    # hop-by-hop 헤더 제거
    excluded = {
        "transfer-encoding", "connection", "keep-alive",
        "proxy-authenticate", "proxy-authorization", "te", "trailers", "upgrade",
    }
    response_headers = {
        k: v for k, v in upstream_response.headers.items()
        if k.lower() not in excluded
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
