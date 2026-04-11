import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProviderName(str, enum.Enum):
    anthropic = "anthropic"
    openai = "openai"
    gemini = "gemini"
    grok = "grok"
    mistral = "mistral"
    cohere = "cohere"
    deepseek = "deepseek"
    together = "together"


class AIProvider(TimestampMixin, Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        Index("ix_ai_providers_user_id", "user_id"),
        Index("ix_ai_providers_user_id_status", "user_id", "status"),
        Index("uq_ai_providers_user_provider", "user_id", "provider_name", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_name: Mapped[ProviderName] = mapped_column(Enum(ProviderName), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", server_default="active")
