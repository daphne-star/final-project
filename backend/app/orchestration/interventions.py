"""Running a founder's intervention inside a live meeting.

The prompt for each kind is written here rather than in the agent
instructions, because an intervention is a task handed to an executive mid
meeting, not a change to who that executive is. The agent answering a
challenge is the same agent that gave the assessment being challenged.
"""

from __future__ import annotations

from app.agents.registry import REGISTRY, AgentId
from app.models.intervention import InterventionKind

#: What each kind asks the executive to do. The founder's own words are
#: appended; these only frame them.
KIND_FRAMING: dict[InterventionKind, str] = {
    InterventionKind.ASK: (
        "The founder has interrupted the meeting to ask you directly. Answer "
        "the question they actually asked, from your own expertise, as briefly "
        "as it can honestly be answered."
    ),
    InterventionKind.CHALLENGE: (
        "The founder is challenging your position. Engage with the substance. "
        "If they are right, say so and say what changes. If they are not, say "
        "why, without softening it to be agreeable — they asked because they "
        "want your judgement, not your deference."
    ),
    InterventionKind.REQUEST_EVIDENCE: (
        "The founder wants to know what your position actually rests on. "
        "Separate what you got from the company's own records, what you "
        "assumed, and what you do not know. If a claim of yours has no "
        "evidence behind it, say that plainly rather than finding some."
    ),
    InterventionKind.CRITIQUE_COLLEAGUE: (
        "The founder has asked you to examine a colleague's conclusion from "
        "your own function's angle. Say where it holds and where it does not. "
        "Agreeing is a real answer; so is finding nothing wrong with it."
    ),
    InterventionKind.REQUEST_ALTERNATIVE: (
        "The founder wants an option the board has not put forward. Propose a "
        "genuine alternative from your angle, including what would have to be "
        "true for it to be the right one — not a restatement of an existing "
        "option with different words."
    ),
    InterventionKind.IMPLEMENTATION_DETAIL: (
        "The founder wants the concrete version: who does what, in what order, "
        "and what has to be in place first. Relative timing only; you do not "
        "know the start date."
    ),
    InterventionKind.EXPLAIN_RISK: (
        "The founder wants a risk explained properly: what would have to "
        "happen for it to materialise, how you would see it coming, and what "
        "it would cost. Say if you cannot size it."
    ),
}


def build_prompt(
    *,
    kind: InterventionKind,
    agent_id: AgentId,
    founder_text: str,
    about_agent_id: AgentId | None,
    meeting_question: str,
    own_position: str | None,
    target_position: str | None,
    stage: str,
) -> str:
    """Assemble the intervention prompt with the context the agent needs."""
    definition = REGISTRY[agent_id]
    parts: list[str] = [
        f"The board meeting is in progress (stage: {stage}).",
        f"The question before the board is:\n{meeting_question}",
        "",
        KIND_FRAMING[kind],
        "",
    ]

    if own_position:
        parts.append(f"Your own position so far:\n{own_position}\n")

    if about_agent_id is not None and target_position:
        other = REGISTRY[about_agent_id]
        parts.append(
            f"{other.display_name} ({other.title}) concluded:\n{target_position}\n"
        )

    parts.extend(
        [
            f"The founder says, to you specifically ({definition.display_name}):",
            f'"{founder_text.strip()}"',
            "",
            (
                "Answer them directly. This is an interruption in a live "
                "meeting, not a written report: be brief and specific."
            ),
        ]
    )
    return "\n".join(parts)


def default_title(kind: InterventionKind, agent_id: AgentId) -> str:
    name = REGISTRY[agent_id].short_title
    return {
        InterventionKind.ASK: f"Question for {name}",
        InterventionKind.CHALLENGE: f"Challenge to {name}",
        InterventionKind.REQUEST_EVIDENCE: f"Evidence from {name}",
        InterventionKind.CRITIQUE_COLLEAGUE: f"{name} critiques a colleague",
        InterventionKind.REQUEST_ALTERNATIVE: f"Alternative from {name}",
        InterventionKind.IMPLEMENTATION_DETAIL: f"Implementation detail from {name}",
        InterventionKind.EXPLAIN_RISK: f"Risk explained by {name}",
    }[kind]
