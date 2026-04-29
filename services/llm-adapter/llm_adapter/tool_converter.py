"""Convert tool schemas between Anthropic and OpenAI formats.

Internal standard: Anthropic format.
Conversion happens only when sending to an OpenAI-compatible endpoint.
"""
from __future__ import annotations


def convert_tools_for_adapter(
    tools: list[dict],
    target_format: str,  # "anthropic" | "openai"
) -> list[dict]:
    if target_format == "openai":
        return [_anthropic_to_openai(t) for t in tools]
    return tools  # already in Anthropic format


def _anthropic_to_openai(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def _openai_to_anthropic(tool: dict) -> dict:
    fn = tool.get("function", tool)
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


def extract_tool_calls_from_openai(choice) -> list[dict] | None:
    """Parse tool calls from an OpenAI-style choice object."""
    msg = choice.message
    if not msg.tool_calls:
        return None
    return [
        {
            "type": "tool_use",
            "id": tc.id,
            "name": tc.function.name,
            "input": tc.function.arguments,
        }
        for tc in msg.tool_calls
    ]
