from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .routers.artifacts import router as artifacts_router
from shared_types.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Artifact Service",
    description="에이전트 아티팩트 등록·분석·버전 관리 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(artifacts_router, tags=["artifacts"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "artifact-service"}
