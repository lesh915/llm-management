"""Initial schema — all core tables.

Revision ID: 001
Revises:
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agent_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("model_requirements", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('prompt','mcp','skill','tool_schema')", name="ck_artifact_type"),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("family", sa.String(100)),
        sa.Column("version", sa.String(50)),
        sa.Column("capabilities", JSONB, nullable=False),
        sa.Column("characteristics", JSONB, nullable=False),
        sa.Column("pricing", JSONB, nullable=False),
        sa.Column("api_config", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'active'"),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deprecated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','deprecated','retired')", name="ck_model_status"),
    )

    op.create_table(
        "model_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("artifact_id", UUID(as_uuid=True), sa.ForeignKey("agent_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(100), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("artifact_id", "model_id", name="uq_variant_artifact_model"),
    )

    op.create_table(
        "comparison_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("artifact_id", UUID(as_uuid=True), sa.ForeignKey("agent_artifacts.id")),
        sa.Column("model_ids", ARRAY(sa.String), nullable=False),
        sa.Column("dataset_id", sa.String(255), nullable=False),
        sa.Column("metrics", ARRAY(sa.String), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "comparison_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(100), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("raw_outputs", JSONB),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aiops_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("model_id", sa.String(100), sa.ForeignKey("model_registry.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20)),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="'open'"),
        sa.Column("actions", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # TimescaleDB hypertable for ops_metrics
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops_metrics (
            time        TIMESTAMPTZ NOT NULL,
            agent_id    UUID        NOT NULL,
            model_id    VARCHAR(100) NOT NULL,
            metric_name VARCHAR(100) NOT NULL,
            value       DOUBLE PRECISION NOT NULL
        )
    """)
    op.execute("SELECT create_hypertable('ops_metrics', 'time', if_not_exists => TRUE)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ops_metrics ON ops_metrics (agent_id, metric_name, time DESC)")


def downgrade() -> None:
    for table in [
        "ops_metrics", "aiops_events", "comparison_results",
        "comparison_tasks", "model_variants", "model_registry",
        "agent_artifacts", "agents",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
