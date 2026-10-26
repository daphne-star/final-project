"""Structured outputs specific to a board meeting.

Consultation outputs live in ``schemas.py``; these are the shapes that only
appear when several executives are in the room. Every one is validated by
Pydantic AI with bounded retries — no stage parses free text.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.agents.schemas import Assumption, OpenQuestion, Risk
from app.models.enums import ConfidenceLevel, Priority, Severity

# --------------------------------------------------------------------------
# Stage 1 — Agenda (Chairperson)
# --------------------------------------------------------------------------


class AgendaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Short label for this part of the discussion")
    question: str = Field(description="The specific question this item must settle")
    why_it_matters: str


class ParticipantSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(description="Must be one of the roster ids you were given")
    reason: str = Field(description="Why this function bears on the decision")


class MeetingAgendaOutput(BaseModel):
    """How the Chairperson frames the meeting before anyone analyses anything."""

    model_config = ConfigDict(extra="forbid")

    reframed_question: str = Field(
        description=(
            "The real question the board should answer. Often not the question "
            "as asked. Say so plainly if you are reframing it."
        )
    )
    agenda_items: list[AgendaItem] = Field(min_length=1)
    participants: list[ParticipantSelection] = Field(
        min_length=1,
        description="Which executives should contribute, and why. Exclude yourself.",
    )
    tensions_to_test: list[str] = Field(
        default_factory=list,
        description="Disagreements you expect and want surfaced rather than smoothed over",
    )


# --------------------------------------------------------------------------
# Stage 4 — Debate (Chairperson plans, executives object)
# --------------------------------------------------------------------------


class DebateAssignment(BaseModel):
    """One executive asked to challenge one specific claim by another."""

    model_config = ConfigDict(extra="forbid")

    challenger_agent_id: str
    target_agent_id: str
    claim_to_challenge: str = Field(
        description="Quote or closely paraphrase the actual claim from their assessment"
    )
    why_this_conflict_matters: str


class DebatePlanOutput(BaseModel):
    """The Chairperson's read of where the real disagreements are.

    ``assignments`` may legitimately be empty: if the executives agree, the
    spec forbids manufacturing a fight.
    """

    model_config = ConfigDict(extra="forbid")

    conflicts_found: bool
    assignments: list[DebateAssignment] = Field(default_factory=list)
    rationale: str = Field(
        description="What you saw in the assessments that led to these assignments, or to none"
    )


class ObjectionOutput(BaseModel):
    """One executive's response to a colleague's specific claim."""

    model_config = ConfigDict(extra="forbid")

    stance: str = Field(
        description="One of: 'challenge', 'partially_agree', 'agree'. Agreeing is allowed."
    )
    challenged_claim: str
    objection: str = Field(
        description="Your actual argument. If you agree, say why the claim holds."
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Company facts or your own prior reasoning. Never invented data.",
    )
    severity: Severity = Field(description="How much this changes the decision if you are right")
    proposed_resolution: str | None = Field(
        default=None, description="What would settle this disagreement"
    )


# --------------------------------------------------------------------------
# Stage 5 — Revision
# --------------------------------------------------------------------------


class RevisionOutput(BaseModel):
    """Whether an executive moved after being challenged.

    ``position_changed = False`` is a perfectly good outcome and must not be
    penalised; holding a position under scrutiny is informative.
    """

    model_config = ConfigDict(extra="forbid")

    position_changed: bool
    updated_position: str = Field(
        description="Your position now. Restate it even if unchanged."
    )
    reason_for_change: str = Field(
        description="What in the objection moved you, or why it did not"
    )
    evidence_considered: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Stage 6 — Synthesis (Chairperson)
# --------------------------------------------------------------------------


class StrategicOptionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(description="Short slug, e.g. 'retention'")
    title: str
    description: str
    benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    costs: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evaluation: str = Field(description="Your read on how this option fared in the discussion")


class DissentingOpinion(BaseModel):
    """A minority view that survived the debate. The spec requires these be
    recorded rather than resolved away."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    position: str
    reasoning: str


class ActionItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    suggested_owner: str | None = None
    priority: Priority
    target_window: str | None = Field(
        default=None, description="Relative, e.g. '0-30 days'. Never invent calendar dates."
    )
    dependencies: list[str] = Field(default_factory=list)


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_30_days: list[ActionItemOutput] = Field(default_factory=list)
    days_30_to_60: list[ActionItemOutput] = Field(default_factory=list)
    days_60_to_90: list[ActionItemOutput] = Field(default_factory=list)


class DecisionBriefOutput(BaseModel):
    """The Chairperson's synthesis of what the board actually discussed.

    The instructions forbid introducing conclusions nobody investigated, and
    ``dissenting_opinions`` plus ``unresolved_questions`` exist so that
    disagreement and ignorance survive into the written record.
    """

    model_config = ConfigDict(extra="forbid")

    problem_statement: str
    executive_summary: str
    strategic_options: list[StrategicOptionOutput] = Field(min_length=1)
    recommended_option_id: str
    recommendation_rationale: str

    financial_implications: str | None = None
    operational_implications: str | None = None
    legal_considerations: str | None = None
    customer_implications: str | None = None
    competitive_implications: str | None = None

    dissenting_opinions: list[DissentingOpinion] = Field(default_factory=list)
    unresolved_questions: list[OpenQuestion] = Field(default_factory=list)
    key_assumptions: list[Assumption] = Field(default_factory=list)
    major_risks: list[Risk] = Field(default_factory=list)
    confidence_and_uncertainty: str = Field(
        description="How confident the board is, and precisely what would change the answer"
    )
    confidence_level: ConfidenceLevel
    action_plan: ActionPlan
