"""AI 진단 에이전트 단위 테스트.

- tools.py 공통 executor 테스트
- anthropic_agent.py (Anthropic SDK agentic loop) 테스트
- diagnosis_agent.py dispatcher 테스트
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── tools.py — 공통 executor ───────────────────────────────────────────────────

from ai_agent_runner.tools import (
    execute_query_metrics,
    execute_get_recent_events,
    execute_propose_action,
)


@pytest.mark.asyncio
async def test_query_metrics_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"time": "2024-01-01T00:00:00", "metric_name": "error_rate", "value": 0.05},
            {"time": "2024-01-01T00:01:00", "metric_name": "error_rate", "value": 0.08},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_query_metrics({"agent_id": "test-agent-123", "limit": 10})

    assert "error_rate" in result
    assert "0.05" in result


@pytest.mark.asyncio
async def test_query_metrics_empty_data():
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_query_metrics({"agent_id": "test-agent-123"})

    assert "없습니다" in result


@pytest.mark.asyncio
async def test_query_metrics_http_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_query_metrics({"agent_id": "test-agent-123"})

    assert "실패" in result


@pytest.mark.asyncio
async def test_get_recent_events_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "created_at": "2024-01-01T00:00:00",
                "event_type": "error_rate_spike",
                "severity": "high",
                "status": "open",
                "description": "Error rate exceeded threshold",
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_get_recent_events({"agent_id": "test-agent-123"})

    assert "error_rate_spike" in result
    assert "high" in result


@pytest.mark.asyncio
async def test_get_recent_events_empty():
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_get_recent_events({"agent_id": "test-agent-123"})

    assert "없습니다" in result


@pytest.mark.asyncio
async def test_propose_action_success():
    mock_get_resp = MagicMock()
    mock_get_resp.json.return_value = {"data": {"actions": []}}
    mock_get_resp.raise_for_status = MagicMock()

    mock_patch_resp = MagicMock()
    mock_patch_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_get_resp)
    mock_client.patch = AsyncMock(return_value=mock_patch_resp)

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_propose_action(
            {
                "action_type": "switch_model",
                "params": {"fallback_model_id": "gpt-4"},
                "reason": "높은 에러율 감지",
                "confidence": "high",
            },
            event_id="evt-001",
        )

    assert "switch_model" in result
    assert "high" in result


@pytest.mark.asyncio
async def test_propose_action_http_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("Service unavailable"))

    with patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_client):
        result = await execute_propose_action(
            {"action_type": "notify", "params": {}, "reason": "테스트", "confidence": "low"},
            event_id="evt-002",
        )

    assert "실패" in result


# ── anthropic_agent.py ─────────────────────────────────────────────────────────

from ai_agent_runner.agents.anthropic_agent import run_diagnosis as anthropic_run_diagnosis
from ai_agent_runner.agents.anthropic_agent import _dummy_diagnosis


def test_dummy_diagnosis_returns_correct_structure():
    result = _dummy_diagnosis("error_rate_spike", "high")
    assert "diagnosis" in result
    assert result["actions_proposed"] == 0
    assert result["tool_calls"] == 0
    assert "error_rate_spike" in result["diagnosis"]
    assert "high" in result["diagnosis"]


def test_dummy_diagnosis_includes_api_key_hint():
    result = _dummy_diagnosis("latency_p95_breach", "medium")
    assert "ANTHROPIC_API_KEY" in result["diagnosis"]


@pytest.mark.asyncio
async def test_anthropic_run_diagnosis_without_api_key():
    with patch("ai_agent_runner.agents.anthropic_agent.ANTHROPIC_API_KEY", ""):
        result = await anthropic_run_diagnosis(
            event_id="evt-999",
            event_type="error_rate_spike",
            severity="high",
            description="에러율 급증",
            agent_id="agent-001",
            model_id="gpt-4",
        )
    assert result["tool_calls"] == 0
    assert result["actions_proposed"] == 0
    assert "ANTHROPIC_API_KEY" in result["diagnosis"]


@pytest.mark.asyncio
async def test_anthropic_run_diagnosis_end_turn():
    """Claude API end_turn 응답 테스트 (tool call 없음)."""
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "진단 완료: 에러율이 정상 범위를 초과하였습니다."

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [mock_text_block]

    mock_anthropic_client = AsyncMock()
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("ai_agent_runner.agents.anthropic_agent.ANTHROPIC_API_KEY", "test-key"), \
         patch("ai_agent_runner.agents.anthropic_agent.anthropic.AsyncAnthropic",
               return_value=mock_anthropic_client):
        result = await anthropic_run_diagnosis(
            event_id="evt-100",
            event_type="error_rate_spike",
            severity="high",
            description="에러율 급증",
            agent_id="agent-001",
            model_id="gpt-4",
        )

    assert result["tool_calls"] == 0
    assert "진단 완료" in result["diagnosis"]


@pytest.mark.asyncio
async def test_anthropic_run_diagnosis_with_tool_call():
    """Claude API tool_use → end_turn 2 step 테스트."""
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.name = "query_metrics"
    mock_tool_block.id = "tool-abc123"
    mock_tool_block.input = {"agent_id": "agent-001", "limit": 10}

    mock_response_1 = MagicMock()
    mock_response_1.stop_reason = "tool_use"
    mock_response_1.content = [mock_tool_block]

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "메트릭 조회 후 진단: 에러율 임계치 초과."

    mock_response_2 = MagicMock()
    mock_response_2.stop_reason = "end_turn"
    mock_response_2.content = [mock_text_block]

    mock_anthropic_client = AsyncMock()
    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=[mock_response_1, mock_response_2]
    )

    mock_http_response = MagicMock()
    mock_http_response.json.return_value = {
        "data": [{"time": "2024-01-01T00:00:00", "metric_name": "error_rate", "value": 0.15}]
    }
    mock_http_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(return_value=mock_http_response)

    with patch("ai_agent_runner.agents.anthropic_agent.ANTHROPIC_API_KEY", "test-key"), \
         patch("ai_agent_runner.agents.anthropic_agent.anthropic.AsyncAnthropic",
               return_value=mock_anthropic_client), \
         patch("ai_agent_runner.tools.httpx.AsyncClient", return_value=mock_http_client):
        result = await anthropic_run_diagnosis(
            event_id="evt-200",
            event_type="error_rate_spike",
            severity="critical",
            description="에러율 15% 초과",
            agent_id="agent-001",
            model_id="model-xyz",
        )

    assert result["tool_calls"] == 1
    assert "진단" in result["diagnosis"]


# ── dispatcher: diagnosis_agent.py ────────────────────────────────────────────

from ai_agent_runner.diagnosis_agent import run_diagnosis


@pytest.mark.asyncio
async def test_dispatcher_routes_to_anthropic_by_default():
    """AGENT_TYPE 미설정 시 anthropic 에이전트로 라우팅."""
    mock_result = {"diagnosis": "anthropic result", "actions_proposed": 0, "tool_calls": 0}

    with patch("ai_agent_runner.diagnosis_agent.AGENT_TYPE", "anthropic"), \
         patch("ai_agent_runner.agents.anthropic_agent.run_diagnosis",
               new=AsyncMock(return_value=mock_result)) as mock_run:
        result = await run_diagnosis(
            event_id="evt-d1",
            event_type="error_rate_spike",
            severity="high",
            description="테스트",
            agent_id="agent-001",
            model_id="m1",
        )

    assert result["diagnosis"] == "anthropic result"


@pytest.mark.asyncio
async def test_dispatcher_routes_to_langgraph():
    """AGENT_TYPE=langgraph 시 langgraph 에이전트로 라우팅."""
    mock_result = {"diagnosis": "langgraph result", "actions_proposed": 1, "tool_calls": 2}

    with patch("ai_agent_runner.diagnosis_agent.AGENT_TYPE", "langgraph"), \
         patch("ai_agent_runner.agents.langgraph_agent.run_diagnosis",
               new=AsyncMock(return_value=mock_result)):
        result = await run_diagnosis(
            event_id="evt-d2",
            event_type="latency_spike",
            severity="medium",
            description="지연 급증",
            agent_id="agent-002",
            model_id="m2",
        )

    assert result["diagnosis"] == "langgraph result"
    assert result["actions_proposed"] == 1
