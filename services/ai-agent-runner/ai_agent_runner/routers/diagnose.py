"""진단 트리거 엔드포인트 (FR-D3 step 1-2)."""
from __future__ import annotations

import logging
import os
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..diagnosis_agent import run_diagnosis

router = APIRouter()
logger = logging.getLogger(__name__)

AIOPS_SERVICE_URL = os.environ.get("AIOPS_SERVICE_URL", "http://aiops-service:8000")


@router.post("/diagnose")
async def trigger_diagnose(body: dict, background_tasks: BackgroundTasks):
    """
    AI 에이전트 진단 시작 (aiops-service에서 호출).
    body: { "event_id": str }
    """
    event_id = body.get("event_id")
    if not event_id:
        raise HTTPException(422, "event_id is required")

    # 이벤트 정보 조회
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{AIOPS_SERVICE_URL}/events/{event_id}")
            resp.raise_for_status()
            event = resp.json().get("data", {})
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(404, f"Event {event_id} not found")
        raise HTTPException(502, f"aiops-service 통신 오류: {e}")
    except Exception as e:
        raise HTTPException(502, f"aiops-service 통신 오류: {e}")

    # 백그라운드에서 진단 실행
    background_tasks.add_task(
        _run_diagnosis_background,
        event_id=event_id,
        event_type=event.get("event_type", "unknown"),
        severity=event.get("severity", "medium"),
        description=event.get("description", ""),
        agent_id=str(event.get("agent_id", "")),
        model_id=event.get("model_id", ""),
    )

    return {
        "data": {
            "event_id": event_id,
            "status": "diagnosing",
            "message": "백그라운드에서 AI 진단을 시작했습니다.",
        }
    }


async def _run_diagnosis_background(
    event_id: str,
    event_type: str,
    severity: str,
    description: str,
    agent_id: str,
    model_id: str,
):
    """백그라운드에서 진단 실행 후 결과를 aiops-service에 저장."""
    logger.info("AI 진단 시작: event=%s, type=%s", event_id, event_type)
    try:
        result = await run_diagnosis(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            description=description,
            agent_id=agent_id,
            model_id=model_id,
        )
        logger.info(
            "AI 진단 완료: event=%s, tool_calls=%d, actions=%d",
            event_id,
            result["tool_calls"],
            result["actions_proposed"],
        )

        # 진단 결과를 이벤트 description에 추가 (간단한 방법)
        # 실제 운영에서는 별도 diagnosis 필드나 comment 시스템 활용 권장
        if result["actions_proposed"] == 0:
            # 제안된 조치가 없으면 이벤트 상태를 open으로 복귀
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{AIOPS_SERVICE_URL}/events/{event_id}",
                    json={"status": "open"},
                )

    except Exception as e:
        logger.error("AI 진단 실패: event=%s, error=%s", event_id, e)
        # 실패 시 이벤트 상태를 open으로 복귀
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.patch(
                    f"{AIOPS_SERVICE_URL}/events/{event_id}",
                    json={"status": "open"},
                )
        except Exception:
            pass
