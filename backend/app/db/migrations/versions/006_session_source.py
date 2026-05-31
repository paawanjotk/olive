"""sessions: add source column for channel-origin filtering

Revision ID: 006_session_source
Revises: 005_workflow_schedules
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "006_session_source"
down_revision = "005_workflow_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="web",
        ),
    )
    op.create_index("ix_sessions_source", "sessions", ["source"])


def downgrade() -> None:
    op.drop_index("ix_sessions_source", table_name="sessions")
    op.drop_column("sessions", "source")
