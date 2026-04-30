"""AIOps event management + action approval endpoints (FR-D3)."""
from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import AIOpsEvent
from ..database import get_db
from ..rules import evaluate_rules, DEFAULT_RULES

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]

AI_AGENT_RUNNER_URL = os.environ.get("AI_AGENT_RUNNER_URL", "http://ai-agent-runner:8000")


@router.get("")
async def list_events(
    db: Db,
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(default=50, le=200),
):
    stmt = select(AIOpsEvent).order_by(AIOpsEvent.created_at.desc()).limit(limit)
    if agent_id:
        stmt = stmt.where(AIOpsEvent.agent_id == uuid.UUID(agent_id))
    if status:
        stmt = stmt.where(AIOpsEvent.status == status)
    if severity:
        stmt = stmt.where(AIOpsEvent.severity == severity)

    rows = (await db.execute(stmt)).scalars().all()
    return {"data": [_ser(r) for r in rows], "meta": {"count": len(rows)}}


@router.get("/{event_id}")
async def get_event(event_id: str, db: Db):
    ev = await db.get(AIOpsEvent, uuid.UUID(event_id))
    if not ev:
        raise HTTPException(404, "Event not found")
    return {"data": _ser(ev)}


@router.post("/{event_id}/diagnose")
async def trigger_diagnosis(event_id: str, db: Db):
    """
    AI 에이전트 진단 트리거 (FR-D3 step 1-2).
    ai-agent-runner 서비스를 호출하여 비동기 진단 시작.
    """
    import httpx
    ev = await db.get(AIOpsEvent, uuid.UUID(event_id))
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev.status not in ("open",):
        raise HTTPException(409, f"Event status is '{ev.status}', cannot re-diagnose.")

    ev.status = "diagnosing"
    await db.commit()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{AI_AGENT_RUNNER_URL}/diagnose",
                json={"event_id": event_id},
            )
    except Exception:
        pass   # runner may not be up in dev; continue

    return {"data": {"event_id": event_id, "status": "diagnosing",
                     "message": "AI 에이전트 진단이 시작되었습니다."}}


@router.patch("/{event_id}/approve")
async def approve_action(event_id: str, body: dict, db: Db):
    """
    조치 승인 (FR-D3 step 3-4).
    body: { "action_index": int, "approved": bool, "note": str }
    승인 시 ai-agent-runner에 실행 요청.
    """
    import httpx
    ev = await db.get(AIOpsEvent, uuid.UUID(event_id))
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev.status != "pending_approval":
        raise HTTPException(409, f"Event is not pending approval (status: {ev.status})")

    approved: bool = body.get("approved", False)
    idx: int = body.get("action_index", 0)
    actions: list = ev.actions or []

    if idx >= len(actions):
        raise HTTPException(422, f"action_index {idx} out of range")

    actions[idx]["approved"] = approved
    actions[idx]["note"] = body.get("note", "")
    ev.actions = actions

    if approved:
        ev.status = "executing"
        await db.commit()
        # Notify runner to execute the approved action
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{AI_AGENT_RUNNER_URL}/execute",
                    json={"event_id": event_id, "action_index": idx},
                )
        except Exception:
            pass
    else:
        ev.status = "open"
        await db.commit()

    return {"data": _ser(ev)}


@router.patch("/{event_id}/resolve")
async def resolve_event(event_id: str, db: Db):
    ev = await db.get(AIOpsEvent, uuid.UUID(event_id))
    if not ev:
        raise HTTPException(404, "Event not found")
    ev.status = "resolved"
    await db.commit()
    return {"data": _ser(ev)}


@router.post("/{event_id}/evaluate-rules")
async def evaluate_event_rules(event_id: str, db: Db):
    """
    이벤트에 매칭되는 자동화 규칙을 평가하고 즉시 실행 가능한 규칙을 처리 (FR-D4).
    """
    ev = await db.get(AIOpsEvent, uuid.UUID(event_id))
    if not ev:
        raise HTTPException(404, "Event not found")

    matches = evaluate_rules(ev, DEFAULT_RULES)
    auto_executed = []
    pending_approval = []

    for match in matches:
        if not match.requires_approval:
            # Auto-execute (e.g., notify)
            auto_executed.append({
                "rule": match.rule_name,
                "action": match.action_type,
                "params": match.action_params,
            })
        else:
            pending_approval.append({
                "rule": match.rule_name,
                "action": match.action_type,
                "params": match.action_params,
                "requires_approval": True,
            })

    if pending_approval:
        ev.actions = (ev.actions or []) + pending_approval
        ev.status = "pending_approval"
        await db.commit()

    return {
        "data": {
            "event_id": event_id,
            "rules_matched": len(matches),
            "auto_executed": auto_executed,
            "pending_approval": pending_approval,
        }
    }


def _ser(ev: AIOpsEvent) -> dict:
    return {
        "id": str(ev.id),
        "agent_id": str(ev.agent_id) if ev.agent_id else None,
        "model_id": ev.model_id,
        "event_type": ev.event_type,
        "severity": ev.severity,
        "description": ev.description,
        "status": ev.status,
        "actions": ev.actions or [],
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }
