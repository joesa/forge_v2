import uuid

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    plan: Mapped[str] = mapped_column(String, default="free", server_default="free")
    token_limit: Mapped[int] = mapped_column(Integer, default=10000, server_default="10000")
