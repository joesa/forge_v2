import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AccessibilityReport(TimestampMixin, Base):
    __tablename__ = "accessibility_reports"
    __table_args__ = (
        Index("ix_accessibility_reports_build_id", "build_id"),
    )

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE"), nullable=False
    )
    route: Mapped[str] = mapped_column(String, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    serious_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    violations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
