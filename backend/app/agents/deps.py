"""Typed dependencies injected into every agent run.

Two rules shape this module:

1. Authorization is resolved *before* the agent runs. ``organization_id`` here
   is the one the API already verified membership for; the model cannot widen
   it by asking (spec section 8).
2. Only a bounded, already-authorized context snapshot is carried — never a
   repository handle the model could use to read the whole database, and never
   a secret.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.agents.registry import AgentId, ToolScope


@dataclass(frozen=True, slots=True)
class CompanyContext:
    """The authorized slice of company facts an agent may reason over.

    Built by the service layer from CompanyProfile. Every field is either
    user-entered or derived from user-entered values, so an agent quoting one
    is quoting the founder, not itself.
    """

    company_name: str | None = None
    industry: str | None = None
    business_model: str | None = None
    stage: str | None = None
    headcount: int | None = None
    description: str | None = None
    revenue_model: str | None = None

    arr_usd: float | None = None
    monthly_burn_usd: float | None = None
    cash_on_hand_usd: float | None = None
    runway_months: float | None = None
    annual_churn_rate: float | None = None

    goals: tuple[str, ...] = ()
    challenges: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.company_name is None

    def as_prompt_block(self) -> str:
        """Render for the instructions. Absent values are stated as unknown
        rather than omitted, so the model can see what it is missing."""
        if self.is_empty:
            return (
                "No company profile has been entered yet. You know nothing about "
                "this business beyond what the user tells you in conversation. Do "
                "not invent figures, customers, or market facts."
            )

        lines: list[str] = ["Company facts confirmed by the user:"]

        def add(label: str, value: object, suffix: str = "") -> None:
            lines.append(f"- {label}: {value}{suffix}" if value is not None else f"- {label}: not provided")

        add("Name", self.company_name)
        add("Industry", self.industry)
        add("Business model", self.business_model)
        add("Stage", self.stage)
        add("Headcount", self.headcount)
        add("Revenue model", self.revenue_model)
        add("ARR (USD)", f"{self.arr_usd:,.0f}" if self.arr_usd is not None else None)
        add(
            "Monthly burn (USD)",
            f"{self.monthly_burn_usd:,.0f}" if self.monthly_burn_usd is not None else None,
        )
        add(
            "Cash on hand (USD)",
            f"{self.cash_on_hand_usd:,.0f}" if self.cash_on_hand_usd is not None else None,
        )
        add("Runway (months)", self.runway_months)
        add(
            "Annual churn",
            f"{self.annual_churn_rate:.1%}" if self.annual_churn_rate is not None else None,
        )

        if self.description:
            lines.append(f"- What the company does: {self.description}")
        if self.goals:
            lines.append(f"- Goals: {'; '.join(self.goals)}")
        if self.challenges:
            lines.append(f"- Challenges: {'; '.join(self.challenges)}")
        if self.constraints:
            lines.append(f"- Constraints: {'; '.join(self.constraints)}")

        lines.append(
            "Any figure not listed above is unknown to you. Say so rather than estimating."
        )
        return "\n".join(lines)


@dataclass(slots=True)
class GhostBoardDeps:
    """Per-run dependency bundle handed to a Pydantic AI agent."""

    organization_id: uuid.UUID
    user_id: uuid.UUID | None
    agent_id: AgentId

    company: CompanyContext = field(default_factory=CompanyContext)

    consultation_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None

    #: Tool families this agent is allowed to reach, copied from the registry
    #: at build time. Phase 5 enforces this when attaching MCP toolsets.
    allowed_tool_scopes: tuple[ToolScope, ...] = ()

    def may_use(self, scope: ToolScope) -> bool:
        return scope in self.allowed_tool_scopes
