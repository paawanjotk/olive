"""agents table

Revision ID: 002_agents_table
Revises: 001_initial_schema
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_agents_table"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("role", sa.String(100), server_default="assistant", nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), server_default="claude-sonnet-4-6", nullable=False),
        sa.Column("provider", sa.String(50), server_default="anthropic", nullable=False),
        sa.Column("temperature", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default="8096", nullable=False),
        sa.Column("max_iterations", sa.Integer(), server_default="5", nullable=False),
        sa.Column("tools", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("soul_md", sa.Text(), nullable=True),
        # Flexible UI/display metadata: avatar_emoji, avatar_color, tags, etc.
        sa.Column("meta", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_is_active", "agents", ["is_active"])
    op.create_index("ix_agents_created_at", "agents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agents_created_at", table_name="agents")
    op.drop_index("ix_agents_is_active", table_name="agents")
    op.drop_table("agents")
