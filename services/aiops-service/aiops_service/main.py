"""AIOps Service — FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .routers import metrics, events, rules, reports
from shared_types.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="AIOps Service",
    description="운영 지표 수집, 이상 탐지, 규칙 엔진, AI 에이전트 협업, 운영 리포트",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(events.router,  prefix="/events",  tags=["events"])
app.include_router(rules.router,   prefix="/rules",   tags=["rules"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aiops-service"}
