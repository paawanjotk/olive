"""agents: add user_id for per-user isolation

Revision ID: 003_agents_add_user_id
Revises: 002_agents_table
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "003_agents_add_user_id"
down_revision = "002_agents_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable first — existing rows have no owner so we wipe them.
    op.add_column("agents", sa.Column("user_id", sa.UUID(as_uuid=True), nullable=True))

    # Purge ownerless agents (all existing rows in dev).
    op.execute("DELETE FROM agents WHERE user_id IS NULL")

    # Enforce not-null + FK now that the table is clean.
    op.alter_column("agents", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_agents_user_id", "agents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_user_id", table_name="agents")
    op.drop_constraint("fk_agents_user_id", "agents", type_="foreignkey")
    op.drop_column("agents", "user_id")
