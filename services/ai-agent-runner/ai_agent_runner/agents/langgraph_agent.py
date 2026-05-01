"""LangGraph + LangChain Anthropic 기반 AIOps 진단 에이전트.

Anthropic 에이전트와 동일한 시그니처(run_diagnosis)를 제공하여
AGENT_TYPE=langgraph 환경변수만으로 교체 가능합니다.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """당신은 LLM 관리 플랫폼의 AIOps 전문 진단 에이전트입니다.

역할:
1. LLM 에이전트의 운영 이벤트와 메트릭을 분석합니다
2. 장애 원인(높은 오류율, 지연 급증, 비용 초과, 도구 실패)을 진단합니다
3. 구체적인 조치 방안을 제안합니다

진단 절차:
1. query_metrics로 최근 메트릭을 조회하여 현황을 파악합니다
2. get_recent_events로 관련 이벤트 히스토리를 확인합니다
3. 데이터 기반으로 근본 원인을 파악합니다
4. propose_action으로 명확한 조치 1가지를 제안합니다

조치 유형: switch_model, rollback, notify, scale_down
신뢰도: high / medium / low 중 하나를 반드시 포함합니다.

설명은 한국어로, 기술 용어와 action type은 영어로 작성합니다.
"""


async def run_diagnosis(
    event_id: str,
    event_type: str,
    severity: str,
    description: str,
    agent_id: str,
    model_id: str,
) -> dict[str, Any]:
    """LangGraph ReAct 에이전트로 AIOps 이벤트를 진단합니다."""
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY 미설정 — 더미 진단 반환")
        return {
            "diagnosis": (
                f"[LangGraph 더미 진단] {event_type} 이벤트 감지. 심각도: {severity}. "
                "ANTHROPIC_API_KEY를 설정하면 실제 AI 진단이 실행됩니다."
            ),
            "actions_proposed": 0,
            "tool_calls": 0,
        }

    # ── LangChain / LangGraph 임포트 (런타임 지연 로딩) ──────────────────────
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.tools import tool
        from langgraph.prebuilt import create_react_agent
    except ImportError as e:
        logger.error("LangGraph 의존성 누락: %s — pip install langchain-anthropic langgraph", e)
        raise

    from ..tools import (
        execute_get_recent_events,
        execute_propose_action,
        execute_query_metrics,
    )

    # ── LangChain 도구 정의 (event_id를 클로저로 캡처) ────────────────────────

    @tool
    async def query_metrics(
        agent_id: str,
        model_id: str = "",
        metric: str = "",
        limit: int = 50,
    ) -> str:
        """에이전트/모델의 최근 운영 메트릭을 조회합니다 (error_rate, latency_p95, cost 등)."""
        args: dict[str, Any] = {"agent_id": agent_id, "limit": limit}
        if model_id:
            args["model_id"] = model_id
        if metric:
            args["metric"] = metric
        return await execute_query_metrics(args)

    @tool
    async def get_recent_events(
        agent_id: str,
        limit: int = 10,
        status: str = "",
    ) -> str:
        """에이전트의 최근 AIOps 이벤트 히스토리를 조회합니다."""
        args: dict[str, Any] = {"agent_id": agent_id, "limit": limit}
        if status:
            args["status"] = status
        return await execute_get_recent_events(args)

    @tool
    async def propose_action(
        action_type: str,
        reason: str,
        confidence: str,
        target_model_id: str = "",
        target_version: str = "",
        message: str = "",
    ) -> str:
        """AIOps 이벤트에 대한 조치를 제안합니다. 인간 승인 대기 상태로 등록됩니다.

        action_type: switch_model | rollback | notify | scale_down
        confidence: high | medium | low
        """
        params: dict[str, Any] = {}
        if target_model_id:
            params["target_model_id"] = target_model_id
        if target_version:
            params["target_version"] = target_version
        if message:
            params["message"] = message

        args = {
            "action_type": action_type,
            "params": params,
            "reason": reason,
            "confidence": confidence,
        }
        # event_id는 외부 클로저에서 캡처
        return await execute_propose_action(args, event_id)

    # ── ReAct 에이전트 구성 ────────────────────────────────────────────────────
    llm = ChatAnthropic(
        model=MODEL,
        api_key=ANTHROPIC_API_KEY,
        temperature=0,
    )

    tools = [query_metrics, get_recent_events, propose_action]

    graph = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SystemMessage(content=SYSTEM_PROMPT),
    )

    user_message = (
        f"다음 AIOps 이벤트를 진단하고 조치를 제안해주세요.\n\n"
        f"이벤트 ID: {event_id}\n"
        f"이벤트 유형: {event_type}\n"
        f"심각도: {severity}\n"
        f"설명: {description}\n"
        f"에이전트 ID: {agent_id}\n"
        f"모델 ID: {model_id}\n\n"
        "먼저 관련 메트릭과 최근 이벤트를 조회하여 상황을 파악한 후 진단해주세요."
    )

    logger.info("[langgraph] 진단 시작: event=%s, type=%s", event_id, event_type)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=user_message)]}
    )

    # ── 결과 파싱 ──────────────────────────────────────────────────────────────
    messages = result.get("messages", [])

    # tool call 수 집계
    tool_calls_count = sum(
        len(m.tool_calls)
        for m in messages
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
    )

    # propose_action 호출 수 집계
    actions_proposed = sum(
        1
        for m in messages
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
        for tc in m.tool_calls
        if tc.get("name") == "propose_action"
    )

    # 최종 AI 응답 텍스트 추출
    final_diagnosis = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, str) and content.strip():
                final_diagnosis = content
                break
            elif isinstance(content, list):
                texts = [
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                    if not isinstance(block, dict) or block.get("type") == "text"
                ]
                final_diagnosis = "\n".join(t for t in texts if t.strip())
                if final_diagnosis:
                    break

    logger.info(
        "[langgraph] 진단 완료: event=%s, tool_calls=%d, actions=%d",
        event_id,
        tool_calls_count,
        actions_proposed,
    )

    return {
        "diagnosis": final_diagnosis or "진단이 완료되었습니다.",
        "actions_proposed": actions_proposed,
        "tool_calls": tool_calls_count,
    }
