import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SandboxStatus(str, enum.Enum):
    warm = "warm"
    claimed = "claimed"
    building = "building"
    stopping = "stopping"
    stopped = "stopped"
    error = "error"


class Sandbox(TimestampMixin, Base):
    __tablename__ = "sandboxes"
    __table_args__ = (
        Index("ix_sandboxes_project_id", "project_id"),
        Index("ix_sandboxes_status", "status"),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[SandboxStatus] = mapped_column(
        Enum(SandboxStatus), default=SandboxStatus.warm, server_default="warm"
    )
    northflank_service_id: Mapped[str | None] = mapped_column(String, nullable=True)
