"""Result reports, recommendation, and A/B comparison endpoints (FR-C3~C5)."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import ComparisonTask, ComparisonResult
from ..database import get_db
from ..recommender import recommend_model

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]


# ── Result report (FR-C3) ─────────────────────────────────────────────────────

@router.get("/{task_id}/report")
async def get_report(task_id: str, db: Db):
    """
    정량 + 정성 비교 리포트.
    로컬 모델은 비용 0으로 표시되며 is_local 플래그로 구분.
    """
    task = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in ("completed", "running"):
        raise HTTPException(400, f"Task status is '{task.status}'. Run the task first.")

    stmt = select(ComparisonResult).where(ComparisonResult.task_id == uuid.UUID(task_id))
    results = (await db.execute(stmt)).scalars().all()

    if not results:
        return {"data": {"task_id": task_id, "status": task.status, "results": []}}

    result_dicts = [_ser_result(r) for r in results]

    # Per-metric leaderboard
    all_metrics = set()
    for r in result_dicts:
        all_metrics.update(r["metrics"].keys())

    leaderboard: dict[str, list] = {}
    for metric in sorted(all_metrics):
        sorted_models = sorted(
            result_dicts,
            key=lambda x: x["metrics"].get(metric, 0),
            reverse=metric not in ("cost_per_query", "latency_p95", "latency_p50", "failure_rate"),
        )
        leaderboard[metric] = [
            {"rank": i + 1, "model_id": r["model_id"],
             "value": r["metrics"].get(metric),
             "is_local": r.get("is_local", False)}
            for i, r in enumerate(sorted_models)
        ]

    return {
        "data": {
            "task_id": task_id,
            "task_name": task.name,
            "status": task.status,
            "model_count": len(result_dicts),
            "results": result_dicts,
            "leaderboard": leaderboard,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
    }


# ── Recommendation (FR-C4) ────────────────────────────────────────────────────

@router.get("/{task_id}/recommendation")
async def get_recommendation(
    task_id: str,
    db: Db,
    priority: str = Query(default="balanced", pattern="^(cost|performance|balanced)$"),
):
    """
    우선순위(cost / performance / balanced)에 따른 최적 모델 추천.
    자연어 근거 포함.
    """
    task = await db.get(ComparisonTask, uuid.UUID(task_id))
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != "completed":
        raise HTTPException(400, "Task must be completed before generating a recommendation.")

    stmt = select(ComparisonResult).where(ComparisonResult.task_id == uuid.UUID(task_id))
    results = (await db.execute(stmt)).scalars().all()
    if not results:
        raise HTTPException(404, "No results found for this task.")

    result_dicts = [_ser_result(r) for r in results]

    try:
        recommendation = recommend_model(result_dicts, priority=priority)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"data": recommendation}


# ── A/B comparison (FR-C5) ────────────────────────────────────────────────────

@router.get("/{task_id}/ab")
async def ab_comparison(
    task_id: str,
    db: Db,
    model_a: str = Query(..., description="첫 번째 모델 ID"),
    model_b: str = Query(..., description="두 번째 모델 ID"),
):
    """
    두 모델의 지표를 나란히(side-by-side) 비교.
    차이(delta)와 승자를 함께 반환.
    """
    stmt = select(ComparisonResult).where(
        ComparisonResult.task_id == uuid.UUID(task_id),
        ComparisonResult.model_id.in_([model_a, model_b]),
    )
    rows = (await db.execute(stmt)).scalars().all()
    by_model = {r.model_id: r for r in rows}

    if model_a not in by_model:
        raise HTTPException(404, f"No result for model '{model_a}' in this task.")
    if model_b not in by_model:
        raise HTTPException(404, f"No result for model '{model_b}' in this task.")

    ra, rb = by_model[model_a], by_model[model_b]
    ma, mb = ra.metrics, rb.metrics

    all_metrics = set(ma.keys()) | set(mb.keys())
    comparison: list[dict] = []
    _lower_better = {"cost_per_query", "latency_p95", "latency_p50", "failure_rate"}

    for metric in sorted(all_metrics):
        va = ma.get(metric)
        vb = mb.get(metric)
        delta = None
        winner = None
        if va is not None and vb is not None:
            delta = round(vb - va, 6)
            lower_better = metric in _lower_better
            if va < vb:
                winner = model_a if lower_better else model_b
            elif vb < va:
                winner = model_b if lower_better else model_a
            else:
                winner = "tie"
        comparison.append({
            "metric": metric,
            model_a: va,
            model_b: vb,
            "delta_b_minus_a": delta,
            "winner": winner,
        })

    return {
        "data": {
            "task_id": task_id,
            "model_a": model_a,
            "model_b": model_b,
            "comparison": comparison,
            "cost_a_usd": float(ra.cost_usd or 0),
            "cost_b_usd": float(rb.cost_usd or 0),
        }
    }


# ── Serializer ────────────────────────────────────────────────────────────────

def _ser_result(r: ComparisonResult) -> dict:
    return {
        "model_id": r.model_id,
        "metrics": r.metrics or {},
        "cost_usd": float(r.cost_usd or 0),
        "is_local": float(r.cost_usd or 0) == 0.0,  # local = zero cost
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
