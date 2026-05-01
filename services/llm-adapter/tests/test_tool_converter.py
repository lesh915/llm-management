"""LLM 어댑터 — 도구 형식 변환기 단위 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm_adapter.tool_converter import (
    convert_tools_for_adapter,
    _anthropic_to_openai,
    _openai_to_anthropic,
    extract_tool_calls_from_openai,
)

# ── 샘플 도구 정의 ──────────────────────────────────────────────────────────────

ANTHROPIC_TOOL = {
    "name": "query_metrics",
    "description": "에이전트 운영 지표를 조회합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "metric": {"type": "string", "enum": ["error_rate", "latency_p95"]},
        },
        "required": ["agent_id"],
    },
}

OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name": "query_metrics",
        "description": "에이전트 운영 지표를 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "metric": {"type": "string", "enum": ["error_rate", "latency_p95"]},
            },
            "required": ["agent_id"],
        },
    },
}


# ── convert_tools_for_adapter ──────────────────────────────────────────────────

class TestConvertToolsForAdapter:
    def test_openai_format_conversion(self):
        result = convert_tools_for_adapter([ANTHROPIC_TOOL], "openai")
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "query_metrics"

    def test_anthropic_format_returns_unchanged(self):
        result = convert_tools_for_adapter([ANTHROPIC_TOOL], "anthropic")
        assert result == [ANTHROPIC_TOOL]

    def test_empty_tools_list(self):
        assert convert_tools_for_adapter([], "openai") == []
        assert convert_tools_for_adapter([], "anthropic") == []

    def test_multiple_tools_conversion(self):
        tools = [ANTHROPIC_TOOL, {**ANTHROPIC_TOOL, "name": "another_tool"}]
        result = convert_tools_for_adapter(tools, "openai")
        assert len(result) == 2
        assert result[0]["function"]["name"] == "query_metrics"
        assert result[1]["function"]["name"] == "another_tool"


# ── _anthropic_to_openai ───────────────────────────────────────────────────────

class TestAnthropicToOpenAI:
    def test_full_conversion(self):
        result = _anthropic_to_openai(ANTHROPIC_TOOL)
        assert result["type"] == "function"
        assert result["function"]["name"] == ANTHROPIC_TOOL["name"]
        assert result["function"]["description"] == ANTHROPIC_TOOL["description"]
        assert result["function"]["parameters"] == ANTHROPIC_TOOL["input_schema"]

    def test_missing_description_defaults_to_empty(self):
        tool = {"name": "simple_tool", "input_schema": {"type": "object", "properties": {}}}
        result = _anthropic_to_openai(tool)
        assert result["function"]["description"] == ""

    def test_missing_input_schema_defaults(self):
        tool = {"name": "minimal_tool", "description": "minimal"}
        result = _anthropic_to_openai(tool)
        assert result["function"]["parameters"] == {"type": "object", "properties": {}}


# ── _openai_to_anthropic ───────────────────────────────────────────────────────

class TestOpenAIToAnthropic:
    def test_full_conversion(self):
        result = _openai_to_anthropic(OPENAI_TOOL)
        assert result["name"] == "query_metrics"
        assert result["description"] == OPENAI_TOOL["function"]["description"]
        assert result["input_schema"] == OPENAI_TOOL["function"]["parameters"]

    def test_missing_parameters_defaults(self):
        tool = {"function": {"name": "simple", "description": "desc"}}
        result = _openai_to_anthropic(tool)
        assert result["input_schema"] == {"type": "object", "properties": {}}

    def test_flat_function_format(self):
        """function 키 없이 바로 name이 있는 경우."""
        tool = {"name": "flat_tool", "description": "flat", "parameters": {"type": "object", "properties": {}}}
        result = _openai_to_anthropic(tool)
        assert result["name"] == "flat_tool"


# ── extract_tool_calls_from_openai ─────────────────────────────────────────────

class TestExtractToolCallsFromOpenAI:
    def _make_choice(self, tool_calls=None, content=""):
        choice = MagicMock()
        choice.message.content = content
        choice.message.tool_calls = tool_calls
        return choice

    def test_no_tool_calls_returns_none(self):
        choice = self._make_choice(tool_calls=None)
        assert extract_tool_calls_from_openai(choice) is None

    def test_empty_tool_calls_returns_none(self):
        choice = self._make_choice(tool_calls=[])
        # openai SDK returns None not [] when no tool calls, but handle [] gracefully
        result = extract_tool_calls_from_openai(choice)
        # [] is falsy, treated same as None in the implementation
        assert result == [] or result is None

    def test_single_tool_call_extracted(self):
        tc = MagicMock()
        tc.id = "call_abc123"
        tc.function.name = "query_metrics"
        tc.function.arguments = '{"agent_id": "agent-001"}'

        choice = self._make_choice(tool_calls=[tc])
        result = extract_tool_calls_from_openai(choice)

        assert result is not None
        assert len(result) == 1
        assert result[0]["type"] == "tool_use"
        assert result[0]["id"] == "call_abc123"
        assert result[0]["name"] == "query_metrics"
        assert result[0]["input"] == '{"agent_id": "agent-001"}'

    def test_multiple_tool_calls_extracted(self):
        tc1 = MagicMock()
        tc1.id = "call_1"
        tc1.function.name = "tool_a"
        tc1.function.arguments = "{}"

        tc2 = MagicMock()
        tc2.id = "call_2"
        tc2.function.name = "tool_b"
        tc2.function.arguments = '{"key": "value"}'

        choice = self._make_choice(tool_calls=[tc1, tc2])
        result = extract_tool_calls_from_openai(choice)

        assert len(result) == 2
        assert result[0]["name"] == "tool_a"
        assert result[1]["name"] == "tool_b"
