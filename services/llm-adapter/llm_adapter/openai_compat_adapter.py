"""OpenAI-compatible adapter — works for OpenAI, vLLM, LM Studio, LocalAI."""
from __future__ import annotations

import time

import httpx
from openai import AsyncOpenAI

from .base import BaseLLMAdapter, LLMResponse, AdapterCapabilities
from .tool_converter import convert_tools_for_adapter, extract_tool_calls_from_openai


class OpenAICompatAdapter(BaseLLMAdapter):
    """
    Handles any server that exposes an OpenAI-compatible REST API:
    - OpenAI cloud
    - vLLM  (http://localhost:8000/v1)
    - LM Studio (http://localhost:1234/v1)
    - LocalAI   (http://localhost:8080/v1)
    - Ollama v1 compat (http://localhost:11434/v1)
    """

    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str = "local",
        is_local: bool = False,
        timeout: float = 120.0,
    ):
        self.model_id = model_id
        self.is_local = is_local
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=httpx.AsyncClient(timeout=httpx.Timeout(timeout)),
        )

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        start = time.monotonic()

        params: dict = dict(
            model=self.model_id,
            messages=messages,
            max_tokens=max_tokens,
        )
        if tools:
            params["tools"] = convert_tools_for_adapter(tools, "openai")

        response = await self.client.chat.completions.create(**params)
        choice = response.choices[0]

        tool_calls = extract_tool_calls_from_openai(choice)
        content: str | list = tool_calls if tool_calls else (choice.message.content or "")

        return LLMResponse(
            content=content,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            latency_ms=(time.monotonic() - start) * 1000,
            raw=response.model_dump(),
            is_local=self.is_local,
        )

    async def health_check(self) -> bool:
        if not self.is_local:
            # Cloud providers (OpenAI, Google) sometimes have restricted models.list()
            # or different paths. To avoid blocking preflight, we assume OK if not local.
            # Real errors will be caught during the actual completion call.
            return True
            
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    def get_capabilities(self) -> AdapterCapabilities:
        # Local servers vary — rely on model_registry.capabilities for authoritative info
        return AdapterCapabilities(streaming=True, tool_use=True)

    def format_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> dict:
        """Format an assistant message for the history (OpenAI-specific tool_calls format)."""
        msg = {"role": "assistant", "content": content or ""}
        if tool_calls:
            # Convert back to OpenAI format for the history
            openai_tool_calls = []
            for tc in tool_calls:
                openai_tool_calls.append({
                    "id": tc.get("id"),
                    "type": "function",
                    "function": {
                        "name": tc.get("name"),
                        "arguments": tc.get("input") if isinstance(tc.get("input"), str) else str(tc.get("input", "{}"))
                    }
                })
            msg["tool_calls"] = openai_tool_calls
        return msg
