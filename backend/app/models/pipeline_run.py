import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PipelineStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PipelineRun(TimestampMixin, Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_project_id", "project_id"),
        Index("ix_pipeline_runs_user_id", "user_id"),
        Index("ix_pipeline_runs_user_id_status", "user_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus), default=PipelineStatus.pending, server_default="pending"
    )
    current_stage: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    idea_spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
