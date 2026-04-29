"""Unit tests for cost calculation."""
import pytest
from comparison_engine.cost import calculate_cost, estimate_task_cost, total_task_cost


class TestCalculateCost:
    def test_cloud_model_cost(self):
        pricing = {"input_per_1m_tokens": 3.0, "output_per_1m_tokens": 15.0}
        usage   = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
        assert calculate_cost(pricing, usage) == pytest.approx(18.0)

    def test_local_model_zero_cost(self):
        pricing = {"input_per_1m_tokens": 0.0, "output_per_1m_tokens": 0.0}
        usage   = {"input_tokens": 500_000, "output_tokens": 200_000}
        assert calculate_cost(pricing, usage) == 0.0

    def test_input_only_cost(self):
        pricing = {"input_per_1m_tokens": 1.0, "output_per_1m_tokens": 0.0}
        usage   = {"input_tokens": 500_000, "output_tokens": 0}
        assert calculate_cost(pricing, usage) == pytest.approx(0.5)

    def test_missing_pricing_keys_default_to_zero(self):
        assert calculate_cost({}, {"input_tokens": 1_000_000, "output_tokens": 1_000_000}) == 0.0


class TestEstimateTaskCost:
    def test_estimates_cloud_and_local(self):
        pricings = {
            "claude-sonnet": {"input_per_1m_tokens": 3.0, "output_per_1m_tokens": 15.0},
            "ollama/llama":  {"input_per_1m_tokens": 0.0, "output_per_1m_tokens": 0.0},
        }
        estimates = estimate_task_cost(pricings, dataset_size=100,
                                        avg_input_tokens=500, avg_output_tokens=200)
        assert estimates["ollama/llama"] == 0.0
        assert estimates["claude-sonnet"] > 0.0

    def test_total_excludes_local(self):
        pricings = {
            "cloud": {"input_per_1m_tokens": 3.0, "output_per_1m_tokens": 0.0},
            "local": {"input_per_1m_tokens": 0.0, "output_per_1m_tokens": 0.0},
        }
        estimates = estimate_task_cost(pricings, dataset_size=10)
        total = total_task_cost(estimates)
        assert total == estimates["cloud"]
