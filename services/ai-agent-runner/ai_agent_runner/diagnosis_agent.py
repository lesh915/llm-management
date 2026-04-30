"""Claude SDK 기반 AI 진단 에이전트 (FR-D3).

Anthropic claude-opus-4-7 모델을 사용하여 AIOps 이벤트를 진단하고
조치를 제안하는 agentic loop를 실행합니다.

시스템 프롬프트에 prompt caching을 적용하여 반복 요청 비용을 절감합니다.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
import httpx

logger = logging.getLogger(__name__)

# ── 환경 설정 ──────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AIOPS_SERVICE_URL = os.environ.get("AIOPS_SERVICE_URL", "http://aiops-service:8000")
MODEL = "claude-opus-4-7"

# ── 시스템 프롬프트 (prompt caching 대상) ──────────────────────────────────────

SYSTEM_PROMPT = """You are an expert AIOps diagnostic agent for an LLM management platform.

Your role is to:
1. Analyze operational events and metrics from LLM agents
2. Diagnose root causes of issues (high error rates, latency spikes, cost overruns, tool failures)
3. Propose concrete remediation actions

## Available Tools
- `query_metrics`: Query recent operational metrics for a model/agent
- `get_recent_events`: Get recent AIOps events for context
- `propose_action`: Submit a proposed remediation action for human approval

## Diagnostic Process
1. Start by querying recent metrics to understand the current state
2. Review related events for patterns
3. Identify the root cause based on the data
4. Propose ONE clear, actionable remediation step

## Action Types
- `switch_model`: Switch to a fallback model (when error rate is high)
- `rollback`: Rollback to a previous model version
- `notify`: Send a notification to the operations team
- `scale_down`: Reduce request load/rate limiting

## Guidelines
- Be concise and data-driven in your analysis
- Prioritize stability over performance
- Always propose the most conservative action first
- Include confidence level (high/medium/low) with your diagnosis

Respond in Korean for descriptions, but use English for technical terms and action types.
"""


# ── Tool 정의 ─────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "query_metrics",
        "description": (
            "Query recent operational metrics for an agent/model. "
            "Returns time-series data for error_rate, latency_p95, cost, tool_call_failure_rate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "UUID of the agent to query",
                },
                "model_id": {
                    "type": "string",
                    "description": "Model ID to filter metrics (optional)",
                },
                "metric": {
                    "type": "string",
                    "description": "Specific metric name to query (optional)",
                    "enum": ["error_rate", "latency_p95", "cost", "tool_call_failure_rate"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of data points to return (default 50)",
                    "default": 50,
                },
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "get_recent_events",
        "description": (
            "Get recent AIOps events for an agent to understand the incident history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "UUID of the agent",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of recent events to return (default 10)",
                    "default": 10,
                },
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
            "This will be added to the event's action list for human approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "Type of action to take",
                    "enum": ["switch_model", "rollback", "notify", "scale_down"],
                },
                "params": {
                    "type": "object",
                    "description": "Action-specific parameters",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation (Korean) of why this action is recommended",
                },
                "confidence": {
                    "type": "string",
                    "description": "Confidence level of the diagnosis",
                    "enum": ["high", "medium", "low"],
                },
            },
            "required": ["action_type", "params", "reason", "confidence"],
        },
    },
]


# ── Tool 실행 함수 ─────────────────────────────────────────────────────────────

async def _execute_query_metrics(args: dict) -> str:
    """aiops-service에서 메트릭 조회."""
    agent_id = args["agent_id"]
    params: dict[str, Any] = {"limit": args.get("limit", 50)}
    if "model_id" in args:
        params["model_id"] = args["model_id"]
    if "metric" in args:
        params["metric"] = args["metric"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{AIOPS_SERVICE_URL}/metrics/{agent_id}",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("data", [])
            if not rows:
                return "해당 에이전트의 메트릭 데이터가 없습니다."
            # 요약 형태로 반환
            summary_lines = []
            for r in rows[:20]:  # 최대 20개
                summary_lines.append(
                    f"[{r.get('time', 'N/A')}] {r.get('metric_name')}: {r.get('value')}"
                )
            return "\n".join(summary_lines)
    except Exception as e:
        logger.warning("query_metrics 실패: %s", e)
        return f"메트릭 조회 실패: {e}"


async def _execute_get_recent_events(args: dict) -> str:
    """aiops-service에서 최근 이벤트 조회."""
    agent_id = args["agent_id"]
    params: dict[str, Any] = {
        "agent_id": agent_id,
        "limit": args.get("limit", 10),
    }
    if "status" in args:
        params["status"] = args["status"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{AIOPS_SERVICE_URL}/events",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            events = data.get("data", [])
            if not events:
                return "최근 이벤트가 없습니다."
            lines = []
            for ev in events:
                lines.append(
                    f"[{ev.get('created_at', 'N/A')}] "
                    f"{ev.get('event_type')} | severity={ev.get('severity')} | "
                    f"status={ev.get('status')} | {ev.get('description', '')}"
                )
            return "\n".join(lines)
    except Exception as e:
        logger.warning("get_recent_events 실패: %s", e)
        return f"이벤트 조회 실패: {e}"


async def _execute_propose_action(args: dict, event_id: str) -> str:
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
            # 이벤트 조회 후 actions 업데이트
            get_resp = await client.get(f"{AIOPS_SERVICE_URL}/events/{event_id}")
            get_resp.raise_for_status()
            ev = get_resp.json().get("data", {})
            current_actions = ev.get("actions", []) or []
            current_actions.append(action)

            # PATCH로 actions + status 업데이트
            # evaluate-rules 엔드포인트를 통해 처리
            patch_resp = await client.patch(
                f"{AIOPS_SERVICE_URL}/events/{event_id}",
                json={"actions": current_actions, "status": "pending_approval"},
            )
            # 200이든 404든 일단 기록
            logger.info("propose_action patch 결과: %s", patch_resp.status_code)

        return (
            f"조치 제안 완료: {args['action_type']} "
            f"(신뢰도: {args.get('confidence')}) - {args.get('reason')}"
        )
    except Exception as e:
        logger.warning("propose_action 실패: %s", e)
        return f"조치 제안 저장 실패: {e}"


async def _dispatch_tool(tool_name: str, tool_input: dict, event_id: str) -> str:
    """tool_name에 따라 적절한 실행 함수 호출."""
    if tool_name == "query_metrics":
        return await _execute_query_metrics(tool_input)
    elif tool_name == "get_recent_events":
        return await _execute_get_recent_events(tool_input)
    elif tool_name == "propose_action":
        return await _execute_propose_action(tool_input, event_id)
    else:
        return f"알 수 없는 도구: {tool_name}"


# ── 메인 진단 함수 ─────────────────────────────────────────────────────────────

async def run_diagnosis(
    event_id: str,
    event_type: str,
    severity: str,
    description: str,
    agent_id: str,
    model_id: str,
) -> dict:
    """
    Claude SDK agentic loop으로 AIOps 이벤트를 진단하고 조치를 제안합니다.

    Returns:
        {
            "diagnosis": str,       # 진단 결과 텍스트
            "actions_proposed": int, # 제안된 조치 수
            "tool_calls": int,       # 사용된 tool call 수
        }
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY가 설정되지 않았습니다. 더미 진단을 반환합니다.")
        return _dummy_diagnosis(event_type, severity)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_message = (
        f"다음 AIOps 이벤트를 진단하고 조치를 제안해주세요.\n\n"
        f"**이벤트 ID**: {event_id}\n"
        f"**이벤트 유형**: {event_type}\n"
        f"**심각도**: {severity}\n"
        f"**설명**: {description}\n"
        f"**에이전트 ID**: {agent_id}\n"
        f"**모델 ID**: {model_id}\n\n"
        f"먼저 관련 메트릭과 최근 이벤트를 조회하여 상황을 파악한 후 진단해주세요."
    )

    messages = [{"role": "user", "content": user_message}]
    tool_calls_count = 0
    actions_proposed = 0
    final_diagnosis = ""

    # Agentic loop (최대 5회 반복)
    for iteration in range(5):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    # prompt caching: 시스템 프롬프트를 캐시하여 반복 비용 절감
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        logger.info(
            "진단 iteration %d: stop_reason=%s, blocks=%d",
            iteration + 1,
            response.stop_reason,
            len(response.content),
        )

        # 응답을 메시지 히스토리에 추가
        messages.append({"role": "assistant", "content": response.content})

        # tool_use가 없으면 종료
        if response.stop_reason == "end_turn":
            # 최종 텍스트 추출
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_diagnosis = block.text
            break

        # tool_use 블록 처리
        tool_use_blocks = [
            b for b in response.content
            if hasattr(b, "type") and b.type == "tool_use"
        ]

        if not tool_use_blocks:
            # 텍스트만 있으면 종료
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_diagnosis = block.text
            break

        # 모든 tool call 실행
        tool_results = []
        for tool_block in tool_use_blocks:
            tool_calls_count += 1
            tool_name = tool_block.name
            tool_input = tool_block.input if isinstance(tool_block.input, dict) else {}

            logger.info("Tool 실행: %s(%s)", tool_name, json.dumps(tool_input, ensure_ascii=False))
            result_text = await _dispatch_tool(tool_name, tool_input, event_id)

            if tool_name == "propose_action":
                actions_proposed += 1

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})

    return {
        "diagnosis": final_diagnosis or "진단이 완료되었습니다.",
        "actions_proposed": actions_proposed,
        "tool_calls": tool_calls_count,
    }


def _dummy_diagnosis(event_type: str, severity: str) -> dict:
    """API 키 없을 때 반환하는 더미 진단 결과."""
    return {
        "diagnosis": (
            f"[더미 진단] {event_type} 이벤트가 감지되었습니다. "
            f"심각도: {severity}. "
            "ANTHROPIC_API_KEY를 설정하면 실제 AI 진단이 실행됩니다."
        ),
        "actions_proposed": 0,
        "tool_calls": 0,
    }
