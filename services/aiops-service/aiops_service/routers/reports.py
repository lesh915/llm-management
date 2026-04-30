"""Operational reports (FR-D5): daily/weekly summaries."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import AIOpsEvent
from ..database import get_db

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]


@router.get("/daily")
async def daily_report(
    db: Db,
    date: str | None = Query(None, description="YYYY-MM-DD, 기본값 오늘"),
):
    """일간 운영 요약 리포트 (FR-D5)."""
    if date:
        day_start = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    metric_summary = await _metric_summary(db, day_start, day_end)
    event_summary  = await _event_summary(db, day_start, day_end)
    action_summary = await _action_summary(db, day_start, day_end)

    return {
        "data": {
            "date": day_start.date().isoformat(),
            "period": {"from": day_start.isoformat(), "to": day_end.isoformat()},
            "metrics": metric_summary,
            "events": event_summary,
            "actions": action_summary,
        }
    }


@router.get("/weekly")
async def weekly_report(db: Db):
    """주간 운영 요약 리포트 (FR-D5)."""
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    metric_summary = await _metric_summary(db, week_start, now)
    event_summary  = await _event_summary(db, week_start, now)
    action_summary = await _action_summary(db, week_start, now)

    # Trend: daily event counts
    trend_sql = """
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM aiops_events
        WHERE created_at >= :start AND created_at < :end
        GROUP BY day ORDER BY day
    """
    trend_rows = (await db.execute(
        text(trend_sql), {"start": week_start, "end": now}
    )).fetchall()

    return {
        "data": {
            "period": {"from": week_start.isoformat(), "to": now.isoformat()},
            "metrics": metric_summary,
            "events": event_summary,
            "actions": action_summary,
            "daily_event_trend": [
                {"date": str(r[0]), "count": r[1]} for r in trend_rows
            ],
        }
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _metric_summary(
    db: AsyncSession, start: datetime, end: datetime
) -> dict:
    sql = """
        SELECT model_id, metric_name,
               AVG(value) AS avg_val,
               MAX(value) AS max_val,
               SUM(value) AS total_val,
               COUNT(*)   AS samples
        FROM ops_metrics
        WHERE time >= :start AND time < :end
        GROUP BY model_id, metric_name
        ORDER BY model_id, metric_name
    """
    rows = (await db.execute(text(sql), {"start": start, "end": end})).fetchall()
    summary: dict[str, list] = {}
    for r in rows:
        summary.setdefault(r[0], []).append({
            "metric": r[1], "avg": round(r[2], 4),
            "max": r[3], "total": round(r[4], 6), "samples": r[5],
        })
    return summary


async def _event_summary(
    db: AsyncSession, start: datetime, end: datetime
) -> dict:
    stmt = (
        select(AIOpsEvent)
        .where(AIOpsEvent.created_at >= start, AIOpsEvent.created_at < end)
    )
    events = (await db.execute(stmt)).scalars().all()

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for ev in events:
        by_type[ev.event_type]   = by_type.get(ev.event_type, 0) + 1
        by_severity[ev.severity] = by_severity.get(ev.severity, 0) + 1
        by_status[ev.status]     = by_status.get(ev.status, 0) + 1

    return {
        "total": len(events),
        "by_type": by_type,
        "by_severity": by_severity,
        "by_status": by_status,
    }


async def _action_summary(
    db: AsyncSession, start: datetime, end: datetime
) -> dict:
    """Count events where actions were taken (approved + executed)."""
    stmt = (
        select(AIOpsEvent)
        .where(
            AIOpsEvent.created_at >= start,
            AIOpsEvent.created_at < end,
            AIOpsEvent.status.in_(["executing", "resolved"]),
        )
    )
    events = (await db.execute(stmt)).scalars().all()

    action_counts: dict[str, int] = {}
    for ev in events:
        for action in (ev.actions or []):
            atype = action.get("action", action.get("type", "unknown"))
            action_counts[atype] = action_counts.get(atype, 0) + 1

    return {
        "total_events_actioned": len(events),
        "action_type_counts": action_counts,
    }
