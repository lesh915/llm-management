"""Auto-discover and register Ollama models into the registry."""
from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import ModelRegistry

# Known model families for metadata inference
_FAMILY_PATTERNS: list[tuple[str, dict]] = [
    ("llama",     {"family": "Llama",    "reasoning_depth": "medium"}),
    ("mistral",   {"family": "Mistral",  "reasoning_depth": "medium"}),
    ("mixtral",   {"family": "Mixtral",  "reasoning_depth": "high"}),
    ("qwen",      {"family": "Qwen",     "reasoning_depth": "medium"}),
    ("deepseek",  {"family": "DeepSeek", "reasoning_depth": "high"}),
    ("phi",       {"family": "Phi",      "reasoning_depth": "medium"}),
    ("gemma",     {"family": "Gemma",    "reasoning_depth": "medium"}),
    ("falcon",    {"family": "Falcon",   "reasoning_depth": "low"}),
    ("vicuna",    {"family": "Vicuna",   "reasoning_depth": "medium"}),
    ("codellama", {"family": "CodeLlama","reasoning_depth": "medium"}),
]


async def import_from_ollama(base_url: str, db: AsyncSession) -> dict:
    """
    Scan a running Ollama instance and register discovered models.
    Returns counts of imported / already_registered / failed models.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
        except Exception as exc:
            raise ConnectionError(
                f"Cannot connect to Ollama at {base_url}: {exc}"
            ) from exc

        installed: list[str] = [m["name"] for m in resp.json().get("models", [])]

    results: dict[str, list] = {"imported": [], "already_registered": [], "failed": []}

    for model_name in installed:
        model_id = f"ollama/{model_name}"
        existing = await db.get(ModelRegistry, model_id)
        if existing:
            results["already_registered"].append(model_id)
            continue

        try:
            meta = _infer_model_meta(model_name)
            db.add(ModelRegistry(
                id=model_id,
                provider="Ollama",
                family=meta["family"],
                version=model_name,
                is_custom=True,
                capabilities=meta["capabilities"],
                characteristics=meta["characteristics"],
                pricing={"input_per_1m_tokens": 0.0, "output_per_1m_tokens": 0.0},
                api_config={
                    "endpoint": base_url,
                    "auth_type": "none",
                    "model_name": model_name,
                    "openai_compat": True,
                },
            ))
            results["imported"].append(model_id)
        except Exception as exc:
            results["failed"].append({"model": model_id, "error": str(exc)})

    await db.commit()
    return results


def _infer_model_meta(model_name: str) -> dict:
    """
    Infer capabilities and characteristics from a model name string.
    Examples: "llama3.2:3b", "mistral:7b-instruct", "qwen2.5:72b"
    """
    name_lower = model_name.lower()

    family = "Unknown"
    reasoning_depth = "medium"
    for pattern, meta in _FAMILY_PATTERNS:
        if pattern in name_lower:
            family = meta["family"]
            reasoning_depth = meta["reasoning_depth"]
            break

    # Infer context window from parameter count
    context_window = 8192
    if any(x in name_lower for x in ["70b", "72b", "65b"]):
        context_window = 131072
    elif any(x in name_lower for x in ["34b", "32b", "30b"]):
        context_window = 65536
    elif any(x in name_lower for x in ["13b", "14b"]):
        context_window = 32768
    elif any(x in name_lower for x in ["7b", "8b", "6b"]):
        context_window = 32768
    elif any(x in name_lower for x in ["3b", "2b", "1b"]):
        context_window = 8192

    vision = any(x in name_lower for x in ["vision", "vl", "vlm", "llava", "moondream"])

    return {
        "family": family,
        "version": model_name,
        "capabilities": {
            "context_window": context_window,
            "max_output_tokens": min(context_window // 4, 8192),
            "vision": vision,
            "tool_use": True,
            "structured_output": True,
            "streaming": True,
            "parallel_tool_calls": False,
            "extended_thinking": False,
        },
        "characteristics": {
            "reasoning_depth": reasoning_depth,
            "instruction_following": "medium",
            "code_generation": "medium",
            "latency_tier": "low",
        },
    }
