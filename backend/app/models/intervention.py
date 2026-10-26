"""User interventions in a live meeting.

The spec calls this the defining feature, and the part that makes it real
rather than decorative is that an intervention is a persisted row the
orchestrator picks up — not a frontend state change. It is queued by an
authenticated REST call, drained by the running meeting at a safe point, and
the resulting exchange survives in the meeting's history.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class InterventionKind(StrEnum):
    """What the founder is asking for. Shapes the prompt, not the plumbing."""

    ASK = "ask"
    CHALLENGE = "challenge"
    REQUEST_EVIDENCE = "request_evidence"
    CRITIQUE_COLLEAGUE = "critique_colleague"
    REQUEST_ALTERNATIVE = "request_alternative"
    IMPLEMENTATION_DETAIL = "implementation_detail"
    EXPLAIN_RISK = "explain_risk"


class InterventionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    ANSWERED = "answered"
    FAILED = "failed"
    #: The meeting ended before the queue was drained.
    ABANDONED = "abandoned"


class MeetingIntervention(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meeting_interventions"
    __table_args__ = (
        Index("ix_intervention_meeting_status", "meeting_id", "status"),
        Index("ix_intervention_meeting_created", "meeting_id", "created_at"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    #: Who the founder is addressing.
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: For critique_colleague: whose conclusion to examine.
    about_agent_id: Mapped[str | None] = mapped_column(String(64))

    kind: Mapped[InterventionKind] = mapped_column(
        Enum(InterventionKind, name="intervention_kind"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[InterventionStatus] = mapped_column(
        Enum(InterventionStatus, name="intervention_status"),
        default=InterventionStatus.QUEUED,
        nullable=False,
    )
    #: The stage the meeting was in when this was answered, for the record.
    answered_at_stage: Mapped[str | None] = mapped_column(String(64))
    response: Mapped[str | None] = mapped_column(Text)
    structured_response: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
