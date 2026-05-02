"""SQLAlchemy ORM models — shared across all services."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    artifacts: Mapped[list[AgentArtifact]] = relationship("AgentArtifact", back_populates="agent")


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)   # prompt|mcp|skill|tool_schema
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model_requirements: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped[Agent] = relationship("Agent", back_populates="artifacts")
    variants: Mapped[list[ModelVariant]] = relationship("ModelVariant", back_populates="artifact")


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    family: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[str | None] = mapped_column(String(50))
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False)
    characteristics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pricing: Mapped[dict] = mapped_column(JSONB, nullable=False)
    api_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVariant(Base):
    __tablename__ = "model_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    artifact: Mapped[AgentArtifact] = relationship("AgentArtifact", back_populates="variants")


class ComparisonTask(Base):
    __tablename__ = "comparison_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_artifacts.id")
    )
    model_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    results: Mapped[list[ComparisonResult]] = relationship("ComparisonResult", back_populates="task")


class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_outputs: Mapped[list | None] = mapped_column(JSONB)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[ComparisonTask] = relationship("ComparisonTask", back_populates="results")


class OpsMetric(Base):
    __tablename__ = "ops_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)


class AIOpsEvent(Base):
    __tablename__ = "aiops_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    model_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("model_registry.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
