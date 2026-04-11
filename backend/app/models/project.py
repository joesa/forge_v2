import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    building = "building"
    live = "live"
    error = "error"
    archived = "archived"


class Framework(str, enum.Enum):
    nextjs = "nextjs"
    vite_react = "vite_react"
    fastapi = "fastapi"
    django = "django"
    express = "express"


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_id", "user_id"),
        Index("ix_projects_user_id_status", "user_id", "status"),
        Index("ix_projects_user_id_status_updated", "user_id", "status", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.draft, server_default="draft"
    )
    framework: Mapped[Framework] = mapped_column(Enum(Framework), nullable=False)
