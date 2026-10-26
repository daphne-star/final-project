"""Board meetings and everything produced inside one."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ConfidenceLevel,
    MeetingMode,
    MeetingStage,
    MeetingStatus,
    ParticipantStatus,
    Severity,
    ToolInvocationStatus,
)

if TYPE_CHECKING:
    from app.models.identity import Organization


class Meeting(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meetings"
    __table_args__ = (Index("ix_meetings_org_created", "organization_id", "created_at"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[MeetingMode] = mapped_column(
        Enum(MeetingMode, name="meeting_mode"), nullable=False
    )
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, name="meeting_status"), default=MeetingStatus.DRAFT, nullable=False
    )
    stage: Mapped[MeetingStage] = mapped_column(
        Enum(MeetingStage, name="meeting_stage"), default=MeetingStage.INTAKE, nullable=False
    )

    agenda: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    debate_rounds_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_requests_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="meetings")
    participants: Mapped[list[MeetingParticipant]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    events: Mapped[list[MeetingEvent]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    assessments: Mapped[list[AgentAssessment]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class MeetingParticipant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "agent_id", name="uq_meeting_agent"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ParticipantStatus] = mapped_column(
        Enum(ParticipantStatus, name="participant_status"),
        default=ParticipantStatus.WAITING,
        nullable=False,
    )
    speaking_order: Mapped[int | None] = mapped_column(Integer)

    meeting: Mapped[Meeting] = relationship(back_populates="participants")


class MeetingEvent(Base, UUIDMixin):
    """Append-only event log. Persisted before delivery so SSE can replay."""

    __tablename__ = "meeting_events"
    __table_args__ = (
        UniqueConstraint("meeting_id", "sequence_number", name="uq_meeting_event_seq"),
        Index("ix_meeting_events_meeting_seq", "meeting_id", "sequence_number"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    meeting: Mapped[Meeting] = relationship(back_populates="events")


class AgentAssessment(Base, UUIDMixin, TimestampMixin):
    """One structured executive position (spec section 5)."""

    __tablename__ = "agent_assessments"
    __table_args__ = (Index("ix_assessment_meeting_agent", "meeting_id", "agent_id"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_position: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_arguments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    evidence_references: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    risks: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    opportunities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    open_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level"), nullable=False
    )

    meeting: Mapped[Meeting] = relationship(back_populates="assessments")


class AgentObjection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_objections"
    __table_args__ = (Index("ix_objection_meeting", "meeting_id"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    source_agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    challenged_claim: Mapped[str] = mapped_column(Text, nullable=False)
    objection: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="objection_severity"), nullable=False
    )
    proposed_resolution: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AgentRevision(Base, UUIDMixin, TimestampMixin):
    """Original and revised positions are tracked separately (spec stage 6)."""

    __tablename__ = "agent_revisions"
    __table_args__ = (Index("ix_revision_meeting_agent", "meeting_id", "agent_id"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    original_position: Mapped[str] = mapped_column(Text, nullable=False)
    updated_position: Mapped[str] = mapped_column(Text, nullable=False)
    reason_for_change: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_considered: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class ToolInvocation(Base, UUIDMixin, TimestampMixin):
    """Audit record for every MCP tool call (spec section 8)."""

    __tablename__ = "tool_invocations"
    __table_args__ = (Index("ix_tool_invocation_org_created", "organization_id", "created_at"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE")
    )
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE")
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    arguments: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[ToolInvocationStatus] = mapped_column(
        Enum(ToolInvocationStatus, name="tool_invocation_status"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
