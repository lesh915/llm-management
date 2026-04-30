"""Anthropic 어댑터 단위 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm_adapter.anthropic_adapter import AnthropicAdapter
from llm_adapter.base import LLMResponse, AdapterCapabilities


def _make_text_response(text: str = "안녕하세요!") -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    response.usage.input_tokens = 20
    response.usage.output_tokens = 10
    response.model_dump.return_value = {}
    return response


def _make_tool_use_response(tool_name: str = "query", tool_id: str = "call_1") -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = {"agent_id": "agent-001"}
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    response.usage.input_tokens = 50
    response.usage.output_tokens = 30
    response.model_dump.return_value = {}
    return response


class TestAnthropicAdapter:
    def _adapter(self, model_id="claude-opus-4-7") -> AnthropicAdapter:
        with patch("llm_adapter.anthropic_adapter.anthropic.AsyncAnthropic"):
            return AnthropicAdapter(model_id=model_id, api_key="test-key")

    # ── complete — text response ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_complete_text_response(self):
        adapter = self._adapter()
        mock_response = _make_text_response("결과 텍스트")
        adapter.client.messages.create = AsyncMock(return_value=mock_response)

        result = await adapter.complete(
            messages=[{"role": "user", "content": "안녕하세요"}],
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "결과 텍스트"
        assert result.usage["input_tokens"] == 20
        assert result.usage["output_tokens"] == 10
        assert result.is_local is False
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self):
        adapter = self._adapter()
        adapter.client.messages.create = AsyncMock(return_value=_make_text_response())

        await adapter.complete(
            messages=[{"role": "user", "content": "test"}],
            system="당신은 전문가입니다.",
        )

        call_kwargs = adapter.client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "당신은 전문가입니다."

    @pytest.mark.asyncio
    async def test_complete_with_tools(self):
        adapter = self._adapter()
        adapter.client.messages.create = AsyncMock(return_value=_make_text_response())

        tools = [{"name": "my_tool", "description": "test", "input_schema": {}}]
        await adapter.complete(
            messages=[{"role": "user", "content": "use a tool"}],
            tools=tools,
        )

        call_kwargs = adapter.client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_complete_no_tools_no_tools_param(self):
        """tools=None일 때 API 호출에 tools 파라미터 포함 안됨."""
        adapter = self._adapter()
        adapter.client.messages.create = AsyncMock(return_value=_make_text_response())

        await adapter.complete(messages=[{"role": "user", "content": "hello"}], tools=None)

        call_kwargs = adapter.client.messages.create.call_args.kwargs
        assert "tools" not in call_kwargs

    # ── complete — tool_use response ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_complete_tool_use_response(self):
        adapter = self._adapter()
        adapter.client.messages.create = AsyncMock(
            return_value=_make_tool_use_response("search", "call_xyz")
        )

        result = await adapter.complete(
            messages=[{"role": "user", "content": "search for something"}],
            tools=[{"name": "search", "description": "", "input_schema": {}}],
        )

        assert isinstance(result.content, list)
        assert len(result.content) == 1
        assert result.content[0]["type"] == "tool_use"
        assert result.content[0]["name"] == "search"
        assert result.content[0]["id"] == "call_xyz"

    @pytest.mark.asyncio
    async def test_complete_model_id_passed(self):
        adapter = self._adapter(model_id="claude-opus-4-7")
        adapter.client.messages.create = AsyncMock(return_value=_make_text_response())

        await adapter.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = adapter.client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-7"

    # ── health_check ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        adapter = self._adapter()
        adapter.client.models.list = AsyncMock()
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        adapter = self._adapter()
        adapter.client.models.list = AsyncMock(side_effect=Exception("API unreachable"))
        assert await adapter.health_check() is False

    # ── get_capabilities ───────────────────────────────────────────────────────

    def test_get_capabilities(self):
        adapter = self._adapter()
        caps = adapter.get_capabilities()
        assert isinstance(caps, AdapterCapabilities)
        assert caps.tool_use is True
        assert caps.vision is True
        assert caps.parallel_tool_calls is True
