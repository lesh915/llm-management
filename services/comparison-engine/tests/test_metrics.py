"""Unit tests for the metrics calculation module."""
import pytest
from comparison_engine.metrics import (
    EvalCase, ModelOutput,
    calculate_metrics,
    _correctness, _tool_call_accuracy, _percentile,
    _failure_rate, _normalize_text,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_outputs(contents: list, latencies: list | None = None) -> list[ModelOutput]:
    lats = latencies or [100.0] * len(contents)
    return [
        ModelOutput(
            case_id=f"case-{i:03d}",
            content=c,
            input_tokens=50,
            output_tokens=20,
            latency_ms=lat,
        )
        for i, (c, lat) in enumerate(zip(contents, lats))
    ]


def make_cases(expected: list) -> list[EvalCase]:
    return [
        EvalCase(
            id=f"case-{i:03d}",
            input_messages=[{"role": "user", "content": "q"}],
            expected_output=e,
        )
        for i, e in enumerate(expected)
    ]


# ── Correctness ───────────────────────────────────────────────────────────────

class TestCorrectness:
    def test_all_correct(self):
        outputs = make_outputs(["Answer 0", "Answer 1", "Answer 2"])
        cases   = make_cases(["Answer 0", "Answer 1", "Answer 2"])
        assert _correctness(outputs, {c.id: c for c in cases}) == 1.0

    def test_none_correct(self):
        outputs = make_outputs(["Wrong", "Wrong", "Wrong"])
        cases   = make_cases(["Right", "Right", "Right"])
        assert _correctness(outputs, {c.id: c for c in cases}) == 0.0

    def test_partial_correct(self):
        outputs = make_outputs(["A", "B", "C"])
        cases   = make_cases(["A", "X", "C"])
        assert _correctness(outputs, {c.id: c for c in cases}) == pytest.approx(2 / 3)

    def test_case_insensitive_match(self):
        outputs = make_outputs(["hello world"])
        cases   = make_cases(["HELLO WORLD"])
        assert _correctness(outputs, {c.id: c for c in cases}) == 1.0

    def test_empty_outputs(self):
        assert _correctness([], {}) == 0.0


# ── Tool call accuracy ────────────────────────────────────────────────────────

class TestToolCallAccuracy:
    def test_exact_match(self):
        outputs = [ModelOutput(
            case_id="case-000",
            content=[{"type": "tool_use", "name": "search",
                       "input": {"query": "hello"}}],
            input_tokens=10, output_tokens=5, latency_ms=50,
        )]
        cases = [EvalCase(
            id="case-000",
            input_messages=[],
            expected_tool_calls=[{"name": "search", "arguments": {"query": "hello"}}],
        )]
        result = _tool_call_accuracy(outputs, {c.id: c for c in cases})
        assert result == 1.0

    def test_wrong_tool_name(self):
        outputs = [ModelOutput(
            case_id="case-000",
            content=[{"type": "tool_use", "name": "other", "input": {}}],
            input_tokens=10, output_tokens=5, latency_ms=50,
        )]
        cases = [EvalCase(
            id="case-000", input_messages=[],
            expected_tool_calls=[{"name": "search", "arguments": {}}],
        )]
        assert _tool_call_accuracy(outputs, {c.id: c for c in cases}) == 0.0

    def test_no_tool_calls_when_expected(self):
        outputs = [ModelOutput(
            case_id="case-000", content="plain text",
            input_tokens=10, output_tokens=5, latency_ms=50,
        )]
        cases = [EvalCase(
            id="case-000", input_messages=[],
            expected_tool_calls=[{"name": "search", "arguments": {}}],
        )]
        assert _tool_call_accuracy(outputs, {c.id: c for c in cases}) == 0.0


# ── Percentile ────────────────────────────────────────────────────────────────

class TestPercentile:
    def test_p95_simple(self):
        values = list(range(1, 101))  # 1..100
        # p95 index = int(100 * 0.95) - 1 = 94 → value 95
        assert _percentile(values, 95) == 95

    def test_p50_median(self):
        values = [10, 20, 30, 40, 50]
        assert _percentile(values, 50) == 30


# ── Failure rate ──────────────────────────────────────────────────────────────

class TestFailureRate:
    def test_no_failures(self):
        outputs = make_outputs(["a", "b", "c"])
        assert _failure_rate(outputs) == 0.0

    def test_all_failed(self):
        outputs = [
            ModelOutput(case_id=f"case-{i:03d}", content="",
                        input_tokens=0, output_tokens=0, latency_ms=0,
                        error="timeout")
            for i in range(3)
        ]
        assert _failure_rate(outputs) == 1.0

    def test_partial_failure(self):
        outputs = make_outputs(["ok", "ok"])
        outputs[0].error = "err"
        assert _failure_rate(outputs) == 0.5


# ── calculate_metrics integration ────────────────────────────────────────────

class TestCalculateMetrics:
    def test_returns_requested_metrics_only(self):
        outputs = make_outputs(["A", "B"])
        cases   = make_cases(["A", "B"])
        result = calculate_metrics(
            outputs, cases,
            ["correctness", "latency_p95"],
            pricing={},
        )
        assert "correctness" in result
        assert "latency_p95" in result
        assert "tool_call_accuracy" not in result

    def test_cost_per_query_local_model(self):
        outputs = make_outputs(["a"])
        cases   = make_cases(["a"])
        result = calculate_metrics(
            outputs, cases,
            ["cost_per_query"],
            pricing={"input_per_1m_tokens": 0.0, "output_per_1m_tokens": 0.0},
        )
        assert result["cost_per_query"] == 0.0

    def test_cost_per_query_cloud_model(self):
        outputs = [ModelOutput(
            case_id="case-000", content="a",
            input_tokens=1_000_000, output_tokens=0,
            latency_ms=100,
        )]
        cases = make_cases(["a"])
        result = calculate_metrics(
            outputs, cases,
            ["cost_per_query"],
            pricing={"input_per_1m_tokens": 3.0, "output_per_1m_tokens": 0.0},
        )
        assert result["cost_per_query"] == pytest.approx(3.0)
