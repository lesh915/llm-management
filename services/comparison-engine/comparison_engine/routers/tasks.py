"""Comparison task CRUD + run endpoints (FR-C1, FR-C2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import ComparisonTask
from shared_types.schemas import ComparisonTaskCreate
from ..database import get_db
from ..cost import estimate_task_cost

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]

import os
MODEL_REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://localhost:8002")


# ── Task CRUD ─────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(body: ComparisonTaskCreate, db: Db):
    """비교 태스크 생성 (FR-C1)."""
    task = ComparisonTask(
        name=body.name,
        artifact_id=uuid.UUID(body.artifact_id) if body.artifact_id else None,
        model_ids=body.models,
        dataset_id=body.dataset_id,
        metrics=body.metrics,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"data": _ser(task)}


@router.get("")
async def list_tasks(db: Db, status_filter: str | None = None):
    stmt = select(ComparisonTask)
    if status_filter:
        stmt = stmt.where(ComparisonTask.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return {"data": [_ser(r) for r in rows], "meta": {"total": len(rows)}}


@router.get("/{task_id}")
async def get_task(task_id: str, db: Db):
    t = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not t:
        raise HTTPException(404, "Task not found")
    return {"data": _ser(t)}


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, db: Db):
    t = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status == "running":
        raise HTTPException(409, "Cannot delete a running task")
    await db.delete(t)
    await db.commit()


# ── Preflight cost estimate ───────────────────────────────────────────────────

@router.get("/{task_id}/estimate")
async def estimate_cost(task_id: str, db: Db):
    """실행 전 예상 비용 및 가용성 체크."""
    t = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not t:
        raise HTTPException(404, "Task not found")

    pricings: dict[str, dict] = {}
    availability: dict[str, bool] = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for mid in t.model_ids:
            try:
                r = await client.get(f"{MODEL_REGISTRY_URL}/models/{mid}")
                r.raise_for_status()
                meta = r.json()["data"]
                pricings[mid] = meta.get("pricing", {})
                availability[mid] = True
            except Exception:
                pricings[mid] = {}
                availability[mid] = False

    estimates = estimate_task_cost(pricings, dataset_size=10)   # rough 10-case estimate
    total = sum(estimates.values())

    return {
        "data": {
            "task_id": task_id,
            "per_model_cost_usd": estimates,
            "total_estimated_usd": round(total, 6),
            "model_availability": availability,
            "local_models": [
                mid for mid, p in pricings.items()
                if p.get("input_per_1m_tokens", -1) == 0.0
            ],
        }
    }


# ── Task execution ────────────────────────────────────────────────────────────

@router.post("/{task_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_task(task_id: str, db: Db, background_tasks: BackgroundTasks):
    """
    태스크 실행 (FR-C2).
    - 즉시 202 반환 후 Celery 워커에서 비동기 실행
    - WS /ws/tasks/{task_id}/progress 로 실시간 진행 상태 수신 가능
    """
    t = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status == "running":
        raise HTTPException(409, "Task is already running")
    if t.status == "completed":
        raise HTTPException(409, "Task already completed — create a new task to re-run")

    # Dispatch to Celery
    from ..worker import run_comparison_task_celery
    run_comparison_task_celery.delay(task_id)

    t.status = "running"
    await db.commit()

    return {
        "data": {
            "task_id": task_id,
            "status": "running",
            "message": "태스크가 시작되었습니다. WS로 진행 상태를 확인하세요.",
            "ws_url": f"/ws/tasks/{task_id}/progress",
        }
    }


@router.get("/{task_id}/status")
async def task_status(task_id: str, db: Db):
    t = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not t:
        raise HTTPException(404, "Task not found")
    return {
        "data": {
            "task_id": task_id,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
    }


# ── Serializer ────────────────────────────────────────────────────────────────

def _ser(t: ComparisonTask) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "artifact_id": str(t.artifact_id) if t.artifact_id else None,
        "model_ids": t.model_ids,
        "dataset_id": t.dataset_id,
        "metrics": t.metrics,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }
