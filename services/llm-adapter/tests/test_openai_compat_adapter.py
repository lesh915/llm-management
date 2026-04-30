"""OpenAI-compatible 어댑터 단위 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm_adapter.openai_compat_adapter import OpenAICompatAdapter
from llm_adapter.base import LLMResponse


def _make_openai_response(content: str = "Hello", tool_calls=None) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = msg

    usage = MagicMock()
    usage.prompt_tokens = 15
    usage.completion_tokens = 8

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response.model_dump.return_value = {}
    return response


class TestOpenAICompatAdapter:
    def _adapter(self, is_local=False) -> OpenAICompatAdapter:
        with patch("llm_adapter.openai_compat_adapter.AsyncOpenAI"):
            return OpenAICompatAdapter(
                model_id="gpt-4o",
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                is_local=is_local,
            )

    # ── complete — text ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_complete_text_response(self):
        adapter = self._adapter()
        adapter.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("안녕하세요!")
        )

        result = await adapter.complete(
            messages=[{"role": "user", "content": "hi"}]
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "안녕하세요!"
        assert result.usage["input_tokens"] == 15
        assert result.usage["output_tokens"] == 8
        assert result.is_local is False

    @pytest.mark.asyncio
    async def test_complete_local_flag(self):
        adapter = self._adapter(is_local=True)
        adapter.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("local response")
        )

        result = await adapter.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.is_local is True

    # ── complete — tool calls ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_complete_with_tool_calls(self):
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "search"
        tc.function.arguments = '{"query": "test"}'

        adapter = self._adapter()
        adapter.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(tool_calls=[tc])
        )

        result = await adapter.complete(
            messages=[{"role": "user", "content": "search something"}],
            tools=[{"name": "search", "description": "", "input_schema": {}}],
        )

        assert isinstance(result.content, list)
        assert result.content[0]["type"] == "tool_use"
        assert result.content[0]["name"] == "search"

    @pytest.mark.asyncio
    async def test_tools_converted_to_openai_format(self):
        """Anthropic 형식의 tools가 OpenAI 형식으로 변환되어 전달되는지 확인."""
        adapter = self._adapter()
        adapter.client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response()
        )

        anthropic_tools = [{
            "name": "my_tool",
            "description": "desc",
            "input_schema": {"type": "object", "properties": {}},
        }]

        await adapter.complete(
            messages=[{"role": "user", "content": "use tool"}],
            tools=anthropic_tools,
        )

        call_kwargs = adapter.client.chat.completions.create.call_args.kwargs
        assert "tools" in call_kwargs
        # OpenAI 형식인지 확인
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "my_tool"

    @pytest.mark.asyncio
    async def test_no_usage_returns_zero(self):
        """usage가 None인 경우 0으로 처리."""
        response = _make_openai_response()
        response.usage = None

        adapter = self._adapter()
        adapter.client.chat.completions.create = AsyncMock(return_value=response)

        result = await adapter.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.usage["input_tokens"] == 0
        assert result.usage["output_tokens"] == 0

    # ── health_check ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        adapter = self._adapter()
        adapter.client.models.list = AsyncMock()
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        adapter = self._adapter()
        adapter.client.models.list = AsyncMock(side_effect=Exception("timeout"))
        assert await adapter.health_check() is False
