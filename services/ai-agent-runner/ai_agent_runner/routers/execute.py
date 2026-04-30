"""조치 실행 엔드포인트 (FR-D3 step 4)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..executor import execute_action

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/execute")
async def trigger_execute(body: dict):
    """
    승인된 조치를 실행합니다 (aiops-service에서 호출).
    body: { "event_id": str, "action_index": int }
    """
    event_id = body.get("event_id")
    action_index = body.get("action_index", 0)

    if not event_id:
        raise HTTPException(422, "event_id is required")

    if not isinstance(action_index, int) or action_index < 0:
        raise HTTPException(422, "action_index must be a non-negative integer")

    logger.info("조치 실행 요청: event=%s, action_index=%d", event_id, action_index)

    result = await execute_action(event_id=event_id, action_index=action_index)

    if not result.get("success"):
        raise HTTPException(500, result.get("error", "조치 실행 실패"))

    return {"data": result}
