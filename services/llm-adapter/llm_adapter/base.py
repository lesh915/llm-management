"""Base interface for all LLM adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str | list          # str for text, list for tool calls
    usage: dict                  # input_tokens, output_tokens
    latency_ms: float
    raw: dict                    # provider raw response
    is_local: bool = False       # True for Ollama / vLLM etc.


@dataclass
class AdapterCapabilities:
    """Runtime capabilities — may differ from model_registry metadata."""
    tool_use: bool = False
    streaming: bool = True
    parallel_tool_calls: bool = False
    vision: bool = False
    json_mode: bool = False


class BaseLLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Send messages and return a response."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the model endpoint is reachable."""

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities()

    def format_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> dict:
        """Format an assistant message for the conversation history."""
        msg = {"role": "assistant", "content": content or ""}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg

    def format_tool_result(self, tool_call_id: str, name: str, content: str) -> dict:
        """Format a single tool result message for the conversation history."""
        return self.format_tool_results([{"id": tool_call_id, "name": name, "content": content}])

    def format_tool_results(self, results: list[dict]) -> list[dict] | dict:
        """
        Format multiple tool results for the conversation history.
        Expected result dict: {"id": str, "name": str, "content": str}
        """
        # Default to OpenAI format (separate messages per tool call)
        msgs = []
        for r in results:
            msgs.append({
                "role": "tool",
                "tool_call_id": r["id"],
                "name": r["name"],
                "content": r["content"]
            })
        return msgs
