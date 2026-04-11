import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CoherenceReport(TimestampMixin, Base):
    __tablename__ = "coherence_reports"
    __table_args__ = (
        Index("ix_coherence_reports_build_id", "build_id"),
    )

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE"), nullable=False
    )
    critical_errors: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    auto_fixes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    report_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
