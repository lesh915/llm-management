"""Ops metrics ingestion and query endpoints (FR-D1)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import OpsMetric
from ..database import get_db
from ..detectors.anomaly_detector import AnomalyDetector
from shared_types.models import AIOpsEvent

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]
_detector = AnomalyDetector()


@router.post("", status_code=201)
async def ingest_metrics(body: dict, db: Db):
    """
    운영 지표 수집 (FR-D1).
    Body: { agent_id, model_id, metrics: [{name, value}], timestamp? }
    수집 즉시 이상 탐지 실행 → 이상 감지 시 AIOpsEvent 자동 생성.
    """
    agent_id = body["agent_id"]
    model_id = body["model_id"]
    ts = datetime.fromisoformat(body["timestamp"]) if body.get("timestamp") \
        else datetime.now(timezone.utc)

    for m in body.get("metrics", []):
        db.add(OpsMetric(
            time=ts,
            agent_id=uuid.UUID(agent_id),
            model_id=model_id,
            metric_name=m["name"],
            value=float(m["value"]),
        ))
    await db.commit()

    # Run anomaly detection after every ingest
    new_events = await _detector.check_all(agent_id, model_id, db)
    created_events = []
    for ev in new_events:
        aiops_event = AIOpsEvent(
            agent_id=uuid.UUID(ev.agent_id),
            model_id=ev.model_id,
            event_type=ev.event_type,
            severity=ev.severity,
            description=ev.description,
            status="open",
        )
        db.add(aiops_event)
        created_events.append(ev.event_type)
    if new_events:
        await db.commit()

    return {
        "data": {
            "ingested": len(body.get("metrics", [])),
            "anomalies_detected": len(new_events),
            "events_created": created_events,
        }
    }


@router.get("/{agent_id}")
async def query_metrics(
    agent_id: str,
    db: Db,
    model_id: str | None = Query(None),
    metric: str | None = Query(None),
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
    limit: int = Query(default=200, le=1000),
):
    """운영 지표 조회 (시간 범위 + 지표명 필터)."""
    where = ["agent_id = :agent_id"]
    params: dict = {"agent_id": agent_id}

    if model_id:
        where.append("model_id = :model_id")
        params["model_id"] = model_id
    if metric:
        where.append("metric_name = :metric")
        params["metric"] = metric
    if from_ts:
        where.append("time >= :from_ts")
        params["from_ts"] = from_ts
    if to_ts:
        where.append("time <= :to_ts")
        params["to_ts"] = to_ts

    sql = f"""
        SELECT time, model_id, metric_name, value
        FROM ops_metrics
        WHERE {' AND '.join(where)}
        ORDER BY time DESC
        LIMIT :limit
    """
    params["limit"] = limit
    rows = (await db.execute(text(sql), params)).fetchall()

    return {
        "data": [
            {"time": r[0].isoformat(), "model_id": r[1],
             "metric_name": r[2], "value": r[3]}
            for r in rows
        ],
        "meta": {"count": len(rows)},
    }


@router.get("/{agent_id}/summary")
async def metrics_summary(agent_id: str, model_id: str, db: Db):
    """최근 1시간 지표 요약 (평균·최댓값·최솟값)."""
    sql = """
        SELECT metric_name,
               AVG(value)  AS avg_val,
               MAX(value)  AS max_val,
               MIN(value)  AS min_val,
               COUNT(*)    AS samples
        FROM ops_metrics
        WHERE agent_id  = :agent_id
          AND model_id  = :model_id
          AND time >= NOW() - INTERVAL '1 hour'
        GROUP BY metric_name
    """
    rows = (await db.execute(
        text(sql), {"agent_id": agent_id, "model_id": model_id}
    )).fetchall()

    return {
        "data": [
            {"metric": r[0], "avg": round(r[1], 4),
             "max": r[2], "min": r[3], "samples": r[4]}
            for r in rows
        ]
    }
