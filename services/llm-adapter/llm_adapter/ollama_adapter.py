"""Ollama native adapter with OpenAI-compat fallback for tool calls."""
from __future__ import annotations

import time

import httpx

from .base import BaseLLMAdapter, LLMResponse, AdapterCapabilities
from .openai_compat_adapter import OpenAICompatAdapter


class OllamaAdapter(BaseLLMAdapter):
    """
    Ollama adapter strategy:
    - Plain chat   → Ollama native  /api/chat  (faster, richer metadata)
    - Tool calls   → OpenAI-compat  /v1/chat/completions (Ollama ≥0.2.8)

    Extra features:
    - list_local_models()  → installed model names
    - auto_pull=True       → pulls model on first use if not installed
    """

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        auto_pull: bool = False,
        timeout: float = 120.0,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.auto_pull = auto_pull
        self._http = httpx.AsyncClient(timeout=timeout)
        # Delegate tool-call requests to the OpenAI-compat endpoint
        self._compat = OpenAICompatAdapter(
            model_id=model_name,
            base_url=f"{self.base_url}/v1",
            api_key="ollama",
            is_local=True,
            timeout=timeout,
        )

    # ── Public interface ──────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        if tools:
            # Use OpenAI-compat path for tool calls
            return await self._compat.complete(messages, tools, max_tokens, **kwargs)

        if self.auto_pull:
            await self._ensure_model_exists()

        return await self._native_chat(messages, max_tokens)

    async def health_check(self) -> bool:
        try:
            resp = await self._http.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(tool_use=True, streaming=True)

    def format_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> dict:
        return self._compat.format_assistant_message(content, tool_calls)

    # ── Ollama-specific helpers ───────────────────────────────────────────────

    async def list_local_models(self) -> list[str]:
        """Return names of models installed in this Ollama instance."""
        resp = await self._http.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]

    async def pull_model(self, model_name: str | None = None) -> None:
        """Pull (download) a model. Uses self.model_name if not specified."""
        name = model_name or self.model_name
        resp = await self._http.post(
            f"{self.base_url}/api/pull",
            json={"name": name, "stream": False},
            timeout=600.0,
        )
        resp.raise_for_status()

    async def get_model_info(self) -> dict:
        """Return Ollama model details (parameters, template, etc.)."""
        resp = await self._http.post(
            f"{self.base_url}/api/show",
            json={"name": self.model_name},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _native_chat(self, messages: list[dict], max_tokens: int) -> LLMResponse:
        start = time.monotonic()
        resp = await self._http.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
            latency_ms=(time.monotonic() - start) * 1000,
            raw=data,
            is_local=True,
        )

    async def _ensure_model_exists(self) -> None:
        installed = await self.list_local_models()
        if self.model_name not in installed:
            await self.pull_model()
