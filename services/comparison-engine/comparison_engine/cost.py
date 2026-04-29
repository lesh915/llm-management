"""Cost calculation utilities.

Rules:
- Cloud models: (input_tokens / 1M) * input_price + (output_tokens / 1M) * output_price
- Local models (pricing = 0.0): always 0 USD — but latency cost is tracked separately
"""
from __future__ import annotations


def calculate_cost(pricing: dict, usage: dict) -> float:
    """
    Return USD cost for a single LLM call.

    Args:
        pricing: dict with keys input_per_1m_tokens, output_per_1m_tokens (floats)
        usage:   dict with keys input_tokens, output_tokens (ints)
    """
    input_price  = float(pricing.get("input_per_1m_tokens", 0.0))
    output_price = float(pricing.get("output_per_1m_tokens", 0.0))
    input_tokens  = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))

    return (input_tokens / 1_000_000 * input_price
            + output_tokens / 1_000_000 * output_price)


def estimate_task_cost(
    model_pricings: dict[str, dict],
    dataset_size: int,
    avg_input_tokens: int = 500,
    avg_output_tokens: int = 500,
) -> dict[str, float]:
    """
    Pre-run cost estimate per model.

    Returns a dict of model_id -> estimated_usd.
    Local models return 0.0.
    """
    return {
        model_id: calculate_cost(
            pricing,
            {"input_tokens": avg_input_tokens * dataset_size,
             "output_tokens": avg_output_tokens * dataset_size},
        )
        for model_id, pricing in model_pricings.items()
    }


def total_task_cost(per_model_costs: dict[str, float]) -> float:
    return sum(per_model_costs.values())
