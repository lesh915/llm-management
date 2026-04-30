"""AI 진단 에이전트 단위 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_agent_runner.diagnosis_agent import (
    _dummy_diagnosis,
    _execute_query_metrics,
    _execute_get_recent_events,
    _execute_propose_action,
    run_diagnosis,
)


# ── _dummy_diagnosis ───────────────────────────────────────────────────────────

def test_dummy_diagnosis_returns_correct_structure():
    result = _dummy_diagnosis("error_rate_spike", "high")
    assert "diagnosis" in result
    assert "actions_proposed" in result
    assert "tool_calls" in result
    assert result["actions_proposed"] == 0
    assert result["tool_calls"] == 0
    assert "error_rate_spike" in result["diagnosis"]
    assert "high" in result["diagnosis"]


def test_dummy_diagnosis_includes_api_key_hint():
    result = _dummy_diagnosis("latency_p95_breach", "medium")
    assert "ANTHROPIC_API_KEY" in result["diagnosis"]


# ── _execute_query_metrics ─────────────────────────────────────────────────────

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

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_query_metrics({"agent_id": "test-agent-123", "limit": 10})

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

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_query_metrics({"agent_id": "test-agent-123"})

    assert "없습니다" in result


@pytest.mark.asyncio
async def test_query_metrics_http_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_query_metrics({"agent_id": "test-agent-123"})

    assert "실패" in result


# ── _execute_get_recent_events ─────────────────────────────────────────────────

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

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_get_recent_events({"agent_id": "test-agent-123"})

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

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_get_recent_events({"agent_id": "test-agent-123"})

    assert "없습니다" in result


# ── _execute_propose_action ────────────────────────────────────────────────────

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

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_propose_action(
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

    with patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_client):
        result = await _execute_propose_action(
            {
                "action_type": "notify",
                "params": {"channel": "slack"},
                "reason": "테스트",
                "confidence": "low",
            },
            event_id="evt-002",
        )

    assert "실패" in result


# ── run_diagnosis (no API key — dummy path) ────────────────────────────────────

@pytest.mark.asyncio
async def test_run_diagnosis_without_api_key():
    """ANTHROPIC_API_KEY 없을 때 더미 진단 반환."""
    with patch("ai_agent_runner.diagnosis_agent.ANTHROPIC_API_KEY", ""):
        result = await run_diagnosis(
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


# ── run_diagnosis (with mock Claude API) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_diagnosis_with_mock_api():
    """Claude API 응답을 모킹하여 agentic loop 테스트."""
    # end_turn 응답 (tool call 없이 바로 종료)
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "진단 완료: 에러율이 정상 범위를 초과하였습니다."

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [mock_text_block]

    mock_anthropic_client = AsyncMock()
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("ai_agent_runner.diagnosis_agent.ANTHROPIC_API_KEY", "test-key"), \
         patch("ai_agent_runner.diagnosis_agent.anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
        result = await run_diagnosis(
            event_id="evt-100",
            event_type="error_rate_spike",
            severity="high",
            description="에러율 급증",
            agent_id="agent-001",
            model_id="gpt-4",
        )

    assert result["tool_calls"] == 0
    assert result["actions_proposed"] == 0
    assert "진단 완료" in result["diagnosis"]


@pytest.mark.asyncio
async def test_run_diagnosis_with_tool_call():
    """Claude API가 tool_use를 반환하는 경우 테스트."""
    # 1st response: tool_use (query_metrics)
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.name = "query_metrics"
    mock_tool_block.id = "tool-abc123"
    mock_tool_block.input = {"agent_id": "agent-001", "limit": 10}

    mock_response_1 = MagicMock()
    mock_response_1.stop_reason = "tool_use"
    mock_response_1.content = [mock_tool_block]

    # 2nd response: end_turn
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "메트릭 조회 후 진단: 에러율이 임계치를 초과했습니다."

    mock_response_2 = MagicMock()
    mock_response_2.stop_reason = "end_turn"
    mock_response_2.content = [mock_text_block]

    mock_anthropic_client = AsyncMock()
    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=[mock_response_1, mock_response_2]
    )

    # mock httpx for query_metrics
    mock_http_response = MagicMock()
    mock_http_response.json.return_value = {
        "data": [{"time": "2024-01-01T00:00:00", "metric_name": "error_rate", "value": 0.15}]
    }
    mock_http_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(return_value=mock_http_response)

    with patch("ai_agent_runner.diagnosis_agent.ANTHROPIC_API_KEY", "test-key"), \
         patch("ai_agent_runner.diagnosis_agent.anthropic.AsyncAnthropic", return_value=mock_anthropic_client), \
         patch("ai_agent_runner.diagnosis_agent.httpx.AsyncClient", return_value=mock_http_client):
        result = await run_diagnosis(
            event_id="evt-200",
            event_type="error_rate_spike",
            severity="critical",
            description="에러율 15% 초과",
            agent_id="agent-001",
            model_id="model-xyz",
        )

    assert result["tool_calls"] == 1
    assert result["actions_proposed"] == 0
    assert "진단" in result["diagnosis"]
