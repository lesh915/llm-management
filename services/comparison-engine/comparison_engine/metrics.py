"""Metrics calculation for comparison results (FR-C3).

Supported metrics:
    correctness          — exact-match ratio vs expected output
    tool_call_accuracy   — correct tool name + args ratio
    latency_p50          — median latency in ms
    latency_p95          — 95th-percentile latency in ms
    cost_per_query       — mean USD cost per case
    context_utilization  — mean input_tokens / context_window
    failure_rate         — ratio of error/timeout outputs
    avg_turns            — mean number of turns in agent sessions
    tool_usage_rate      — ratio of cases where tools were used
    reasoning_volume     — mean characters of 'thought' per turn
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCase:
    id: str
    input_messages: list[dict]
    expected_output: str | None = None
    expected_tool_calls: list[dict] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)


@dataclass
class ModelOutput:
    case_id: str
    content: str | list     # str for text, list[dict] for tool calls
    input_tokens: int
    output_tokens: int
    latency_ms: float
    error: str | None = None


def calculate_metrics(
    outputs: list[ModelOutput],
    dataset: list[EvalCase],
    requested_metrics: list[str],
    pricing: dict | None = None,
    context_window: int | None = None,
) -> dict[str, float]:
    """
    Compute all requested metrics from a list of model outputs.

    Args:
        outputs:           One ModelOutput per EvalCase (same order).
        dataset:           The original eval cases.
        requested_metrics: Which metrics to compute.
        pricing:           Model pricing dict (for cost_per_query).
        context_window:    Model's max context size (for context_utilization).
    """
    results: dict[str, float] = {}
    case_map = {c.id: c for c in dataset}

    if "correctness" in requested_metrics:
        results["correctness"] = _correctness(outputs, case_map)

    if "tool_call_accuracy" in requested_metrics:
        results["tool_call_accuracy"] = _tool_call_accuracy(outputs, case_map)

    latencies = [o.latency_ms for o in outputs if o.error is None]

    if "latency_p50" in requested_metrics and latencies:
        results["latency_p50"] = _percentile(latencies, 50)

    if "latency_p95" in requested_metrics and latencies:
        results["latency_p95"] = _percentile(latencies, 95)

    if "cost_per_query" in requested_metrics:
        results["cost_per_query"] = _cost_per_query(outputs, pricing or {})

    if "context_utilization" in requested_metrics and context_window:
        results["context_utilization"] = _context_utilization(outputs, context_window)

    if "failure_rate" in requested_metrics:
        results["failure_rate"] = _failure_rate(outputs)

    return results


def calculate_agent_metrics(trajectories: list[dict]) -> dict[str, float]:
    """Compute agent-specific metrics from trajectories."""
    if not trajectories:
        return {}
    
    turns_counts = []
    cases_with_tools = 0
    total_thought_len = 0
    total_turns = 0
    
    for traj in trajectories:
        turns = traj.get("turns", [])
        turns_counts.append(len(turns))
        
        has_tool = any(t.get("action") for t in turns)
        if has_tool:
            cases_with_tools += 1
            
        for turn in turns:
            total_thought_len += len(turn.get("thought") or "")
            total_turns += 1
            
    return {
        "avg_turns": statistics.mean(turns_counts) if turns_counts else 0.0,
        "tool_usage_rate": cases_with_tools / len(trajectories) if trajectories else 0.0,
        "reasoning_volume": total_thought_len / total_turns if total_turns > 0 else 0.0
    }


# ── Individual metric implementations ────────────────────────────────────────

def _correctness(outputs: list[ModelOutput], case_map: dict) -> float:
    if not outputs:
        return 0.0
    correct = 0
    total = 0
    for o in outputs:
        case = case_map.get(o.case_id)
        if not case or case.expected_output is None:
            continue
        total += 1
        if _normalize_text(str(o.content)) == _normalize_text(case.expected_output):
            correct += 1
    return correct / total if total else 0.0


def _tool_call_accuracy(outputs: list[ModelOutput], case_map: dict) -> float:
    """
    Score each output's tool calls against expected_tool_calls.
    A call is correct when both the tool name AND a subset of args match.
    """
    if not outputs:
        return 0.0
    scores: list[float] = []
    for o in outputs:
        case = case_map.get(o.case_id)
        if not case or not case.expected_tool_calls:
            continue
        actual_calls = o.content if isinstance(o.content, list) else []
        score = _match_tool_calls(actual_calls, case.expected_tool_calls)
        scores.append(score)
    return statistics.mean(scores) if scores else 0.0


def _match_tool_calls(
    actual: list[dict],
    expected: list[dict],
) -> float:
    """Return [0, 1] score for how well actual matches expected tool calls."""
    if not expected:
        return 1.0
    if not actual:
        return 0.0

    matched = 0
    for exp in expected:
        for act in actual:
            act_name = act.get("name", "")
            exp_name = exp.get("name", "")
            if act_name != exp_name:
                continue
            # Check argument overlap (partial match allowed)
            act_args = _parse_args(act.get("input", act.get("arguments", {})))
            exp_args = _parse_args(exp.get("arguments", exp.get("input", {})))
            if _args_match(act_args, exp_args):
                matched += 1
                break
    return matched / len(expected)


def _parse_args(args: Any) -> dict:
    if isinstance(args, str):
        try:
            return json.loads(args)
        except Exception:
            return {}
    return args or {}


def _args_match(actual: dict, expected: dict) -> bool:
    """All expected keys must match in actual (subset check)."""
    return all(
        str(actual.get(k)) == str(v)
        for k, v in expected.items()
    )


def _percentile(values: list[float], pct: int) -> float:
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * pct / 100) - 1)
    return sorted_vals[idx]


def _cost_per_query(outputs: list[ModelOutput], pricing: dict) -> float:
    from .cost import calculate_cost
    if not outputs:
        return 0.0
    total = sum(
        calculate_cost(pricing, {"input_tokens": o.input_tokens,
                                  "output_tokens": o.output_tokens})
        for o in outputs
    )
    return total / len(outputs)


def _context_utilization(outputs: list[ModelOutput], context_window: int) -> float:
    if not outputs or context_window <= 0:
        return 0.0
    mean_input = statistics.mean(o.input_tokens for o in outputs)
    return min(mean_input / context_window, 1.0)


def _failure_rate(outputs: list[ModelOutput]) -> float:
    if not outputs:
        return 0.0
    return sum(1 for o in outputs if o.error is not None) / len(outputs)


def _normalize_text(text: str) -> str:
    """Lower-case, strip whitespace, collapse spaces."""
    return re.sub(r"\s+", " ", text.strip().lower())
