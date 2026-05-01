"""Anthropic Claude SDK 기반 AIOps 진단 에이전트 (agentic loop)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic

from ..tools import TOOL_SCHEMAS, dispatch_tool

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-7"

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


async def run_diagnosis(
    event_id: str,
    event_type: str,
    severity: str,
    description: str,
    agent_id: str,
    model_id: str,
) -> dict[str, Any]:
    """Claude SDK agentic loop으로 AIOps 이벤트를 진단합니다."""
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY 미설정 — 더미 진단 반환")
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
        "먼저 관련 메트릭과 최근 이벤트를 조회하여 상황을 파악한 후 진단해주세요."
    )

    messages: list[dict] = [{"role": "user", "content": user_message}]
    tool_calls_count = 0
    actions_proposed = 0
    final_diagnosis = ""

    for iteration in range(5):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        logger.info(
            "[anthropic] 진단 iteration %d: stop_reason=%s, blocks=%d",
            iteration + 1,
            response.stop_reason,
            len(response.content),
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_diagnosis = block.text
            break

        tool_use_blocks = [
            b for b in response.content
            if hasattr(b, "type") and b.type == "tool_use"
        ]
        if not tool_use_blocks:
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_diagnosis = block.text
            break

        tool_results = []
        for tool_block in tool_use_blocks:
            tool_calls_count += 1
            tool_input = tool_block.input if isinstance(tool_block.input, dict) else {}
            logger.info("Tool 실행: %s(%s)", tool_block.name, json.dumps(tool_input, ensure_ascii=False))

            result_text = await dispatch_tool(tool_block.name, tool_input, event_id)
            if tool_block.name == "propose_action":
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


def _dummy_diagnosis(event_type: str, severity: str) -> dict[str, Any]:
    return {
        "diagnosis": (
            f"[더미 진단] {event_type} 이벤트 감지. 심각도: {severity}. "
            "ANTHROPIC_API_KEY를 설정하면 실제 AI 진단이 실행됩니다."
        ),
        "actions_proposed": 0,
        "tool_calls": 0,
    }
