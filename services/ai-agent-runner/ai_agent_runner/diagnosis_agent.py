"""AIOps 진단 에이전트 디스패처.

AGENT_TYPE 환경변수에 따라 실제 구현체를 선택합니다.

  AGENT_TYPE=anthropic  (기본값) — Claude SDK agentic loop
  AGENT_TYPE=langgraph           — LangGraph ReAct 에이전트
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

AGENT_TYPE = os.environ.get("AGENT_TYPE", "anthropic").lower()

# 지원 에이전트 목록 (문서화 용)
_SUPPORTED = ("anthropic", "langgraph")

if AGENT_TYPE not in _SUPPORTED:
    logger.warning(
        "AGENT_TYPE=%r 은 지원하지 않습니다. anthropic으로 폴백합니다. 지원 목록: %s",
        AGENT_TYPE,
        _SUPPORTED,
    )
    AGENT_TYPE = "anthropic"

logger.info("에이전트 타입: %s", AGENT_TYPE)


async def run_diagnosis(
    event_id: str,
    event_type: str,
    severity: str,
    description: str,
    agent_id: str,
    model_id: str,
) -> dict[str, Any]:
    """AGENT_TYPE에 따라 진단 에이전트를 선택하여 실행합니다."""
    if AGENT_TYPE == "langgraph":
        from .agents.langgraph_agent import run_diagnosis as _run
    else:
        from .agents.anthropic_agent import run_diagnosis as _run

    return await _run(
        event_id=event_id,
        event_type=event_type,
        severity=severity,
        description=description,
        agent_id=agent_id,
        model_id=model_id,
    )
