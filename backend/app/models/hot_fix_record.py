import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HotFixRecord(TimestampMixin, Base):
    __tablename__ = "hot_fix_records"
    __table_args__ = (
        Index("ix_hot_fix_records_build_id", "build_id"),
    )

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE"), nullable=False
    )
    failed_gate: Mapped[str] = mapped_column(String, nullable=False)
    failing_file: Mapped[str] = mapped_column(String, nullable=False)
    fix_applied: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
