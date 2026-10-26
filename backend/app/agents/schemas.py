"""Structured outputs every executive agent must produce.

These are the contract between the model and the rest of the system. Nothing
downstream parses free text — Pydantic AI validates against these and retries
on failure, so an unparseable response is an error, not a silent degradation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConfidenceLevel, Priority, Severity


class Assumption(BaseModel):
    """Something the agent had to take as given. Named, so it can be tested."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(description="The assumption, stated plainly")
    why_it_matters: str = Field(description="What breaks if this is wrong")
    how_to_validate: str | None = Field(
        default=None, description="A concrete way to check it"
    )


class Risk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    severity: Severity
    likelihood: ConfidenceLevel = Field(description="How likely this is to materialise")
    mitigation: str | None = None


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    potential_impact: str


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    why_it_matters: str
    who_should_answer: str | None = None


class EvidenceReference(BaseModel):
    """Where a claim came from. ``source`` is never invented by the model."""

    model_config = ConfigDict(extra="forbid")

    claim: str
    source: str = Field(
        description=(
            "Where this came from: a named tool result, a company profile field, "
            "or 'user statement'. Say 'no evidence' when there is none."
        )
    )
    is_verified: bool = Field(
        description="True only for tool results or user-confirmed company facts"
    )


class SupportingArgument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point: str
    reasoning: str


class AgentAssessmentOutput(BaseModel):
    """One executive's structured position on a question (spec section 5)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Two or three sentences, in your own voice")
    recommended_position: str = Field(
        description="What you actually recommend, stated as a decision"
    )
    supporting_arguments: list[SupportingArgument] = Field(default_factory=list)
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = Field(
        description="Be honest. Low confidence with named gaps beats false precision."
    )


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    priority: Priority
    suggested_owner: str | None = None
    rough_timeline: str | None = Field(
        default=None, description="Relative, e.g. 'next 30 days'. Never invent dates."
    )


class ConsultationResponse(BaseModel):
    """What a one-on-one consultation turn returns.

    Lighter than a full assessment: a founder asking a direct question wants an
    answer first, with the structure underneath it rather than instead of it.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        description="Your direct answer, in your own professional voice. Markdown allowed."
    )
    key_points: list[str] = Field(
        default_factory=list, description="Three to five takeaways"
    )
    assumptions: list[Assumption] = Field(
        default_factory=list,
        description="Anything you had to assume because the context did not say",
    )
    risks: list[Risk] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(
        default_factory=list, description="What you would need to answer this better"
    )
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    confidence_level: ConfidenceLevel
    out_of_scope: bool = Field(
        default=False,
        description=(
            "True when the question falls outside your remit and another "
            "executive should take it."
        ),
    )
    refer_to_agent_id: str | None = Field(
        default=None,
        description="When out_of_scope, which roster executive should answer instead",
    )
