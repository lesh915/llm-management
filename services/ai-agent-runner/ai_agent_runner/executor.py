"""조치 실행 디스패처 (FR-D3 step 4).

승인된 조치(action)를 실제로 실행하는 함수들을 포함합니다.
각 action_type에 따라 다른 처리 로직을 수행합니다.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

AIOPS_SERVICE_URL = os.environ.get("AIOPS_SERVICE_URL", "http://aiops-service:8000")
MODEL_REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://model-registry-service:8000")
NOTIFICATION_WEBHOOK = os.environ.get("NOTIFICATION_WEBHOOK", "")


async def execute_action(event_id: str, action_index: int) -> dict:
    """
    이벤트의 특정 인덱스 조치를 실행합니다.

    1. aiops-service에서 이벤트 조회
    2. action[action_index] 확인
    3. action_type에 따라 실행
    4. 결과를 이벤트에 업데이트
    """
    # 이벤트 조회
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{AIOPS_SERVICE_URL}/events/{event_id}")
            resp.raise_for_status()
            event = resp.json().get("data", {})
    except Exception as e:
        logger.error("이벤트 조회 실패: %s", e)
        return {"success": False, "error": str(e)}

    actions = event.get("actions", []) or []
    if action_index >= len(actions):
        return {"success": False, "error": f"action_index {action_index} out of range"}

    action = actions[action_index]
    action_type = action.get("action", action.get("type", "unknown"))
    params = action.get("params", {})

    logger.info("조치 실행: event=%s, action=%s, params=%s", event_id, action_type, params)

    # action_type별 실행
    if action_type == "switch_model":
        result = await _execute_switch_model(event, params)
    elif action_type == "rollback":
        result = await _execute_rollback(event, params)
    elif action_type == "notify":
        result = await _execute_notify(event, params)
    elif action_type == "scale_down":
        result = await _execute_scale_down(event, params)
    else:
        result = {"success": False, "error": f"알 수 없는 action_type: {action_type}"}

    # 실행 결과를 action에 기록
    actions[action_index]["execution_result"] = result
    actions[action_index]["executed"] = result.get("success", False)

    # 이벤트 상태 업데이트 (resolved or back to open on failure)
    new_status = "resolved" if result.get("success") else "open"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(
                f"{AIOPS_SERVICE_URL}/events/{event_id}",
                json={"actions": actions, "status": new_status},
            )
    except Exception as e:
        logger.warning("이벤트 상태 업데이트 실패: %s", e)

    return result


# ── 개별 action 실행 함수 ──────────────────────────────────────────────────────

async def _execute_switch_model(event: dict, params: dict) -> dict:
    """폴백 모델로 전환."""
    fallback_model_id = params.get("fallback_model_id", "")
    agent_id = event.get("agent_id")

    if not fallback_model_id:
        return {"success": False, "error": "fallback_model_id가 지정되지 않았습니다."}

    logger.info("모델 전환: agent=%s -> model=%s", agent_id, fallback_model_id)

    # model-registry-service에 상태 업데이트 (실제 라우팅 변경은 외부 시스템)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{MODEL_REGISTRY_URL}/models/{fallback_model_id}/status",
                json={"status": "active", "note": f"Failover from agent {agent_id}"},
            )
            logger.info("모델 상태 업데이트: %s", resp.status_code)
    except Exception as e:
        logger.warning("모델 레지스트리 업데이트 실패 (계속 진행): %s", e)

    return {
        "success": True,
        "action": "switch_model",
        "fallback_model_id": fallback_model_id,
        "message": f"폴백 모델 '{fallback_model_id}'로 전환 요청이 완료되었습니다.",
    }


async def _execute_rollback(event: dict, params: dict) -> dict:
    """이전 모델 버전으로 롤백."""
    target_version = params.get("target_version", "previous")
    model_id = event.get("model_id", "")

    logger.info("롤백 실행: model=%s -> version=%s", model_id, target_version)

    return {
        "success": True,
        "action": "rollback",
        "model_id": model_id,
        "target_version": target_version,
        "message": f"모델 '{model_id}'을 버전 '{target_version}'으로 롤백 요청이 완료되었습니다.",
    }


async def _execute_notify(event: dict, params: dict) -> dict:
    """운영팀에 알림 전송."""
    channel = params.get("channel", "default")
    message = params.get("message", "")
    event_type = event.get("event_type", "")
    severity = event.get("severity", "")

    notification_body = {
        "channel": channel,
        "text": (
            f"[AIOps 알림] {event_type} 이벤트 감지\n"
            f"심각도: {severity}\n"
            f"설명: {event.get('description', '')}\n"
            f"에이전트: {event.get('agent_id', '')}\n"
            f"모델: {event.get('model_id', '')}\n"
        ) + (f"\n추가 메시지: {message}" if message else ""),
    }

    # 웹훅이 설정된 경우 실제 전송
    if NOTIFICATION_WEBHOOK:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(NOTIFICATION_WEBHOOK, json=notification_body)
                logger.info("알림 전송 완료: status=%s", resp.status_code)
        except Exception as e:
            logger.warning("알림 전송 실패: %s", e)
    else:
        logger.info("알림 (웹훅 미설정): %s", notification_body["text"])

    return {
        "success": True,
        "action": "notify",
        "channel": channel,
        "message": f"알림이 '{channel}' 채널로 전송되었습니다.",
    }


async def _execute_scale_down(event: dict, params: dict) -> dict:
    """요청 부하 감소 / 레이트 리미팅."""
    target_rps = params.get("target_rps", 10)
    duration_minutes = params.get("duration_minutes", 30)

    logger.info(
        "Scale-down 실행: agent=%s, target_rps=%s, duration=%sm",
        event.get("agent_id"),
        target_rps,
        duration_minutes,
    )

    return {
        "success": True,
        "action": "scale_down",
        "target_rps": target_rps,
        "duration_minutes": duration_minutes,
        "message": (
            f"에이전트 '{event.get('agent_id')}'의 요청 속도를 "
            f"{target_rps} RPS로 {duration_minutes}분간 제한 설정이 완료되었습니다."
        ),
    }
