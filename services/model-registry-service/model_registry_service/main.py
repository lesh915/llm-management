"""Model Registry Service — FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .routers import models, health
from shared_types.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (migrations handle schema in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Model Registry Service",
    description="LLM 모델 메타데이터 등록·관리·호환성 분석 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(models.router, prefix="/models", tags=["models"])
