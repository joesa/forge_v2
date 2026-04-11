import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentOutput(TimestampMixin, Base):
    __tablename__ = "agent_outputs"
    __table_args__ = (
        Index("ix_agent_outputs_pipeline_run_id", "pipeline_run_id"),
    )

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    output_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    gate_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
