import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPConnection(Base):
    """Stores an OAuth access token for a third-party MCP provider (GitHub, Notion)
    on behalf of a user. One row per (user, provider) pair."""

    __tablename__ = "mcp_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # "github" | "notion"
    access_token: Mapped[str] = mapped_column(sa.Text, nullable=False)
    token_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, server_default="bearer")
    scope: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # provider-specific metadata: username, workspace_name, login, etc.
    meta: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default=sa.text("'{}'"))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "provider", name="uq_mcp_user_provider"),
    )

    def __repr__(self) -> str:
        return f"<MCPConnection user={self.user_id} provider={self.provider} active={self.is_active}>"
