"""workflow orchestration + openclaw agent identity

Adds the workflow engine tables (workflows, workflow_executions,
workflow_steps, execution_events), channel_bindings for messaging, and
openclaw-style agent identity fields (memory_md, guardrails).

Revision ID: 004_workflow_orchestration
Revises: 003_agents_add_user_id
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "004_workflow_orchestration"
down_revision = "003_agents_add_user_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Agent identity fields (openclaw) ─────────────────────────────────────
    op.add_column("agents", sa.Column("memory_md", sa.Text(), nullable=True))
    op.add_column(
        "agents",
        sa.Column("guardrails", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    # ── workflows ────────────────────────────────────────────────────────────
    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])

    # ── workflow_executions ──────────────────────────────────────────────────
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("trigger_type", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("trigger_context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("input_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
    op.create_index("ix_workflow_executions_user_id", "workflow_executions", ["user_id"])

    # ── workflow_steps ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("input", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_steps_execution_id", "workflow_steps", ["execution_id"])

    # ── execution_events ───────────────────────────────────────────────────────
    op.create_table(
        "execution_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_execution_events_execution_id", "execution_events", ["execution_id"])

    # ── channel_bindings ─────────────────────────────────────────────────────
    op.create_table(
        "channel_bindings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("platform", "external_id", name="uq_channel_platform_external"),
    )
    op.create_index("ix_channel_bindings_user_id", "channel_bindings", ["user_id"])
    op.create_index("ix_channel_bindings_external_id", "channel_bindings", ["external_id"])


def downgrade() -> None:
    op.drop_table("channel_bindings")
    op.drop_table("execution_events")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_executions")
    op.drop_table("workflows")
    op.drop_column("agents", "guardrails")
    op.drop_column("agents", "memory_md")
