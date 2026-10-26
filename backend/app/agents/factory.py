"""Builds one Pydantic AI ``Agent`` per executive.

Each roster entry gets its own Agent instance with its own instructions,
output type, and model settings. There is deliberately no path here that
produces several executives from one model call — the separation is the point
(spec section 5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from app.agents.deps import GhostBoardDeps
from app.agents.meeting_schemas import (
    DebatePlanOutput,
    DecisionBriefOutput,
    MeetingAgendaOutput,
    ObjectionOutput,
    RevisionOutput,
)
from app.agents.prompts import ONE_ON_ONE_SUFFIX, SHARED_RULES, role_instructions
from app.agents.provider import build_model, default_model_settings
from app.agents.registry import REGISTRY, AgentId, ExecutiveDefinition
from app.agents.schemas import AgentAssessmentOutput, ConsultationResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentBundle:
    """An executive and the agent that speaks for it."""

    definition: ExecutiveDefinition
    consultation_agent: Agent[GhostBoardDeps, ConsultationResponse]
    assessment_agent: Agent[GhostBoardDeps, AgentAssessmentOutput]
    objection_agent: Agent[GhostBoardDeps, ObjectionOutput]
    revision_agent: Agent[GhostBoardDeps, RevisionOutput]


def _identity_block(definition: ExecutiveDefinition) -> str:
    """The fixed part of who this executive is."""
    return (
        f"Your name is {definition.display_name}. "
        f"Your role is {definition.title} ({definition.short_title}).\n"
        f"Your remit: {definition.role_summary}\n"
        f"How colleagues describe you: {definition.personality}\n"
        f"Your agent id, for referring to yourself in structured output, "
        f"is '{definition.agent_id.value}'."
    )


def _roster_block() -> str:
    """So an agent can refer work to a real colleague, not an invented one."""
    lines = ["The full board, for referrals only (never answer as one of these):"]
    lines.extend(
        f"- {d.agent_id.value}: {d.display_name}, {d.title}" for d in REGISTRY.values()
    )
    return "\n".join(lines)


def _build_agent[OutputT](
    definition: ExecutiveDefinition,
    output_type: type[OutputT],
    extra_instructions: str,
    model: Model | None = None,
    max_tokens: int | None = None,
) -> Agent[GhostBoardDeps, OutputT]:
    static_instructions = "\n\n".join(
        [
            SHARED_RULES,
            _identity_block(definition),
            role_instructions(definition.agent_id),
            extra_instructions,
            _roster_block(),
        ]
    )

    agent: Agent[GhostBoardDeps, OutputT] = Agent(
        model or build_model(),
        output_type=output_type,
        deps_type=GhostBoardDeps,
        instructions=static_instructions,
        model_settings=default_model_settings(max_tokens=max_tokens),
        name=f"ghostboard-{definition.agent_id.value}",
        # Bounded retries: a response that will not validate twice is a real
        # failure and should surface, not loop.
        retries=2,
    )

    @agent.instructions
    def company_context(ctx: RunContext[GhostBoardDeps]) -> str:
        """Injected per run, so one agent instance serves every organization
        without leaking context between them."""
        return ctx.deps.company.as_prompt_block()

    @agent.instructions
    def scope_reminder(ctx: RunContext[GhostBoardDeps]) -> str:
        if ctx.deps.agent_id != definition.agent_id:
            # Defensive: a mismatch means the service wired the wrong deps.
            logger.warning(
                "Deps agent_id %s does not match agent %s",
                ctx.deps.agent_id,
                definition.agent_id,
            )
        return (
            "You have no external research tools in this session. If answering "
            "well needs information you do not have, say what is missing rather "
            "than filling the gap."
        )

    return agent


ASSESSMENT_SUFFIX = """\
You are producing an independent written assessment for the board. You have
not seen what your colleagues think, and you must not speculate about it or
address them. Write only your own analysis of the question.
"""

OBJECTION_SUFFIX = """\
The board has exchanged initial positions and the Chair has asked you to
respond to one specific claim by one colleague.

Respond to the claim you are given, from your own professional angle. Three
stances are legitimate and you should pick the honest one:
- 'challenge' when you think the claim is wrong or unsupported,
- 'partially_agree' when it holds in part,
- 'agree' when it holds and you have nothing to add against it.

Agreeing is a real answer. Do not invent a disagreement to look rigorous, and
do not soften a real one to seem agreeable. Argue from the company facts and
your own prior reasoning, never from invented data.
"""

REVISION_SUFFIX = """\
A colleague has challenged your position. Consider their argument honestly and
state where you now stand.

Changing your mind on good evidence is a strength; so is holding your position
when the objection does not actually land. Say which happened and why. Restate
your position either way, so the record is complete.
"""


def build_bundle(definition: ExecutiveDefinition, model: Model | None = None) -> AgentBundle:
    """Construct every agent one executive needs across all workflows."""
    return AgentBundle(
        definition=definition,
        consultation_agent=_build_agent(
            definition, ConsultationResponse, ONE_ON_ONE_SUFFIX, model
        ),
        assessment_agent=_build_agent(
            definition, AgentAssessmentOutput, ASSESSMENT_SUFFIX, model, max_tokens=3500
        ),
        objection_agent=_build_agent(
            definition, ObjectionOutput, OBJECTION_SUFFIX, model, max_tokens=2000
        ),
        revision_agent=_build_agent(
            definition, RevisionOutput, REVISION_SUFFIX, model, max_tokens=2000
        ),
    )


AGENDA_SUFFIX = """\
You are opening a board meeting. Nobody has analysed anything yet.

Your job here is framing, not answering. Work out what the board actually
needs to settle, break it into agenda items, and choose which executives bear
on it. Choose only ids from the roster you were given, and never include
yourself in participants — you chair, you do not assess.

Name the tensions you expect between functions. Those are what the meeting is
for; a meeting where everyone agrees was not worth convening.
"""

DEBATE_SUFFIX = """\
You have the executives' independent assessments in front of you. They have
not seen each other's work.

Three things are worth putting to a colleague, and all three count as genuine
conflict:

1. Direct contradiction - two executives who cannot both be right.
2. A load-bearing assumption one executive relies on that another function is
   better placed to test. An assumption nobody has validated is not
   agreement; it is shared exposure, and surfacing it is your job.
3. A recommendation whose feasibility, cost, or legal exposure another
   executive has not been asked about.

Expect case 2 to be the common one. Executives who all reason carefully will
often reach the same provisional answer while resting it on different
unverified premises. Converging on "we need more evidence" is not consensus
about the business - it usually means nobody has tested whose evidence gap
matters most. Put that to them.

For each conflict, assign exactly one challenger and one target, and quote
the specific claim.

Return no assignments only when the assessments genuinely leave nothing to
test, not merely because the recommendations happen to match. Manufacturing a
disagreement that is not there is a failure; so is waving through an
assumption nobody has checked.

Assign at most four challenges; pick the ones that would most change the
decision if the challenge lands.
"""

SYNTHESIS_SUFFIX = """\
You are writing the decision brief. You have the agenda, every independent
assessment, every objection raised, and every revision made.

Hard constraints:
- Every conclusion must trace to something an executive actually said. You may
  not introduce analysis nobody performed, however sensible it seems.
- Disagreement that survived the debate goes in dissenting_opinions, attributed
  by agent id. Do not resolve it by fiat or average it away.
- Questions nobody could answer go in unresolved_questions. A brief that hides
  what the board did not know is worse than one that admits it.
- Recommend one option and say why. Hedging to avoid being wrong is not
  neutrality, it is a failure to do your job.
- The action plan must follow from the discussion, with relative windows
  rather than invented calendar dates.
"""


@dataclass(frozen=True, slots=True)
class ChairAgents:
    """The Chairperson's three meeting-stage agents.

    Separate agents rather than one with a switch: each has a different output
    schema and a different job, and conflating them is how a chair starts
    answering the business question instead of running the process.
    """

    agenda_agent: Agent[GhostBoardDeps, MeetingAgendaOutput]
    debate_agent: Agent[GhostBoardDeps, DebatePlanOutput]
    synthesis_agent: Agent[GhostBoardDeps, DecisionBriefOutput]


def build_chair_agents(model: Model | None = None) -> ChairAgents:
    chair = REGISTRY[AgentId.CHAIRPERSON]
    return ChairAgents(
        agenda_agent=_build_agent(
            chair, MeetingAgendaOutput, AGENDA_SUFFIX, model, max_tokens=2500
        ),
        debate_agent=_build_agent(
            chair, DebatePlanOutput, DEBATE_SUFFIX, model, max_tokens=2500
        ),
        # The decision brief is the largest structured output in the system:
        # 14 fields, nested options, dissent, and a 30/60/90 plan. At 2000
        # tokens the provider truncates it mid-tool-call.
        synthesis_agent=_build_agent(
            chair, DecisionBriefOutput, SYNTHESIS_SUFFIX, model, max_tokens=8000
        ),
    )


@lru_cache(maxsize=1)
def _bundles() -> dict[AgentId, AgentBundle]:
    """Built once per process, on first use rather than at import.

    Deferring matters: constructing a model requires the provider key, and the
    app must still boot (and serve /api/health) without one.
    """
    logger.info("Instantiating %d executive agents", len(REGISTRY))
    return {agent_id: build_bundle(d) for agent_id, d in REGISTRY.items()}


@lru_cache(maxsize=1)
def _chair_agents() -> ChairAgents:
    return build_chair_agents()


def get_bundle(agent_id: AgentId) -> AgentBundle:
    """Return the live agents for one executive."""
    return _bundles()[agent_id]


def get_chair_agents() -> ChairAgents:
    """Return the live Chairperson meeting agents."""
    return _chair_agents()


def reset_agent_cache() -> None:
    """Drop cached agents. Used by tests that swap the model."""
    _bundles.cache_clear()
    _chair_agents.cache_clear()
