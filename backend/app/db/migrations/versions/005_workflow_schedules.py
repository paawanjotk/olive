"""workflow_schedules table

Revision ID: 005_workflow_schedules
Revises: 004_workflow_orchestration
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "005_workflow_schedules"
down_revision = "004_workflow_orchestration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_schedules",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False, server_default="Schedule"),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("repeat_minutes", sa.Integer(), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_schedules_workflow_id", "workflow_schedules", ["workflow_id"])
    op.create_index("ix_workflow_schedules_user_id", "workflow_schedules", ["user_id"])
    op.create_index("ix_workflow_schedules_next_run_at", "workflow_schedules", ["next_run_at"])


def downgrade() -> None:
    op.drop_table("workflow_schedules")
