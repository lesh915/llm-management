"""Unit tests for the model recommendation logic."""
import pytest
from comparison_engine.recommender import recommend_model, PRIORITY_WEIGHTS


def _make_result(model_id: str, correctness: float, cost: float,
                 latency_p95: float, tool_acc: float = 0.9,
                 is_local: bool = False) -> dict:
    return {
        "model_id": model_id,
        "is_local": is_local,
        "metrics": {
            "correctness": correctness,
            "tool_call_accuracy": tool_acc,
            "cost_per_query": cost,
            "latency_p95": latency_p95,
        },
    }


class TestRecommendModel:
    def test_cost_priority_picks_cheapest_acceptable(self):
        results = [
            _make_result("cloud-a", correctness=0.95, cost=0.01, latency_p95=200),
            _make_result("cloud-b", correctness=0.92, cost=0.001, latency_p95=300),
            _make_result("local-c", correctness=0.80, cost=0.0, latency_p95=500,
                         is_local=True),
        ]
        rec = recommend_model(results, priority="cost")
        # Local model has zero cost → should rank first in cost priority
        assert rec["recommended_model"] == "local-c"

    def test_performance_priority_picks_most_accurate(self):
        results = [
            _make_result("fast-cheap", correctness=0.70, cost=0.001, latency_p95=100),
            _make_result("accurate",   correctness=0.97, cost=0.05,  latency_p95=400),
            _make_result("middle",     correctness=0.85, cost=0.01,  latency_p95=200),
        ]
        rec = recommend_model(results, priority="performance")
        assert rec["recommended_model"] == "accurate"

    def test_balanced_priority_returns_all_models_in_ranking(self):
        results = [
            _make_result("a", 0.9, 0.01, 200),
            _make_result("b", 0.8, 0.005, 150),
            _make_result("c", 0.95, 0.02, 300),
        ]
        rec = recommend_model(results, priority="balanced")
        ranked_ids = [r["model_id"] for r in rec["ranking"]]
        assert set(ranked_ids) == {"a", "b", "c"}

    def test_scores_sum_is_reasonable(self):
        results = [
            _make_result("a", 1.0, 0.0, 100),   # perfect
            _make_result("b", 0.0, 1.0, 10000), # worst
        ]
        rec = recommend_model(results, priority="balanced")
        assert rec["scores"]["a"] > rec["scores"]["b"]

    def test_single_model_is_recommended(self):
        results = [_make_result("only", 0.8, 0.01, 200)]
        rec = recommend_model(results, priority="balanced")
        assert rec["recommended_model"] == "only"

    def test_empty_results_raises(self):
        with pytest.raises(ValueError):
            recommend_model([], priority="balanced")

    def test_rationale_is_non_empty_string(self):
        results = [
            _make_result("a", 0.9, 0.01, 200),
            _make_result("b", 0.85, 0.005, 150),
        ]
        rec = recommend_model(results, priority="performance")
        assert isinstance(rec["rationale"], str)
        assert len(rec["rationale"]) > 10

    def test_local_model_tagged_in_rationale(self):
        results = [
            _make_result("local-llama", 0.75, 0.0, 800, is_local=True),
            _make_result("cloud-gpt",   0.90, 0.05, 200, is_local=False),
        ]
        rec = recommend_model(results, priority="cost")
        assert rec["recommended_model"] == "local-llama"
        assert "로컬" in rec["rationale"] or "0원" in rec["rationale"]

    def test_all_priority_profiles_defined(self):
        for profile in ("cost", "performance", "balanced"):
            assert profile in PRIORITY_WEIGHTS

    def test_priority_weights_sum_to_one(self):
        for profile, weights in PRIORITY_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 1e-9, f"{profile} weights don't sum to 1: {total}"
