"""One-on-one consultations with a single executive."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MeetingStatus


class Consultation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "consultations"
    __table_args__ = (Index("ix_consultation_org_agent", "organization_id", "agent_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # Reuses the MeetingStatus values but gets its own PG type, so Alembic never
    # tries to CREATE TYPE meeting_status twice.
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, name="consultation_status"),
        default=MeetingStatus.RUNNING,
        nullable=False,
    )

    messages: Mapped[list[ConsultationMessage]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
        order_by="ConsultationMessage.created_at",
    )


class ConsultationMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "consultation_messages"
    __table_args__ = (Index("ix_consultation_message_parent", "consultation_id", "created_at"),)

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user | agent | system
    agent_id: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Typed agent output (ConsultationResponse) when the turn produced one.
    structured_output: Mapped[dict | None] = mapped_column(JSONB)

    # Serialized Pydantic AI ModelMessage list for this turn, replayed as
    # message_history on the next one. Null for turns that never hit a model.
    model_messages: Mapped[list | None] = mapped_column(JSONB)

    promoted_to_meeting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    consultation: Mapped[Consultation] = relationship(back_populates="messages")
