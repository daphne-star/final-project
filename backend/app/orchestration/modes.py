"""What each meeting mode changes.

A mode is not a different workflow — all five run the same six stages. What
varies is who is in the room, how many challenges are worth running, and what
the board is being asked to *do* with the question. That framing is injected
into the stage prompts rather than into the agent instructions, so one agent
instance per executive still serves every mode and each executive keeps its
own single role block.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentId
from app.models.enums import MeetingMode

#: Every specialist. The Chair is added separately and never assesses.
ALL_SPECIALISTS: tuple[AgentId, ...] = (
    AgentId.CEO,
    AgentId.COO,
    AgentId.CFO,
    AgentId.CGO,
    AgentId.CUSTOMER_ADVOCATE,
    AgentId.COMPETITIVE_INTEL,
    AgentId.GENERAL_COUNSEL,
    AgentId.STRATEGY_CONSULTANT,
)

#: The core five from Session 3, kept as the Quick Consultation fallback.
CORE_FOUR: tuple[AgentId, ...] = (
    AgentId.CEO,
    AgentId.COO,
    AgentId.CFO,
    AgentId.STRATEGY_CONSULTANT,
)


@dataclass(frozen=True, slots=True)
class ModeProfile:
    """How one mode shapes the meeting."""

    mode: MeetingMode
    label: str
    candidates: tuple[AgentId, ...]
    #: Cap on participants the Chair may seat. Keeps the call count bounded.
    max_participants: int
    min_participants: int
    #: Extra model-request headroom, since a bigger room costs more calls.
    model_request_budget: int
    max_challenges: int
    #: True when the meeting needs an existing recommendation to work on.
    requires_subject: bool

    agenda_task: str
    assessment_task: str
    debate_task: str
    synthesis_task: str
    #: Only Strategy Workshop runs the extra COO roadmap stage.
    roadmap_stage: bool = False
    #: Below this many completed assessments there is nothing to synthesise.
    #: A quick consultation legitimately has one voice; a board does not.
    min_assessments: int = 2


_EXECUTIVE = ModeProfile(
    mode=MeetingMode.EXECUTIVE_MEETING,
    label="Executive Meeting",
    candidates=ALL_SPECIALISTS,
    max_participants=6,
    min_participants=3,
    model_request_budget=40,
    max_challenges=4,
    requires_subject=False,
    agenda_task=(
        "Seat three to six executives — the ones whose function genuinely bears "
        "on this decision. Leaving out a function that does not bear on it is a "
        "judgement, not an omission; seating everyone is an abdication of one."
    ),
    assessment_task="Give your independent assessment of the question.",
    debate_task="",
    synthesis_task="",
)

_FULL_BOARD = ModeProfile(
    mode=MeetingMode.FULL_BOARD,
    label="Full Board Meeting",
    candidates=ALL_SPECIALISTS,
    max_participants=8,
    min_participants=8,
    model_request_budget=80,
    max_challenges=4,
    requires_subject=False,
    agenda_task=(
        "This is a full board meeting: every executive attends and every one "
        "will give an assessment. Seat all of them. Your agenda should give "
        "each function something real to answer, not a token line — if a "
        "function has little to add here, say so in your agenda rather than "
        "inventing work for it."
    ),
    assessment_task=(
        "Give your independent assessment of the question. The full board is "
        "attending, so stay tightly inside your own function: your colleagues "
        "cover theirs and duplicated analysis wastes the meeting."
    ),
    debate_task=(
        "With eight assessments in front of you there will be more apparent "
        "conflict than is worth running. Pick the few challenges that would "
        "most change the decision."
    ),
    synthesis_task=(
        "Eight executives contributed. Do not give each a paragraph out of "
        "fairness — weight them by what actually bears on the decision, and "
        "say plainly where a function had little to add."
    ),
)

_DEVILS_ADVOCATE = ModeProfile(
    mode=MeetingMode.DEVILS_ADVOCATE,
    label="Devil's Advocate",
    candidates=(
        AgentId.CFO,
        AgentId.COO,
        AgentId.CUSTOMER_ADVOCATE,
        AgentId.COMPETITIVE_INTEL,
        AgentId.GENERAL_COUNSEL,
        AgentId.STRATEGY_CONSULTANT,
    ),
    max_participants=5,
    min_participants=3,
    model_request_budget=40,
    max_challenges=4,
    requires_subject=True,
    agenda_task=(
        "This meeting exists to stress-test an existing recommendation, not to "
        "re-decide it. Seat the executives most likely to find a way it fails. "
        "Your agenda items should be the specific ways it could be wrong."
    ),
    assessment_task=(
        "Your job here is to find how this recommendation fails, from your own "
        "function's angle. Attack the reasoning, not the people.\n\n"
        "Be specific: which assumption is load-bearing and unverified, what "
        "would have to be true for this to work, what breaks first and under "
        "what conditions. A weakness you can name and test is worth more than "
        "general scepticism.\n\n"
        "If after genuinely trying you cannot find a material weakness from "
        "your angle, say that plainly and say what evidence made you confident. "
        "Manufacturing an objection to look useful is the one failure mode this "
        "meeting cannot tolerate."
    ),
    debate_task=(
        "These are all criticisms of the same recommendation. The useful "
        "conflicts are where one executive's objection is answered by another's "
        "evidence, or where two objections cannot both be serious."
    ),
    synthesis_task=(
        "Report what survived. Your brief should say whether the recommendation "
        "holds, what would have to change for it to hold, or why it should be "
        "abandoned — and it must distinguish weaknesses that were demonstrated "
        "from ones that were merely asserted. If the recommendation came "
        "through intact, say so; a stress test that always fails the thing it "
        "tests is not a test."
    ),
)

_STRATEGY_WORKSHOP = ModeProfile(
    mode=MeetingMode.STRATEGY_WORKSHOP,
    label="Strategy Workshop",
    candidates=ALL_SPECIALISTS,
    max_participants=6,
    min_participants=3,
    model_request_budget=60,
    max_challenges=3,
    requires_subject=False,
    roadmap_stage=True,
    agenda_task=(
        "This is a workshop: the board is here to generate and evaluate "
        "options, then plan the chosen one in detail. Seat the executives who "
        "can both propose alternatives and judge them. Your agenda should push "
        "for options nobody has raised yet, including doing nothing."
    ),
    assessment_task=(
        "Propose alternatives, do not just judge the ones implied by the "
        "question. From your function's angle: what options exist, including "
        "at least one nobody has mentioned, and what would have to be true for "
        "each to be the right one.\n\n"
        "Then say which you would pick and why. Listing options without a view "
        "is not analysis."
    ),
    debate_task=(
        "Focus the challenges on the options themselves: which proposed "
        "alternative rests on an assumption another function is better placed "
        "to test."
    ),
    synthesis_task=(
        "This is a workshop output. Give more strategic options than a normal "
        "brief would — including the ones the board rejected and why — and make "
        "the action plan concrete enough to start on Monday."
    ),
)

_QUICK = ModeProfile(
    mode=MeetingMode.QUICK_CONSULTATION,
    label="Quick Consultation",
    candidates=CORE_FOUR,
    max_participants=1,
    min_participants=1,
    min_assessments=1,
    model_request_budget=12,
    max_challenges=0,
    requires_subject=False,
    agenda_task=(
        "This is a quick consultation. Seat exactly one executive: the single "
        "function best placed to answer. Keep the agenda to one item."
    ),
    assessment_task="Answer the question directly from your own expertise.",
    debate_task="",
    synthesis_task=(
        "One executive answered. Keep the brief short and do not manufacture "
        "options the board never discussed."
    ),
)

MODE_PROFILES: dict[MeetingMode, ModeProfile] = {
    MeetingMode.QUICK_CONSULTATION: _QUICK,
    MeetingMode.EXECUTIVE_MEETING: _EXECUTIVE,
    MeetingMode.FULL_BOARD: _FULL_BOARD,
    MeetingMode.DEVILS_ADVOCATE: _DEVILS_ADVOCATE,
    MeetingMode.STRATEGY_WORKSHOP: _STRATEGY_WORKSHOP,
}


def profile_for(mode: MeetingMode) -> ModeProfile:
    return MODE_PROFILES[mode]


ROADMAP_TASK = """\
The board has chosen a direction. Turn it into a plan the company can start on.

Give concrete 30/60/90-day sequencing with named prerequisites, the capacity
each phase assumes, and what has to be true before each phase can begin. Use
your tools to check whether the plan actually fits the capacity available.

Relative windows only — you do not know the start date, so do not invent one.
Where the plan depends on a figure nobody gave you, say which figure.
"""
