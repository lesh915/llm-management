"""Anomaly detection engine (FR-D2).

Detects four event types by querying TimescaleDB ops_metrics:
    error_rate_spike      — recent error_rate exceeds baseline by threshold %p
    latency_p95_breach    — recent latency_p95 exceeds configured ceiling
    cost_budget_breach    — projected 24h cost exceeds budget limit (USD)
    tool_call_failure     — tool_call_failure_rate delta exceeds threshold

Each detector returns an AIOpsEventCreate if anomalous, else None.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AIOpsEventCreate:
    agent_id: str
    model_id: str
    event_type: str
    severity: str       # low | medium | high | critical
    description: str


class AnomalyDetector:
    # Configurable via env vars or constructor kwargs
    DEFAULT_CONFIG = {
        "error_rate_spike_delta":     5.0,   # %p change triggers alert
        "latency_p95_ceiling_ms":     5000,  # absolute ceiling in ms
        "cost_budget_usd_daily":      50.0,  # projected 24h cost cap
        "tool_failure_delta":         3.0,   # %p change
        "short_window_minutes":       5,
        "long_window_minutes":        60,
    }

    def __init__(self, **overrides):
        self.cfg = {**self.DEFAULT_CONFIG, **overrides}

    async def check_all(
        self,
        agent_id: str,
        model_id: str,
        db: AsyncSession,
    ) -> list[AIOpsEventCreate]:
        events: list[AIOpsEventCreate] = []

        for detector in (
            self._check_error_rate_spike,
            self._check_latency_breach,
            self._check_cost_budget,
            self._check_tool_failure,
        ):
            try:
                event = await detector(agent_id, model_id, db)
                if event:
                    events.append(event)
            except Exception:
                pass   # individual detector failures must not block others

        return events

    # ── Detectors ─────────────────────────────────────────────────────────────

    async def _check_error_rate_spike(
        self, agent_id: str, model_id: str, db: AsyncSession
    ) -> AIOpsEventCreate | None:
        short = await self._avg_metric(
            db, agent_id, model_id, "error_rate",
            self.cfg["short_window_minutes"]
        )
        baseline = await self._avg_metric(
            db, agent_id, model_id, "error_rate",
            self.cfg["long_window_minutes"]
        )
        delta = short - baseline
        if delta >= self.cfg["error_rate_spike_delta"]:
            return AIOpsEventCreate(
                agent_id=agent_id,
                model_id=model_id,
                event_type="error_rate_spike",
                severity="high" if delta >= 10 else "medium",
                description=(
                    f"오류율이 {delta:.1f}%p 급증했습니다. "
                    f"현재: {short:.1f}%, 기준선: {baseline:.1f}%"
                ),
            )
        return None

    async def _check_latency_breach(
        self, agent_id: str, model_id: str, db: AsyncSession
    ) -> AIOpsEventCreate | None:
        current = await self._avg_metric(
            db, agent_id, model_id, "latency_p95",
            self.cfg["short_window_minutes"]
        )
        ceiling = self.cfg["latency_p95_ceiling_ms"]
        if current > ceiling:
            return AIOpsEventCreate(
                agent_id=agent_id,
                model_id=model_id,
                event_type="latency_p95_breach",
                severity="critical" if current > ceiling * 2 else "high",
                description=(
                    f"레이턴시 P95가 임계치를 초과했습니다. "
                    f"현재: {current:.0f}ms, 임계치: {ceiling}ms"
                ),
            )
        return None

    async def _check_cost_budget(
        self, agent_id: str, model_id: str, db: AsyncSession
    ) -> AIOpsEventCreate | None:
        # Sum cost over last 1h → project to 24h
        hourly_cost = await self._sum_metric(
            db, agent_id, model_id, "cost_usd", window_minutes=60
        )
        projected_daily = hourly_cost * 24
        budget = self.cfg["cost_budget_usd_daily"]
        if projected_daily > budget:
            return AIOpsEventCreate(
                agent_id=agent_id,
                model_id=model_id,
                event_type="cost_budget_breach",
                severity="high",
                description=(
                    f"24시간 예상 비용이 예산을 초과합니다. "
                    f"예상: ${projected_daily:.2f}, 예산: ${budget:.2f}"
                ),
            )
        return None

    async def _check_tool_failure(
        self, agent_id: str, model_id: str, db: AsyncSession
    ) -> AIOpsEventCreate | None:
        short = await self._avg_metric(
            db, agent_id, model_id, "tool_call_failure_rate",
            self.cfg["short_window_minutes"]
        )
        baseline = await self._avg_metric(
            db, agent_id, model_id, "tool_call_failure_rate",
            self.cfg["long_window_minutes"]
        )
        delta = short - baseline
        if delta >= self.cfg["tool_failure_delta"]:
            return AIOpsEventCreate(
                agent_id=agent_id,
                model_id=model_id,
                event_type="tool_call_failure_spike",
                severity="high",
                description=(
                    f"도구 호출 실패율이 {delta:.1f}%p 급증했습니다. "
                    f"현재: {short:.1f}%, 기준선: {baseline:.1f}%"
                ),
            )
        return None

    # ── TimescaleDB helpers ───────────────────────────────────────────────────

    async def _avg_metric(
        self,
        db: AsyncSession,
        agent_id: str,
        model_id: str,
        metric_name: str,
        window_minutes: int,
    ) -> float:
        result = await db.execute(
            text("""
                SELECT COALESCE(AVG(value), 0)
                FROM ops_metrics
                WHERE agent_id  = :agent_id
                  AND model_id  = :model_id
                  AND metric_name = :metric_name
                  AND time >= NOW() - INTERVAL ':window minutes'
            """),
            {"agent_id": agent_id, "model_id": model_id,
             "metric_name": metric_name, "window": window_minutes},
        )
        row = result.fetchone()
        return float(row[0]) if row else 0.0

    async def _sum_metric(
        self,
        db: AsyncSession,
        agent_id: str,
        model_id: str,
        metric_name: str,
        window_minutes: int,
    ) -> float:
        result = await db.execute(
            text("""
                SELECT COALESCE(SUM(value), 0)
                FROM ops_metrics
                WHERE agent_id  = :agent_id
                  AND model_id  = :model_id
                  AND metric_name = :metric_name
                  AND time >= NOW() - INTERVAL ':window minutes'
            """),
            {"agent_id": agent_id, "model_id": model_id,
             "metric_name": metric_name, "window": window_minutes},
        )
        row = result.fetchone()
        return float(row[0]) if row else 0.0
