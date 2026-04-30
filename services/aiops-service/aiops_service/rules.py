"""Automation rule engine (FR-D4).

Rules are stored in-DB as JSON and evaluated against incoming AIOps events.
A rule defines: condition metric thresholds + action to execute automatically
(if requires_approval=False) or propose to the user (if requires_approval=True).

Rule schema:
    {
        "name": str,
        "condition": {
            "event_types": ["error_rate_spike", ...],   # match any
            "severity":    ["high", "critical"],         # match any
            "agent_id":    str | null,                   # null = all agents
            "model_id":    str | null,
        },
        "action": {
            "type": "switch_model" | "rollback" | "notify" | "scale_down",
            "params": {...}     # action-type-specific
        },
        "requires_approval": bool,
        "enabled": bool
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from shared_types.models import AIOpsEvent


@dataclass
class RuleMatch:
    rule_id: str
    rule_name: str
    action_type: str
    action_params: dict
    requires_approval: bool


def evaluate_rules(
    event: AIOpsEvent,
    rules: list[dict],
) -> list[RuleMatch]:
    """
    Return all rules that match the given AIOps event.
    Rules without 'enabled: true' are silently skipped.
    """
    matches: list[RuleMatch] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        if _matches(event, rule.get("condition", {})):
            matches.append(RuleMatch(
                rule_id=rule.get("id", ""),
                rule_name=rule.get("name", ""),
                action_type=rule["action"]["type"],
                action_params=rule["action"].get("params", {}),
                requires_approval=rule.get("requires_approval", True),
            ))
    return matches


def _matches(event: AIOpsEvent, condition: dict) -> bool:
    """True when ALL specified condition fields match the event."""
    # event_types filter
    allowed_types = condition.get("event_types")
    if allowed_types and event.event_type not in allowed_types:
        return False

    # severity filter
    allowed_severities = condition.get("severity")
    if allowed_severities and event.severity not in allowed_severities:
        return False

    # agent_id filter (None = any)
    target_agent = condition.get("agent_id")
    if target_agent and str(event.agent_id) != target_agent:
        return False

    # model_id filter
    target_model = condition.get("model_id")
    if target_model and event.model_id != target_model:
        return False

    return True


# ── Built-in default rules ────────────────────────────────────────────────────

DEFAULT_RULES: list[dict] = [
    {
        "id": "auto-notify-critical",
        "name": "critical 이벤트 자동 알림",
        "enabled": True,
        "condition": {"severity": ["critical"]},
        "action": {"type": "notify", "params": {"channel": "default"}},
        "requires_approval": False,
    },
    {
        "id": "auto-fallback-high-error",
        "name": "오류율 급증 시 폴백 모델 전환",
        "enabled": False,   # disabled until fallback_model configured
        "condition": {
            "event_types": ["error_rate_spike"],
            "severity": ["high", "critical"],
        },
        "action": {
            "type": "switch_model",
            "params": {"fallback_model_id": ""},  # fill in per deployment
        },
        "requires_approval": True,   # human approval before switching
    },
    {
        "id": "auto-scale-latency",
        "name": "레이턴시 초과 시 scale-down 제안",
        "enabled": True,
        "condition": {"event_types": ["latency_p95_breach"]},
        "action": {"type": "notify",
                   "params": {"message": "레이턴시 임계치 초과 — 부하 점검 권장"}},
        "requires_approval": False,
    },
]
