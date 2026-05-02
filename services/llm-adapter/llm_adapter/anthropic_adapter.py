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
        
        # Debug logging
        try:
            import json
            with open("/tmp/anthropic_debug.json", "a") as f:
                f.write(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False) + "\n")
        except:
            pass

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
        # Trust cloud provider availability during preflight.
        # Specific errors will be caught during execution.
        return True

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            tool_use=True, streaming=True,
            parallel_tool_calls=True, vision=True, json_mode=True,
        )

    def format_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> dict:
        blocks = []
        if content:
            blocks.append({"type": "text", "text": content})
        if tool_calls:
            for tc in tool_calls:
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc.get("input") or tc.get("arguments") or {}
                })
        return {"role": "assistant", "content": blocks}

    def format_tool_result(self, tool_call_id: str, name: str, content: str) -> dict:
        return self.format_tool_results([{"id": tool_call_id, "name": name, "content": content}])

    def format_tool_results(self, results: list[dict]) -> dict:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": r["id"],
                    "content": r["content"]
                }
                for r in results
            ]
        }
