import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EditorSession(TimestampMixin, Base):
    __tablename__ = "editor_sessions"
    __table_args__ = (
        Index("ix_editor_sessions_project_id", "project_id"),
        Index("ix_editor_sessions_user_id", "user_id"),
        Index("ix_editor_sessions_sandbox_id", "sandbox_id"),
        Index("ix_editor_sessions_user_id_status", "user_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sandboxes.id", ondelete="CASCADE"), nullable=True
    )
    last_active_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(default="active", server_default="active")
