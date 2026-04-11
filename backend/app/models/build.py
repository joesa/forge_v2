import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BuildStatus(str, enum.Enum):
    pending = "pending"
    building = "building"
    success = "success"
    failed = "failed"


class Build(TimestampMixin, Base):
    __tablename__ = "builds"
    __table_args__ = (
        Index("ix_builds_project_id", "project_id"),
        Index("ix_builds_user_id", "user_id"),
        Index("ix_builds_pipeline_run_id", "pipeline_run_id"),
        Index("ix_builds_project_id_status", "project_id", "status"),
        Index("ix_builds_user_id_status", "user_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[BuildStatus] = mapped_column(
        Enum(BuildStatus), default=BuildStatus.pending, server_default="pending"
    )
    gate_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_files_key: Mapped[str | None] = mapped_column(String, nullable=True)
