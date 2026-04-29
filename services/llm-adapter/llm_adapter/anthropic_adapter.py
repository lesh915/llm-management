"""Anthropic Claude adapter."""
from __future__ import annotations

import time

import anthropic

from .base import BaseLLMAdapter, LLMResponse, AdapterCapabilities


class AnthropicAdapter(BaseLLMAdapter):
    def __init__(self, model_id: str, api_key: str):
        self.model_id = model_id
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        system: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        start = time.monotonic()

        params: dict = dict(
            model=self.model_id,
            max_tokens=max_tokens,
            messages=messages,
        )
        if system:
            params["system"] = system
        if tools:
            params["tools"] = tools

        response = await self.client.messages.create(**params)

        # content: list of blocks or plain text
        content: str | list
        if response.stop_reason == "tool_use":
            content = [
                {"type": b.type, "id": getattr(b, "id", None),
                 "name": getattr(b, "name", None), "input": getattr(b, "input", None)}
                for b in response.content
                if b.type == "tool_use"
            ]
        else:
            content = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )

        return LLMResponse(
            content=content,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            latency_ms=(time.monotonic() - start) * 1000,
            raw=response.model_dump(),
            is_local=False,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            tool_use=True, streaming=True,
            parallel_tool_calls=True, vision=True, json_mode=True,
        )
