"""Per-request model usage, for cost ceilings and debugging."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class LLMUsageRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "llm_usage_records"
    __table_args__ = (
        Index("ix_usage_org_created", "organization_id", "created_at"),
        Index("ix_usage_meeting", "meeting_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE")
    )
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE")
    )

    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64))

    request_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: The part of input_tokens the provider served from its prompt cache.
    #: Billed at a fraction of fresh input, so cost cannot be computed
    #: honestly without it.
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
