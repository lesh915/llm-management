"""Model recommendation logic (FR-C4).

Scores each model's ComparisonResult against three priority profiles:
    - cost:        minimize cost_per_query, acceptable correctness
    - performance: maximize correctness + tool_call_accuracy, acceptable latency
    - balanced:    equal weight across all three dimensions

Returns the best model ID with a natural-language rationale.
"""
from __future__ import annotations

import statistics

# Priority profiles: metric -> weight (sum must be 1.0 per profile)
PRIORITY_WEIGHTS: dict[str, dict[str, float]] = {
    "cost": {
        "cost_per_query":      0.55,
        "correctness":         0.30,
        "latency_p95":         0.15,
    },
    "performance": {
        "correctness":         0.45,
        "tool_call_accuracy":  0.30,
        "latency_p95":         0.25,
    },
    "balanced": {
        "correctness":         0.30,
        "tool_call_accuracy":  0.20,
        "cost_per_query":      0.30,
        "latency_p95":         0.20,
    },
}

# Metrics where lower is better → will be inverted before scoring
_LOWER_IS_BETTER = {"cost_per_query", "latency_p95", "latency_p50", "failure_rate"}


def recommend_model(
    results: list[dict],           # list of ComparisonResult dicts
    priority: str = "balanced",
) -> dict:
    """
    Args:
        results:  Each dict must have keys: model_id, metrics (dict), is_local (bool).
        priority: "cost" | "performance" | "balanced"

    Returns:
        {
            "recommended_model": str,
            "priority": str,
            "scores": {model_id: float},
            "rationale": str,
            "ranking": [{model_id, score, is_local}],
        }
    """
    if not results:
        raise ValueError("No results to evaluate.")

    weights = PRIORITY_WEIGHTS.get(priority, PRIORITY_WEIGHTS["balanced"])

    # --- Collect raw values per metric ---
    metric_values: dict[str, list[float]] = {}
    for r in results:
        for k, v in r.get("metrics", {}).items():
            metric_values.setdefault(k, []).append(float(v))

    # --- Normalize each metric to [0, 1] ---
    normalized: dict[str, dict[str, float]] = {}
    for r in results:
        mid = r["model_id"]
        normalized[mid] = {}
        for metric, weight in weights.items():
            raw = float(r.get("metrics", {}).get(metric, 0.0))
            vals = metric_values.get(metric, [raw])
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1.0
            norm = (raw - lo) / span
            # Invert: lower-is-better metrics get higher score when lower
            if metric in _LOWER_IS_BETTER:
                norm = 1.0 - norm
            normalized[mid][metric] = norm

    # --- Weighted sum ---
    scores: dict[str, float] = {
        mid: sum(normalized[mid].get(m, 0.0) * w for m, w in weights.items())
        for mid in normalized
    }

    best_id = max(scores, key=lambda k: scores[k])
    best_result = next(r for r in results if r["model_id"] == best_id)

    ranking = sorted(
        [{"model_id": r["model_id"],
          "score": round(scores[r["model_id"]], 4),
          "is_local": r.get("is_local", False)}
         for r in results],
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "recommended_model": best_id,
        "priority": priority,
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "ranking": ranking,
        "rationale": _build_rationale(best_id, best_result, results, priority, scores),
    }


def _build_rationale(
    best_id: str,
    best_result: dict,
    all_results: list[dict],
    priority: str,
    scores: dict[str, float],
) -> str:
    m = best_result.get("metrics", {})
    is_local = best_result.get("is_local", False)
    local_tag = " (로컬 모델, 비용 0원)" if is_local else ""

    correctness   = m.get("correctness", None)
    tool_acc      = m.get("tool_call_accuracy", None)
    latency       = m.get("latency_p95", None)
    cost          = m.get("cost_per_query", None)

    lines = [f"**{best_id}**{local_tag}가 '{priority}' 우선순위 기준으로 최고 점수를 기록했습니다."]

    if correctness is not None:
        lines.append(f"- 정확도: {correctness:.1%}")
    if tool_acc is not None:
        lines.append(f"- 도구 호출 정확도: {tool_acc:.1%}")
    if latency is not None:
        lines.append(f"- 레이턴시 P95: {latency:.0f}ms")
    if cost is not None:
        cost_str = "0원 (로컬)" if cost == 0.0 else f"${cost:.4f}"
        lines.append(f"- 쿼리당 비용: {cost_str}")

    if len(all_results) > 1:
        second = sorted(scores.items(), key=lambda x: x[1], reverse=True)[1]
        gap = scores[best_id] - second[1]
        lines.append(f"\n2위 모델({second[0]}) 대비 점수 차이: +{gap:.3f}")

    return "\n".join(lines)
