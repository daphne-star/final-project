"""Decision briefs, per-agent positions on them, and resulting action items."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ActionItemStatus, DecisionStatus, Priority


class StrategicDecision(Base, UUIDMixin, TimestampMixin):
    """The persisted DecisionBrief plus the human verdict on it."""

    __tablename__ = "strategic_decisions"
    __table_args__ = (Index("ix_decision_org_status", "organization_id", "status"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("meetings.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)

    strategic_options: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recommended_option_id: Mapped[str | None] = mapped_column(String(64))
    recommendation_rationale: Mapped[str | None] = mapped_column(Text)

    financial_implications: Mapped[str | None] = mapped_column(Text)
    operational_implications: Mapped[str | None] = mapped_column(Text)
    legal_considerations: Mapped[str | None] = mapped_column(Text)
    customer_implications: Mapped[str | None] = mapped_column(Text)
    competitive_implications: Mapped[str | None] = mapped_column(Text)

    dissenting_opinions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    unresolved_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    confidence_and_uncertainty: Mapped[str | None] = mapped_column(Text)
    action_plan: Mapped[dict | None] = mapped_column(JSONB)

    # Human authority: the board advises, the user decides (spec principle 3).
    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, name="decision_status"),
        default=DecisionStatus.PROPOSED,
        nullable=False,
    )
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_notes: Mapped[str | None] = mapped_column(Text)

    positions: Mapped[list[DecisionPosition]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )
    action_items: Mapped[list[ActionItem]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class DecisionPosition(Base, UUIDMixin, TimestampMixin):
    """Where each executive landed, including dissent that survived the debate."""

    __tablename__ = "decision_positions"
    __table_args__ = (Index("ix_position_decision_agent", "decision_id", "agent_id"),)

    decision_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategic_decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stance: Mapped[str] = mapped_column(String(32), nullable=False)  # support | oppose | abstain
    position_summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    is_dissent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    decision: Mapped[StrategicDecision] = relationship(back_populates="positions")


class ActionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "action_items"
    __table_args__ = (Index("ix_action_org_status", "organization_id", "status"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategic_decisions.id", ondelete="CASCADE")
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_owner: Mapped[str | None] = mapped_column(String(200))
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="action_priority"), default=Priority.MEDIUM, nullable=False
    )
    target_date: Mapped[date | None] = mapped_column(Date)
    dependencies: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[ActionItemStatus] = mapped_column(
        Enum(ActionItemStatus, name="action_item_status"),
        default=ActionItemStatus.OPEN,
        nullable=False,
    )
    outcome_notes: Mapped[str | None] = mapped_column(Text)

    decision: Mapped[StrategicDecision | None] = relationship(back_populates="action_items")
