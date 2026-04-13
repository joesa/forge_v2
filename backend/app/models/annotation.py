import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Annotation(TimestampMixin, Base):
    __tablename__ = "annotations"
    __table_args__ = (
        Index("ix_annotations_project_id", "project_id"),
        Index("ix_annotations_user_id", "user_id"),
        Index("ix_annotations_editor_session_id", "editor_session_id"),
        Index("ix_annotations_user_id_status", "user_id", "status"),
        Index("ix_annotations_resolved", "resolved"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    editor_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editor_sessions.id", ondelete="CASCADE"), nullable=True
    )
    css_selector: Mapped[str] = mapped_column(String, nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    x_pct: Mapped[float] = mapped_column(Float, nullable=False)
    y_pct: Mapped[float] = mapped_column(Float, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String, default="active", server_default="active")
