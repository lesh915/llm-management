"""AIOps 진단 도구 실행 함수 — Anthropic / LangGraph 에이전트 공통 사용."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

AIOPS_SERVICE_URL = os.environ.get("AIOPS_SERVICE_URL", "http://aiops-service:8000")

# ── Tool 스키마 정의 (Anthropic SDK용) ────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "query_metrics",
        "description": (
            "Query recent operational metrics for an agent/model. "
            "Returns time-series data for error_rate, latency_p95, cost, tool_call_failure_rate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "UUID of the agent to query"},
                "model_id": {"type": "string", "description": "Model ID to filter metrics (optional)"},
                "metric": {
                    "type": "string",
                    "description": "Specific metric name to query (optional)",
                    "enum": ["error_rate", "latency_p95", "cost", "tool_call_failure_rate"],
                },
                "limit": {"type": "integer", "description": "Number of data points (default 50)", "default": 50},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "get_recent_events",
        "description": "Get recent AIOps events for an agent to understand the incident history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "UUID of the agent"},
                "limit": {"type": "integer", "description": "Number of recent events (default 10)", "default": 10},
                "status": {
                    "type": "string",
                    "description": "Filter by event status (optional)",
                    "enum": ["open", "diagnosing", "pending_approval", "executing", "resolved"],
                },
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "propose_action",
        "description": (
            "Propose a remediation action for the current AIOps event. "
            "Added to the event's action list for human approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["switch_model", "rollback", "notify", "scale_down"],
                },
                "params": {"type": "object", "description": "Action-specific parameters"},
                "reason": {"type": "string", "description": "Brief explanation (Korean)"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["action_type", "params", "reason", "confidence"],
        },
    },
]

# ── 공통 실행 함수 ─────────────────────────────────────────────────────────────

async def execute_query_metrics(args: dict) -> str:
    """aiops-service에서 메트릭 조회."""
    agent_id = args["agent_id"]
    params: dict[str, Any] = {"limit": args.get("limit", 50)}
    if args.get("model_id"):
        params["model_id"] = args["model_id"]
    if args.get("metric"):
        params["metric"] = args["metric"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{AIOPS_SERVICE_URL}/metrics/{agent_id}", params=params)
            resp.raise_for_status()
            rows = resp.json().get("data", [])
        if not rows:
            return "해당 에이전트의 메트릭 데이터가 없습니다."
        lines = [
            f"[{r.get('time', 'N/A')}] {r.get('metric_name')}: {r.get('value')}"
            for r in rows[:20]
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning("query_metrics 실패: %s", e)
        return f"메트릭 조회 실패: {e}"


async def execute_get_recent_events(args: dict) -> str:
    """aiops-service에서 최근 이벤트 조회."""
    params: dict[str, Any] = {
        "agent_id": args["agent_id"],
        "limit": args.get("limit", 10),
    }
    if args.get("status"):
        params["status"] = args["status"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{AIOPS_SERVICE_URL}/events", params=params)
            resp.raise_for_status()
            events = resp.json().get("data", [])
        if not events:
            return "최근 이벤트가 없습니다."
        lines = [
            f"[{ev.get('created_at', 'N/A')}] "
            f"{ev.get('event_type')} | severity={ev.get('severity')} | "
            f"status={ev.get('status')} | {ev.get('description', '')}"
            for ev in events
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning("get_recent_events 실패: %s", e)
        return f"이벤트 조회 실패: {e}"


async def execute_propose_action(args: dict, event_id: str) -> str:
    """aiops-service에 조치 제안 추가."""
    action = {
        "action": args["action_type"],
        "params": args.get("params", {}),
        "reason": args.get("reason", ""),
        "confidence": args.get("confidence", "medium"),
        "proposed_by": "ai-agent",
        "requires_approval": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            get_resp = await client.get(f"{AIOPS_SERVICE_URL}/events/{event_id}")
            get_resp.raise_for_status()
            ev = get_resp.json().get("data", {})
            current_actions = list(ev.get("actions") or [])
            current_actions.append(action)

            patch_resp = await client.patch(
                f"{AIOPS_SERVICE_URL}/events/{event_id}",
                json={"actions": current_actions, "status": "pending_approval"},
            )
            logger.info("propose_action patch: %s", patch_resp.status_code)

        return (
            f"조치 제안 완료: {args['action_type']} "
            f"(신뢰도: {args.get('confidence')}) - {args.get('reason')}"
        )
    except Exception as e:
        logger.warning("propose_action 실패: %s", e)
        return f"조치 제안 저장 실패: {e}"


async def dispatch_tool(tool_name: str, tool_input: dict, event_id: str) -> str:
    """tool_name에 따라 실행 함수 라우팅."""
    if tool_name == "query_metrics":
        return await execute_query_metrics(tool_input)
    elif tool_name == "get_recent_events":
        return await execute_get_recent_events(tool_input)
    elif tool_name == "propose_action":
        return await execute_propose_action(tool_input, event_id)
    return f"알 수 없는 도구: {tool_name}"
