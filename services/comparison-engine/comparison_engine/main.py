"""Comparison Engine — FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .routers import tasks, reports, ws
from shared_types.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Comparison Engine",
    description="다모델 비교 분석: 병렬 실행, 지표 계산, 리포트, 권장 모델 제안",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router,   prefix="/tasks",   tags=["tasks"])
app.include_router(reports.router, prefix="/tasks",   tags=["reports"])
app.include_router(ws.router,                         tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "comparison-engine"}
