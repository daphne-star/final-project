"""Meeting request and response payloads."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    ActionItemStatus,
    ConfidenceLevel,
    DecisionStatus,
    MeetingMode,
    MeetingStage,
    MeetingStatus,
    ParticipantStatus,
    Priority,
    Severity,
)
from app.models.intervention import InterventionKind, InterventionStatus
from app.schemas.common import ORMModel


class MeetingCreate(BaseModel):
    question: str = Field(min_length=10, max_length=4000)
    title: str | None = Field(default=None, max_length=300)
    mode: MeetingMode = MeetingMode.EXECUTIVE_MEETING
    start_immediately: bool = Field(
        default=True, description="Begin the workflow in the background on creation"
    )
    subject_decision_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "The decision to stress-test. Required for devils_advocate mode "
            "and ignored by the others."
        ),
    )
    participant_agent_ids: list[str] | None = Field(
        default=None,
        max_length=8,
        description=(
            "Executives to invite. The Chairperson always attends and must not "
            "be listed. Omit to let the Chair pick from the default pool."
        ),
    )


class ParticipantRead(ORMModel):
    agent_id: str
    selection_reason: str | None
    status: ParticipantStatus
    speaking_order: int | None


class MeetingRead(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    subject_decision_id: uuid.UUID | None = None
    title: str
    question: str
    mode: MeetingMode
    status: MeetingStatus
    stage: MeetingStage
    agenda: dict | None
    started_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None
    debate_rounds_used: int
    model_requests_used: int
    estimated_cost_usd: float
    created_at: datetime


class AssessmentRead(ORMModel):
    """An independently produced position. Never synthesis."""

    id: uuid.UUID
    agent_id: str
    round_number: int
    summary: str
    recommended_position: str
    supporting_arguments: list
    evidence_references: list
    assumptions: list
    risks: list
    opportunities: list
    open_questions: list
    confidence_level: ConfidenceLevel
    created_at: datetime


class ObjectionRead(ORMModel):
    id: uuid.UUID
    source_agent_id: str
    target_agent_id: str
    round_number: int
    challenged_claim: str
    objection: str
    supporting_evidence: list
    severity: Severity
    proposed_resolution: str | None
    created_at: datetime


class RevisionRead(ORMModel):
    id: uuid.UUID
    agent_id: str
    round_number: int
    original_position: str
    updated_position: str
    reason_for_change: str
    evidence_considered: list
    created_at: datetime


class DecisionPositionRead(ORMModel):
    agent_id: str
    stance: str
    position_summary: str
    rationale: str | None
    is_dissent: bool


class ActionItemRead(ORMModel):
    id: uuid.UUID
    description: str
    suggested_owner: str | None
    priority: Priority
    dependencies: list
    status: str


class DecisionRead(ORMModel):
    id: uuid.UUID
    meeting_id: uuid.UUID | None
    title: str
    problem_statement: str
    executive_summary: str
    strategic_options: list
    recommended_option_id: str | None
    recommendation_rationale: str | None
    financial_implications: str | None
    operational_implications: str | None
    legal_considerations: str | None
    customer_implications: str | None
    competitive_implications: str | None
    dissenting_opinions: list
    unresolved_questions: list
    confidence_and_uncertainty: str | None
    action_plan: dict | None
    status: DecisionStatus
    decision_notes: str | None
    positions: list[DecisionPositionRead] = Field(default_factory=list)
    action_items: list[ActionItemRead] = Field(default_factory=list)
    created_at: datetime


class MeetingDetail(MeetingRead):
    """Everything the board produced, retrievable after completion."""

    participants: list[ParticipantRead] = Field(default_factory=list)
    assessments: list[AssessmentRead] = Field(default_factory=list)
    objections: list[ObjectionRead] = Field(default_factory=list)
    revisions: list[RevisionRead] = Field(default_factory=list)
    decision: DecisionRead | None = None
    interventions: list[InterventionRead] = Field(default_factory=list)


class MeetingEventRead(ORMModel):
    id: uuid.UUID
    sequence_number: int
    event_type: str
    agent_id: str | None
    payload: dict
    timestamp: datetime


class DecisionUpdate(BaseModel):
    """The founder's verdict. The board advises; this is where they decide."""

    status: DecisionStatus
    decision_notes: str | None = Field(default=None, max_length=4000)


class InterventionCreate(BaseModel):
    """A founder interrupting a live meeting to address one executive."""

    agent_id: str = Field(description="Which executive to address")
    kind: InterventionKind = InterventionKind.ASK
    prompt: str = Field(min_length=3, max_length=4000)
    about_agent_id: str | None = Field(
        default=None,
        description="For critique_colleague: whose conclusion to examine",
    )


class InterventionRead(ORMModel):
    id: uuid.UUID
    agent_id: str
    about_agent_id: str | None
    kind: InterventionKind
    prompt: str
    status: InterventionStatus
    answered_at_stage: str | None
    response: str | None
    structured_response: dict | None
    error_message: str | None
    answered_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class ActionItemUpdate(BaseModel):
    status: ActionItemStatus | None = None
    suggested_owner: str | None = Field(default=None, max_length=200)
    priority: Priority | None = None
    target_date: date | None = None
    outcome_notes: str | None = Field(default=None, max_length=4000)


class ActionItemDetail(ActionItemRead):
    decision_id: uuid.UUID | None
    target_date: date | None
    outcome_notes: str | None
    created_at: datetime
