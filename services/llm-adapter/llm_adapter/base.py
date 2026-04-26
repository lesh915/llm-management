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
