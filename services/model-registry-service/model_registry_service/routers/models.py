"""Model Registry CRUD + Ollama auto-import endpoints."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import ModelRegistry
from shared_types.schemas import ModelCreate
from ..database import get_db
from ..security import encrypt_api_key
from ..ollama_importer import import_from_ollama

router = APIRouter()

Db = Annotated[AsyncSession, Depends(get_db)]


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def register_model(body: ModelCreate, db: Db):
    """모델 등록 (FR-B1)"""
    existing = await db.get(ModelRegistry, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Model '{body.id}' already exists.")

    api_cfg = body.api.model_dump()
    # Encrypt API key if provided
    if api_cfg.get("api_key"):
        api_cfg["api_key"] = encrypt_api_key(api_cfg["api_key"])

    model = ModelRegistry(
        id=body.id,
        provider=body.provider,
        family=body.family,
        version=body.version,
        capabilities=body.capabilities.model_dump(),
        characteristics=body.characteristics.model_dump(),
        pricing=body.pricing.model_dump(),
        api_config=api_cfg,
        is_custom=body.is_custom,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _serialize(model)


@router.get("")
async def list_models(
    db: Db,
    provider: str | None = Query(None),
    vision: bool | None = Query(None),
    tool_use: bool | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
):
    """모델 목록 조회 (필터 지원)"""
    stmt = select(ModelRegistry)
    if provider:
        stmt = stmt.where(ModelRegistry.provider == provider)
    if status_filter:
        stmt = stmt.where(ModelRegistry.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()

    # JSON 필드 필터 (in-Python for simplicity; use JSONB operators for scale)
    if vision is not None:
        rows = [r for r in rows if r.capabilities.get("vision") == vision]
    if tool_use is not None:
        rows = [r for r in rows if r.capabilities.get("tool_use") == tool_use]

    return {"data": [_serialize(r) for r in rows], "meta": {"total": len(rows)}}


@router.get("/compare")
async def compare_models(
    db: Db,
    model_ids: str = Query(..., description="쉼표로 구분된 모델 ID"),
):
    """모델 특성 비교 매트릭스 (FR-B2)"""
    ids = [m.strip() for m in model_ids.split(",")]
    rows = []
    for mid in ids:
        m = await db.get(ModelRegistry, mid)
        if m:
            rows.append(m)

    if not rows:
        raise HTTPException(status_code=404, detail="No models found.")

    matrix = {
        "models": [r.id for r in rows],
        "capabilities": {
            cap: {r.id: r.capabilities.get(cap) for r in rows}
            for cap in ["context_window", "max_output_tokens", "vision",
                        "tool_use", "structured_output", "parallel_tool_calls",
                        "extended_thinking"]
        },
        "characteristics": {
            ch: {r.id: r.characteristics.get(ch) for r in rows}
            for ch in ["reasoning_depth", "instruction_following",
                       "code_generation", "latency_tier"]
        },
        "pricing": {
            "input_per_1m_tokens": {r.id: r.pricing.get("input_per_1m_tokens") for r in rows},
            "output_per_1m_tokens": {r.id: r.pricing.get("output_per_1m_tokens") for r in rows},
        },
    }
    return {"data": matrix}


@router.get("/{model_id}")
async def get_model(model_id: str, db: Db):
    m = await db.get(ModelRegistry, model_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return {"data": _serialize(m)}


@router.patch("/{model_id}/status")
async def update_model_status(
    model_id: str,
    body: dict,
    db: Db,
):
    """모델 생명주기 상태 변경 (FR-B3): active → deprecated → retired"""
    m = await db.get(ModelRegistry, model_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")

    new_status = body.get("status")
    valid = {"active", "deprecated", "retired"}
    if new_status not in valid:
        raise HTTPException(status_code=422, detail=f"status must be one of {valid}")

    m.status = new_status
    if new_status == "deprecated":
        m.deprecated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"data": _serialize(m)}


# ── Ollama auto-import ────────────────────────────────────────────────────────

@router.post("/import/ollama", status_code=status.HTTP_200_OK)
async def import_ollama_models(body: dict, db: Db):
    """
    Ollama 인스턴스에서 설치된 모델을 자동 탐색하여 레지스트리에 등록 (FR-B4).
    Body: { "base_url": "http://localhost:11434", "auto_register": true }
    """
    base_url = body.get("base_url", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    result = await import_from_ollama(base_url, db)
    return {"data": result}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize(m: ModelRegistry) -> dict:
    cfg = {k: v for k, v in m.api_config.items() if k != "api_key"}  # never expose key
    return {
        "id": m.id,
        "provider": m.provider,
        "family": m.family,
        "version": m.version,
        "capabilities": m.capabilities,
        "characteristics": m.characteristics,
        "pricing": m.pricing,
        "api": cfg,
        "is_custom": m.is_custom,
        "status": m.status,
        "deprecated_at": m.deprecated_at.isoformat() if m.deprecated_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
