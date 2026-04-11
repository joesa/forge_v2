import uuid

from sqlalchemy import Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class IdeaSession(TimestampMixin, Base):
    __tablename__ = "idea_sessions"
    __table_args__ = (
        Index("ix_idea_sessions_user_id", "user_id"),
        Index("ix_idea_sessions_user_id_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    questionnaire_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(default="active", server_default="active")
