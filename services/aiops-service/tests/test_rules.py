"""Rule engine 단위 테스트 (FR-D4)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from aiops_service.rules import evaluate_rules, _matches, DEFAULT_RULES, RuleMatch


def _make_event(
    event_type: str = "error_rate_spike",
    severity: str = "high",
    agent_id: str | None = None,
    model_id: str | None = None,
) -> MagicMock:
    """AIOpsEvent 모의 객체 생성."""
    ev = MagicMock()
    ev.event_type = event_type
    ev.severity = severity
    ev.agent_id = uuid.UUID(agent_id) if agent_id else uuid.uuid4()
    ev.model_id = model_id
    return ev


# ── _matches ──────────────────────────────────────────────────────────────────

class TestMatches:
    def test_empty_condition_matches_all(self):
        ev = _make_event()
        assert _matches(ev, {}) is True

    def test_event_type_match(self):
        ev = _make_event(event_type="error_rate_spike")
        assert _matches(ev, {"event_types": ["error_rate_spike"]}) is True

    def test_event_type_no_match(self):
        ev = _make_event(event_type="error_rate_spike")
        assert _matches(ev, {"event_types": ["latency_p95_breach"]}) is False

    def test_event_type_multiple_allowed(self):
        ev = _make_event(event_type="cost_budget_breach")
        cond = {"event_types": ["error_rate_spike", "cost_budget_breach"]}
        assert _matches(ev, cond) is True

    def test_severity_match(self):
        ev = _make_event(severity="critical")
        assert _matches(ev, {"severity": ["critical"]}) is True

    def test_severity_no_match(self):
        ev = _make_event(severity="low")
        assert _matches(ev, {"severity": ["high", "critical"]}) is False

    def test_agent_id_match(self):
        agent_id = str(uuid.uuid4())
        ev = _make_event(agent_id=agent_id)
        assert _matches(ev, {"agent_id": agent_id}) is True

    def test_agent_id_no_match(self):
        ev = _make_event()
        other_id = str(uuid.uuid4())
        assert _matches(ev, {"agent_id": other_id}) is False

    def test_agent_id_null_matches_any(self):
        ev = _make_event()
        assert _matches(ev, {"agent_id": None}) is True

    def test_model_id_match(self):
        ev = _make_event(model_id="gpt-4")
        assert _matches(ev, {"model_id": "gpt-4"}) is True

    def test_model_id_no_match(self):
        ev = _make_event(model_id="gpt-4")
        assert _matches(ev, {"model_id": "claude-3"}) is False

    def test_multiple_conditions_all_must_match(self):
        ev = _make_event(event_type="error_rate_spike", severity="high")
        cond = {
            "event_types": ["error_rate_spike"],
            "severity": ["high", "critical"],
        }
        assert _matches(ev, cond) is True

    def test_multiple_conditions_partial_fail(self):
        ev = _make_event(event_type="error_rate_spike", severity="low")
        cond = {
            "event_types": ["error_rate_spike"],
            "severity": ["high", "critical"],
        }
        assert _matches(ev, cond) is False


# ── evaluate_rules ────────────────────────────────────────────────────────────

class TestEvaluateRules:
    def test_no_rules_returns_empty(self):
        ev = _make_event()
        result = evaluate_rules(ev, [])
        assert result == []

    def test_disabled_rule_is_skipped(self):
        ev = _make_event(event_type="error_rate_spike", severity="high")
        rules = [
            {
                "id": "rule-disabled",
                "name": "Disabled Rule",
                "enabled": False,
                "condition": {},
                "action": {"type": "notify", "params": {}},
                "requires_approval": False,
            }
        ]
        assert evaluate_rules(ev, rules) == []

    def test_enabled_rule_with_match(self):
        ev = _make_event(event_type="error_rate_spike", severity="high")
        rules = [
            {
                "id": "rule-001",
                "name": "Error spike notify",
                "enabled": True,
                "condition": {"event_types": ["error_rate_spike"]},
                "action": {"type": "notify", "params": {"channel": "slack"}},
                "requires_approval": False,
            }
        ]
        matches = evaluate_rules(ev, rules)
        assert len(matches) == 1
        assert matches[0].rule_id == "rule-001"
        assert matches[0].action_type == "notify"
        assert matches[0].requires_approval is False

    def test_rule_match_with_approval_required(self):
        ev = _make_event(event_type="error_rate_spike", severity="critical")
        rules = [
            {
                "id": "rule-002",
                "name": "Switch model on critical",
                "enabled": True,
                "condition": {"severity": ["critical"]},
                "action": {"type": "switch_model", "params": {"fallback_model_id": "gpt-3.5"}},
                "requires_approval": True,
            }
        ]
        matches = evaluate_rules(ev, rules)
        assert len(matches) == 1
        assert matches[0].requires_approval is True
        assert matches[0].action_params == {"fallback_model_id": "gpt-3.5"}

    def test_multiple_rules_multiple_matches(self):
        ev = _make_event(event_type="error_rate_spike", severity="critical")
        rules = [
            {
                "id": "r1", "name": "Rule 1", "enabled": True,
                "condition": {"event_types": ["error_rate_spike"]},
                "action": {"type": "notify", "params": {}},
                "requires_approval": False,
            },
            {
                "id": "r2", "name": "Rule 2", "enabled": True,
                "condition": {"severity": ["critical"]},
                "action": {"type": "scale_down", "params": {"target_rps": 5}},
                "requires_approval": True,
            },
        ]
        matches = evaluate_rules(ev, rules)
        assert len(matches) == 2

    def test_rule_without_enabled_defaults_to_true(self):
        """enabled 필드 누락 시 기본값 True로 동작."""
        ev = _make_event()
        rules = [
            {
                "id": "r-no-enabled", "name": "Rule",
                # no 'enabled' key
                "condition": {},
                "action": {"type": "notify", "params": {}},
                "requires_approval": False,
            }
        ]
        matches = evaluate_rules(ev, rules)
        assert len(matches) == 1

    def test_no_matching_condition(self):
        ev = _make_event(event_type="cost_budget_breach", severity="low")
        rules = [
            {
                "id": "r-no-match", "name": "No Match Rule", "enabled": True,
                "condition": {"event_types": ["error_rate_spike"], "severity": ["high"]},
                "action": {"type": "notify", "params": {}},
                "requires_approval": False,
            }
        ]
        matches = evaluate_rules(ev, rules)
        assert matches == []


# ── DEFAULT_RULES ──────────────────────────────────────────────────────────────

class TestDefaultRules:
    def test_critical_event_triggers_notify_rule(self):
        ev = _make_event(event_type="error_rate_spike", severity="critical")
        matches = evaluate_rules(ev, DEFAULT_RULES)
        auto = [m for m in matches if not m.requires_approval]
        assert any(m.action_type == "notify" for m in auto)

    def test_latency_breach_triggers_notify(self):
        ev = _make_event(event_type="latency_p95_breach", severity="medium")
        matches = evaluate_rules(ev, DEFAULT_RULES)
        assert any(m.action_type == "notify" for m in matches)

    def test_fallback_rule_disabled_by_default(self):
        """auto-fallback-high-error 규칙은 기본적으로 disabled."""
        ev = _make_event(event_type="error_rate_spike", severity="high")
        matches = evaluate_rules(ev, DEFAULT_RULES)
        # switch_model action should NOT appear because the rule is disabled
        assert not any(m.action_type == "switch_model" for m in matches)

    def test_low_severity_event_no_critical_match(self):
        ev = _make_event(event_type="tool_call_failure_spike", severity="low")
        matches = evaluate_rules(ev, DEFAULT_RULES)
        # critical notify rule should not fire for low severity
        critical_notify = [m for m in matches if m.rule_id == "auto-notify-critical"]
        assert len(critical_notify) == 0
