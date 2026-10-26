"""A deterministic stand-in for the whole board.

The orchestrator makes six different kinds of model call with six different
output schemas. This model identifies which kind is being asked for by
inspecting the output tool's JSON schema, and identifies *which executive* is
asking by reading the instructions — so tests can assert both that every stage
got valid data and that each agent received only its own prompt.

It can also be told to fail for a given agent or stage, which is how the
partial-failure behaviour gets tested without a flaky provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agents.registry import REGISTRY, AgentId


class ScriptedFailure(Exception):
    """Raised inside the model to simulate a provider-side failure."""


@dataclass
class BoardCall:
    kind: str
    agent_id: str | None
    instructions: str
    prompt: str


def _schema_kind(info: AgentInfo) -> str:
    """Work out which stage is calling from the requested output schema."""
    if not info.output_tools:
        return "text"
    schema: dict[str, Any] = info.output_tools[0].parameters_json_schema or {}
    props = set(schema.get("properties", {}))
    for marker, kind in (
        ("reframed_question", "agenda"),
        ("conflicts_found", "debate_plan"),
        ("position_changed", "revision"),
        ("challenged_claim", "objection"),
        ("executive_summary", "synthesis"),
        ("recommended_position", "assessment"),
        ("answer", "consultation"),
    ):
        if marker in props:
            return kind
    return "unknown"


def _agent_from_instructions(instructions: str) -> str | None:
    for agent_id, definition in REGISTRY.items():
        # The identity block names the executive before the roster listing.
        head = instructions.split("The full board")[0]
        if definition.display_name in head:
            return agent_id.value
    return None


@dataclass
class ScriptedBoard:
    """Scripts a meeting where the CFO and CEO genuinely disagree."""

    calls: list[BoardCall] = field(default_factory=list)
    #: agent_id -> stage kind that should blow up, e.g. {"coo": "assessment"}
    fail: dict[str, str] = field(default_factory=dict)
    #: Set False to script a board that agrees, so no debate is assigned.
    produce_conflict: bool = True
    participants: tuple[str, ...] = ("ceo", "coo", "cfo", "strategy_consultant")

    # -- per-agent assessment content, so positions genuinely differ --------
    POSITIONS: ClassVar[dict[str, str]] = {
        "ceo": "Launch the new product; it is the only option that changes our position.",
        "coo": "Improve retention; we do not have the delivery capacity for a launch.",
        "cfo": "Improve retention; a launch is not affordable on a 12-month runway.",
        "strategy_consultant": (
            "The question is a false choice; retention and launch are not mutually exclusive."
        ),
    }

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        instructions = ""
        prompt = ""
        for message in messages:
            if isinstance(message, ModelRequest):
                if message.instructions:
                    instructions = message.instructions
                for part in message.parts:
                    if part.part_kind == "user-prompt":
                        prompt = str(part.content)

        kind = _schema_kind(info)
        agent_id = _agent_from_instructions(instructions)
        self.calls.append(
            BoardCall(kind=kind, agent_id=agent_id, instructions=instructions, prompt=prompt)
        )

        if agent_id and self.fail.get(agent_id) == kind:
            raise ScriptedFailure(f"scripted failure for {agent_id} during {kind}")

        payload = self._payload(kind, agent_id)
        tool_name = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name, payload)])

    # -- payloads ----------------------------------------------------------

    def _payload(self, kind: str, agent_id: str | None) -> dict[str, Any]:
        builder = getattr(self, f"_{kind}", None)
        if builder is None:
            raise AssertionError(f"ScriptedBoard has no payload for kind {kind!r}")
        return builder(agent_id)

    def _agenda(self, _: str | None) -> dict[str, Any]:
        return {
            "reframed_question": (
                "Which single priority best protects revenue over the next 12 months?"
            ),
            "agenda_items": [
                {
                    "title": "Runway impact",
                    "question": "What does each option cost against 12 months of runway?",
                    "why_it_matters": "A choice we cannot fund is not a choice.",
                },
                {
                    "title": "Delivery capacity",
                    "question": "Can 28 people execute the chosen option?",
                    "why_it_matters": "Capacity, not strategy, is the usual constraint.",
                },
            ],
            "participants": [
                {"agent_id": a, "reason": f"{a} bears on this decision"}
                for a in self.participants
            ],
            "tensions_to_test": ["Growth ambition against delivery capacity"],
        }

    def _assessment(self, agent_id: str | None) -> dict[str, Any]:
        position = self.POSITIONS.get(
            agent_id or "", "No strong view on the question as framed."
        )
        return {
            "summary": f"Assessment from {agent_id}: {position}",
            "recommended_position": position,
            "supporting_arguments": [
                {"point": "Runway is 12 months", "reasoning": "3.0M cash over 250k burn"}
            ],
            "evidence_references": [
                {
                    "claim": "Runway is 12 months",
                    "source": "company profile",
                    "is_verified": True,
                }
            ],
            "assumptions": [
                {
                    "statement": "Burn stays flat",
                    "why_it_matters": "Runway shortens if it does not",
                    "how_to_validate": "Check the latest monthly actuals",
                }
            ],
            "risks": [
                {
                    "description": "Capacity is already committed",
                    "severity": "major",
                    "likelihood": "medium",
                    "mitigation": "Sequence the work",
                }
            ],
            "opportunities": [
                {"description": "Retention compounds", "potential_impact": "Protects ARR"}
            ],
            "open_questions": [
                {
                    "question": "Is churn logo or revenue churn?",
                    "why_it_matters": "They imply different fixes",
                    "who_should_answer": "customer_advocate",
                }
            ],
            "confidence_level": "medium",
        }

    def _debate_plan(self, _: str | None) -> dict[str, Any]:
        if not self.produce_conflict:
            return {
                "conflicts_found": False,
                "assignments": [],
                "rationale": "The executives substantially agreed; no challenge is warranted.",
            }
        return {
            "conflicts_found": True,
            "assignments": [
                {
                    "challenger_agent_id": "cfo",
                    "target_agent_id": "ceo",
                    "claim_to_challenge": (
                        "Launch the new product; it is the only option that changes "
                        "our position."
                    ),
                    "why_this_conflict_matters": (
                        "A launch and a 12-month runway may be incompatible."
                    ),
                },
                {
                    "challenger_agent_id": "coo",
                    "target_agent_id": "ceo",
                    "claim_to_challenge": "Launch the new product",
                    "why_this_conflict_matters": "Delivery capacity is already committed.",
                },
            ],
            "rationale": "The CEO wants a launch; the CFO and COO both say it is infeasible.",
        }

    def _objection(self, agent_id: str | None) -> dict[str, Any]:
        return {
            "stance": "challenge",
            "challenged_claim": "Launch the new product",
            "objection": (
                f"{agent_id} objects: a launch consumes runway we need to reach "
                "the next financing milestone."
            ),
            "supporting_evidence": ["Cash on hand 3.0M", "Monthly burn 250k"],
            "severity": "major",
            "proposed_resolution": "Model the launch cost against runway before committing.",
        }

    def _revision(self, agent_id: str | None) -> dict[str, Any]:
        return {
            "position_changed": True,
            "updated_position": (
                f"{agent_id} revised: stage the launch behind a retention push."
            ),
            "reason_for_change": "The runway argument is sound; a full launch is not fundable.",
            "evidence_considered": ["Runway of 12 months", "Committed delivery capacity"],
        }

    def _synthesis(self, _: str | None) -> dict[str, Any]:
        return {
            "problem_statement": "Choosing one priority for the next 12 months.",
            "executive_summary": "Prioritise retention; stage the launch behind it.",
            "strategic_options": [
                {
                    "option_id": "retention",
                    "title": "Improve retention",
                    "description": "Reduce churn before adding surface area.",
                    "benefits": ["Protects existing ARR"],
                    "risks": ["Does not add new revenue"],
                    "costs": ["Engineering time"],
                    "dependencies": ["Churn diagnosis"],
                    "assumptions": ["Churn is addressable"],
                    "evaluation": "Supported by the CFO and COO.",
                },
                {
                    "option_id": "launch",
                    "title": "Launch the new product",
                    "description": "Build a second product line.",
                    "benefits": ["Changes competitive position"],
                    "risks": ["Not fundable on current runway"],
                    "costs": ["Significant"],
                    "dependencies": ["Financing"],
                    "assumptions": ["Capacity exists"],
                    "evaluation": "Challenged on both cost and capacity.",
                },
            ],
            "recommended_option_id": "retention",
            "recommendation_rationale": "It protects revenue within the existing runway.",
            "financial_implications": "Retention preserves the 12-month runway.",
            "operational_implications": "Fits current delivery capacity.",
            "legal_considerations": None,
            "customer_implications": "Depends on why customers are leaving.",
            "competitive_implications": "Does not change position in the short term.",
            "dissenting_opinions": [
                {
                    "agent_id": "ceo",
                    "position": "A launch is still the higher-value move.",
                    "reasoning": "Retention alone does not change the company trajectory.",
                }
            ],
            "unresolved_questions": [
                {
                    "question": "Is the 15% churn logo or revenue churn?",
                    "why_it_matters": "It determines the size of the prize",
                    "who_should_answer": "customer_advocate",
                }
            ],
            "key_assumptions": [
                {
                    "statement": "Burn stays flat",
                    "why_it_matters": "Runway shortens otherwise",
                    "how_to_validate": "Check monthly actuals",
                }
            ],
            "major_risks": [
                {
                    "description": "Churn may not be addressable by product work",
                    "severity": "major",
                    "likelihood": "medium",
                    "mitigation": "Diagnose before committing roadmap",
                }
            ],
            "confidence_and_uncertainty": (
                "Medium. The churn breakdown would change the recommendation."
            ),
            "confidence_level": "medium",
            "action_plan": {
                "first_30_days": [
                    {
                        "description": "Diagnose churn by cohort",
                        "suggested_owner": "Customer team",
                        "priority": "critical",
                        "target_window": "0-30 days",
                        "dependencies": [],
                    }
                ],
                "days_30_to_60": [
                    {
                        "description": "Ship the top two retention fixes",
                        "suggested_owner": "Engineering",
                        "priority": "high",
                        "target_window": "30-60 days",
                        "dependencies": ["Churn diagnosis"],
                    }
                ],
                "days_60_to_90": [
                    {
                        "description": "Re-evaluate the launch against updated runway",
                        "suggested_owner": "CEO",
                        "priority": "medium",
                        "target_window": "60-90 days",
                        "dependencies": ["Retention results"],
                    }
                ],
            },
        }

    # -- helpers for assertions -------------------------------------------

    def kinds(self) -> list[str]:
        return [c.kind for c in self.calls]

    def of_kind(self, kind: str) -> list[BoardCall]:
        return [c for c in self.calls if c.kind == kind]

    def as_model(self) -> FunctionModel:
        return FunctionModel(self, model_name="scripted-board")


def scripted_board(**kwargs) -> tuple[ScriptedBoard, FunctionModel]:
    board = ScriptedBoard(**kwargs)
    return board, board.as_model()


def agent_ids_seen(board: ScriptedBoard, kind: str) -> set[str]:
    return {c.agent_id for c in board.of_kind(kind) if c.agent_id}


__all__ = [
    "AgentId",
    "BoardCall",
    "ScriptedBoard",
    "ScriptedFailure",
    "agent_ids_seen",
    "scripted_board",
]
