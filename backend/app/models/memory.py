"""Company memory: individually provenance-tagged facts about the business."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import FactSource


class CompanyMemory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """One durable fact, never silently promoted from guess to truth.

    Spec section 9 is explicit that an unverified model assumption must not
    become a confirmed company fact automatically, so provenance lives on the
    row itself rather than being inferred at read time.
    """

    __tablename__ = "company_memories"
    __table_args__ = (
        Index("ix_memory_org_kind", "organization_id", "source_kind"),
        Index("ix_memory_search", "search_vector", postgresql_using="gin"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))

    # Shares the fact_source PG type with EvidenceSource; the initial migration
    # creates that type once up front.
    source_kind: Mapped[FactSource] = mapped_column(
        Enum(FactSource, name="fact_source"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    origin_meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="SET NULL")
    )
    origin_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
