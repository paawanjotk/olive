"""mcp_connections table for OAuth token storage

Revision ID: 007_mcp_connections
Revises: 006_session_source
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "007_mcp_connections"
down_revision = "006_session_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_connections",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("token_type", sa.String(50), nullable=False, server_default="bearer"),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("meta", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "provider", name="uq_mcp_user_provider"),
    )
    op.create_index("ix_mcp_connections_user_id", "mcp_connections", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_connections_user_id", table_name="mcp_connections")
    op.drop_table("mcp_connections")
