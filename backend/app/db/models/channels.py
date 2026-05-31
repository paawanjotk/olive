import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChannelBinding(Base):
    """Maps an external messaging surface (e.g. a Telegram chat) to either a
    single agent or a whole workflow. openclaw-style channel binding: an inbound
    message is resolved to its target by (platform, external_id)."""

    __tablename__ = "channel_bindings"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    platform: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # "telegram"
    # External conversation id on the platform (e.g. Telegram chat_id).
    external_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    # Target: exactly one of agent_id / workflow_id is set.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True,
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=True,
    )
    # Platform-specific config (bot token ref, parse mode, etc.).
    config: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default=sa.text("'{}'"))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.UniqueConstraint("platform", "external_id", name="uq_channel_platform_external"),
    )

    def __repr__(self) -> str:
        return f"<ChannelBinding {self.platform}:{self.external_id} → agent={self.agent_id} wf={self.workflow_id}>"
