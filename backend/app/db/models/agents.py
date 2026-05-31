import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    role: Mapped[str] = mapped_column(sa.String(100), nullable=False, server_default="assistant")
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model: Mapped[str] = mapped_column(sa.String(100), nullable=False, server_default="claude-sonnet-4-6")
    provider: Mapped[str] = mapped_column(sa.String(50), nullable=False, server_default="anthropic")
    temperature: Mapped[float] = mapped_column(sa.Float, nullable=False, server_default="0.7")
    max_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="8096")
    max_iterations: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="5")
    # JSON array of tool names e.g. ["web_search", "calculator"]
    tools: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    soul_md: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # openclaw-style persistent memory: the agent's MEMORY.md, loaded at the
    # start of every run and appended to as it learns durable facts.
    memory_md: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Guardrails: caps + approval policy. Kept as JSON so new guardrail types
    # (rate limits, blocked tools, content filters) never need a migration.
    # Shape: {"require_approval": bool, "max_cost_usd": float|None, ...}
    guardrails: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default=sa.text("'{}'"))
    # Flexible display/UI metadata: avatar_emoji, avatar_color, tags, etc.
    # Kept out of typed columns so adding new display props never needs a migration.
    meta: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r} role={self.role!r}>"
