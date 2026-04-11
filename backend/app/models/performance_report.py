import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PerformanceReport(TimestampMixin, Base):
    __tablename__ = "performance_reports"
    __table_args__ = (
        Index("ix_performance_reports_build_id", "build_id"),
    )

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE"), nullable=False
    )
    route: Mapped[str] = mapped_column(String, nullable=False)
    lcp_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    cls: Mapped[float | None] = mapped_column(Float, nullable=True)
    fid_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    bundle_kb: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
