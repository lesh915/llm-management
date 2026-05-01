"""API Gateway — LLM Management Platform 통합 진입점."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import (
    ARTIFACT_SERVICE_URL,
    MODEL_REGISTRY_URL,
    COMPARISON_ENGINE_URL,
    AIOPS_SERVICE_URL,
    AI_AGENT_RUNNER_URL,
    PROXY_TIMEOUT,
)
from .routers import artifacts, models, comparison, aiops, auth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API Gateway starting up...")
    yield
    logger.info("API Gateway shutting down.")


app = FastAPI(
    title="LLM Management Platform — API Gateway",
    description="모든 마이크로서비스로의 단일 진입점. 인증, 라우팅, 관찰가능성 제공.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 요청 추적 미들웨어 ──────────────────────────────────────────────────────────
@app.middleware("http")
async def request_tracing(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()

    response: Response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{elapsed_ms:.1f}"

    logger.info(
        "%s %s %d %.1fms [%s]",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


# ── 라우터 등록 ────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(artifacts.router,  tags=["agents & artifacts"])
app.include_router(models.router,     tags=["model registry"])
app.include_router(comparison.router, tags=["comparison engine"])
app.include_router(aiops.router,      tags=["aiops"])


# ── 헬스 체크 ──────────────────────────────────────────────────────────────────

_UPSTREAM_SERVICES = {
    "artifact-service":        ARTIFACT_SERVICE_URL,
    "model-registry-service":  MODEL_REGISTRY_URL,
    "comparison-engine":       COMPARISON_ENGINE_URL,
    "aiops-service":           AIOPS_SERVICE_URL,
    "ai-agent-runner":         AI_AGENT_RUNNER_URL,
}


@app.get("/health", tags=["gateway"])
async def health():
    """게이트웨이 자체 상태만 반환 (빠른 liveness probe)."""
    return {"status": "ok", "service": "api-gateway"}


@app.get("/health/upstream", tags=["gateway"])
async def health_upstream():
    """모든 업스트림 서비스의 헬스 상태를 집계하여 반환."""
    results: dict[str, dict] = {}

    async def _check(name: str, base_url: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/health")
                results[name] = {
                    "status": "ok" if resp.status_code == 200 else "degraded",
                    "http_status": resp.status_code,
                }
        except Exception as e:
            results[name] = {"status": "unreachable", "error": str(e)}

    import asyncio
    await asyncio.gather(*[
        _check(name, url) for name, url in _UPSTREAM_SERVICES.items()
    ])

    overall = "ok" if all(v["status"] == "ok" for v in results.values()) else "degraded"
    return JSONResponse(
        content={"status": overall, "services": results},
        status_code=200 if overall == "ok" else 207,
    )
