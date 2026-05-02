"""Adapter factory — resolves a model_id to the correct LLM adapter."""
from __future__ import annotations

import os

from cryptography.fernet import Fernet

from .anthropic_adapter import AnthropicAdapter
from .base import BaseLLMAdapter
from .ollama_adapter import OllamaAdapter
from .openai_compat_adapter import OpenAICompatAdapter

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("ENCRYPTION_KEY", "")
        if not key:
            raise EnvironmentError("ENCRYPTION_KEY is not set")
        _fernet = Fernet(key.encode())
    return _fernet


def decrypt_api_key(encrypted: str | None) -> str:
    if not encrypted:
        return "local"
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        # If it's not encrypted (e.g. plaintext during dev), return as-is
        return encrypted


def get_adapter(model_record: dict) -> BaseLLMAdapter:
    """
    Build the right adapter from a model_registry row (as dict).

    model_record keys:
        id, provider, is_custom, api_config { endpoint, auth_type,
        model_name, openai_compat, api_key }
    """
    provider: str = model_record["provider"]
    api_cfg: dict = model_record.get("api_config") or {}
    model_name: str = api_cfg.get("model_name") or model_record["id"]
    endpoint: str = api_cfg.get("endpoint", "")
    raw_key: str | None = api_cfg.get("api_key")
    api_key = decrypt_api_key(raw_key)

    match provider:
        case "Anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY") if api_key == "local" else api_key
            return AnthropicAdapter(model_id=model_name, api_key=key or "local")

        case "OpenAI":
            key = os.environ.get("OPENAI_API_KEY") if api_key == "local" else api_key
            return OpenAICompatAdapter(
                model_id=model_name,
                base_url="https://api.openai.com/v1",
                api_key=key or "local",
                is_local=False,
            )

        case "Google":
            key = os.environ.get("GEMINI_API_KEY") if api_key == "local" else api_key
            # Google uses OpenAI-compat via their REST API
            return OpenAICompatAdapter(
                model_id=model_name,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key=key or "local",
                is_local=False,
            )

        case "Ollama":
            # model_record.id is e.g. "ollama/qwen3.5:latest" → strip provider prefix
            raw_name = api_cfg.get("model_name") or model_record["id"]
            clean_name = raw_name.split("/", 1)[-1] if raw_name.startswith("ollama/") else raw_name
            return OllamaAdapter(
                model_name=clean_name,
                base_url=endpoint or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                auto_pull=api_cfg.get("auto_pull", False) if api_cfg else False,
            )

        case "vLLM" | "LMStudio" | "LM Studio" | "LocalAI":
            return OpenAICompatAdapter(
                model_id=model_name,
                base_url=endpoint or os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"),
                api_key=api_key,
                is_local=True,
            )

        case _:
            # Any custom provider that exposes an OpenAI-compat API
            if model_record.get("is_custom") and api_cfg.get("openai_compat"):
                return OpenAICompatAdapter(
                    model_id=model_name,
                    base_url=endpoint,
                    api_key=api_key,
                    is_local=True,
                )
            raise ValueError(
                f"Unsupported provider '{provider}'. "
                "Set is_custom=true and api.openai_compat=true to use a generic OpenAI-compat adapter."
            )
