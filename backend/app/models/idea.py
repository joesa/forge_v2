import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Idea(TimestampMixin, Base):
    __tablename__ = "ideas"
    __table_args__ = (
        Index("ix_ideas_idea_session_id", "idea_session_id"),
        Index("ix_ideas_user_id", "user_id"),
        Index("ix_ideas_user_id_status", "user_id", "status"),
    )

    idea_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("idea_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tech_stack: Mapped[dict] = mapped_column(JSONB, nullable=False)
    market_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String, default="active", server_default="active")
