"""AI Agent Runner Service — FastAPI entry point (FR-D3)."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routers import diagnose, execute

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Agent Runner starting up...")
    yield
    logger.info("AI Agent Runner shutting down.")


app = FastAPI(
    title="AI Agent Runner",
    description="Claude SDK 기반 AI 진단·조치 에이전트 (FR-D3)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(diagnose.router, prefix="", tags=["diagnosis"])
app.include_router(execute.router, prefix="", tags=["execution"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-agent-runner"}
