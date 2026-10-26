"""Board meeting lifecycle: create, run, persist, retrieve."""

from __future__ import annotations

import logging
import uuid

from pydantic_ai.models import Model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.meeting_schemas import ActionItemOutput, DecisionBriefOutput
from app.agents.registry import REGISTRY, AgentId
from app.db.session import AsyncSessionLocal
from app.models.decision import ActionItem, DecisionPosition, StrategicDecision
from app.models.enums import (
    ActionItemStatus,
    DecisionStatus,
    MeetingMode,
    MeetingStatus,
)
from app.models.meeting import (
    AgentAssessment,
    AgentObjection,
    AgentRevision,
    Meeting,
    MeetingEvent,
)
from app.orchestration.events import EventSink, noop_sink
from app.orchestration.meeting import (
    MeetingAborted,
    MeetingCancelled,
    MeetingLimits,
    MeetingOrchestrator,
)
from app.services.consultation import load_company_context

logger = logging.getLogger(__name__)


class MeetingError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


async def create_meeting(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    question: str,
    title: str | None = None,
    mode: MeetingMode = MeetingMode.EXECUTIVE_MEETING,
) -> Meeting:
    meeting = Meeting(
        organization_id=organization_id,
        created_by_user_id=user_id,
        title=title or _derive_title(question),
        question=question,
        mode=mode,
    )
    db.add(meeting)
    await db.flush()
    await db.refresh(meeting)
    return meeting


def _derive_title(question: str) -> str:
    cleaned = " ".join(question.split())
    return cleaned if len(cleaned) <= 120 else cleaned[:117] + "…"


async def get_meeting(
    db: AsyncSession, meeting_id: uuid.UUID, organization_id: uuid.UUID
) -> Meeting | None:
    """Org scope is part of the query, not a check afterwards."""
    return (
        await db.execute(
            select(Meeting)
            .where(Meeting.id == meeting_id, Meeting.organization_id == organization_id)
            .options(selectinload(Meeting.participants))
        )
    ).scalar_one_or_none()


async def get_meeting_contributions(db: AsyncSession, meeting_id: uuid.UUID) -> dict:
    """Everything the board produced, for retrieval after completion."""
    assessments = (
        (
            await db.execute(
                select(AgentAssessment)
                .where(AgentAssessment.meeting_id == meeting_id)
                .order_by(AgentAssessment.round_number, AgentAssessment.created_at)
            )
        )
        .scalars()
        .all()
    )
    objections = (
        (
            await db.execute(
                select(AgentObjection)
                .where(AgentObjection.meeting_id == meeting_id)
                .order_by(AgentObjection.created_at)
            )
        )
        .scalars()
        .all()
    )
    revisions = (
        (
            await db.execute(
                select(AgentRevision)
                .where(AgentRevision.meeting_id == meeting_id)
                .order_by(AgentRevision.created_at)
            )
        )
        .scalars()
        .all()
    )
    decision = (
        await db.execute(
            select(StrategicDecision)
            .where(StrategicDecision.meeting_id == meeting_id)
            .options(
                selectinload(StrategicDecision.positions),
                selectinload(StrategicDecision.action_items),
            )
        )
    ).scalar_one_or_none()

    return {
        "assessments": list(assessments),
        "objections": list(objections),
        "revisions": list(revisions),
        "decision": decision,
    }


async def list_events(
    db: AsyncSession, meeting_id: uuid.UUID, *, after_sequence: int = 0, limit: int = 500
) -> list[MeetingEvent]:
    """Replayable event log. ``after_sequence`` supports SSE reconnection."""
    return list(
        (
            await db.execute(
                select(MeetingEvent)
                .where(
                    MeetingEvent.meeting_id == meeting_id,
                    MeetingEvent.sequence_number > after_sequence,
                )
                .order_by(MeetingEvent.sequence_number)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def cancel_meeting(db: AsyncSession, meeting: Meeting) -> Meeting:
    """Request cancellation. The orchestrator notices at its next checkpoint.

    This does not abort an in-flight provider request — the spec is explicit
    that we must not claim to.
    """
    if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.FAILED):
        raise MeetingError(
            f"Meeting is already {meeting.status.value}.", code="not_cancellable"
        )
    meeting.status = MeetingStatus.CANCELLED
    await db.flush()
    return meeting


async def run_meeting(
    db: AsyncSession,
    meeting: Meeting,
    *,
    user_id: uuid.UUID | None = None,
    model: Model | None = None,
    limits: MeetingLimits | None = None,
    sink: EventSink = noop_sink,
) -> StrategicDecision:
    """Run the full workflow and persist the resulting decision brief."""
    if meeting.status not in (MeetingStatus.DRAFT, MeetingStatus.PAUSED):
        raise MeetingError(
            f"Meeting is {meeting.status.value} and cannot be started.",
            code="not_startable",
        )

    company = await load_company_context(db, meeting.organization_id)
    orchestrator = MeetingOrchestrator(
        db,
        meeting,
        company,
        limits=limits,
        model=model,
        sink=sink,
        user_id=user_id,
    )

    brief = await orchestrator.run()
    return await persist_decision(db, meeting, brief, orchestrator)


async def persist_decision(
    db: AsyncSession,
    meeting: Meeting,
    brief: DecisionBriefOutput,
    orchestrator: MeetingOrchestrator,
) -> StrategicDecision:
    """Turn the brief into durable records the Decision Center can read."""
    decision = StrategicDecision(
        organization_id=meeting.organization_id,
        meeting_id=meeting.id,
        title=meeting.title,
        problem_statement=brief.problem_statement,
        executive_summary=brief.executive_summary,
        strategic_options=[o.model_dump(mode="json") for o in brief.strategic_options],
        recommended_option_id=brief.recommended_option_id,
        recommendation_rationale=brief.recommendation_rationale,
        financial_implications=brief.financial_implications,
        operational_implications=brief.operational_implications,
        legal_considerations=brief.legal_considerations,
        customer_implications=brief.customer_implications,
        competitive_implications=brief.competitive_implications,
        dissenting_opinions=[d.model_dump(mode="json") for d in brief.dissenting_opinions],
        unresolved_questions=[q.model_dump(mode="json") for q in brief.unresolved_questions],
        confidence_and_uncertainty=brief.confidence_and_uncertainty,
        action_plan=brief.action_plan.model_dump(mode="json"),
        status=DecisionStatus.PROPOSED,
    )
    db.add(decision)
    await db.flush()

    # Final stance per executive, taken from the revision if they made one and
    # the original assessment otherwise, so dissent is attributable.
    dissenting_ids = {d.agent_id for d in brief.dissenting_opinions}
    for agent_id, assessment in orchestrator.assessments.items():
        revision = orchestrator.revisions.get(agent_id)
        position = revision.updated_position if revision else assessment.recommended_position
        db.add(
            DecisionPosition(
                decision_id=decision.id,
                agent_id=agent_id.value,
                stance="oppose" if agent_id.value in dissenting_ids else "support",
                position_summary=position,
                rationale=revision.reason_for_change if revision else assessment.summary,
                is_dissent=agent_id.value in dissenting_ids,
            )
        )

    for window, items in (
        ("0-30 days", brief.action_plan.first_30_days),
        ("30-60 days", brief.action_plan.days_30_to_60),
        ("60-90 days", brief.action_plan.days_60_to_90),
    ):
        for item in items:
            db.add(_action_item(meeting.organization_id, decision.id, item, window))

    await db.flush()
    # Re-select with the collections eagerly loaded. A plain refresh() expires
    # them, and the first attribute access would then lazy-load outside the
    # async context.
    return (
        await db.execute(
            select(StrategicDecision)
            .where(StrategicDecision.id == decision.id)
            .options(
                selectinload(StrategicDecision.positions),
                selectinload(StrategicDecision.action_items),
            )
        )
    ).scalar_one()


def _action_item(
    organization_id: uuid.UUID,
    decision_id: uuid.UUID,
    item: ActionItemOutput,
    default_window: str,
) -> ActionItem:
    return ActionItem(
        organization_id=organization_id,
        decision_id=decision_id,
        description=item.description,
        suggested_owner=item.suggested_owner,
        priority=item.priority,
        # No target_date: the spec forbids inventing calendar dates, so the
        # relative window is carried in dependencies metadata instead.
        dependencies=[*item.dependencies, f"window:{item.target_window or default_window}"],
        status=ActionItemStatus.OPEN,
    )


async def run_meeting_in_background(
    meeting_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> None:
    """Entry point for the fire-and-forget task started by the API.

    Opens its own session: the request that started the meeting has long since
    returned and its session is closed.
    """
    async with AsyncSessionLocal() as db:
        try:
            meeting = await get_meeting(db, meeting_id, organization_id)
            if meeting is None:
                logger.error("Background meeting %s vanished before it started", meeting_id)
                return
            await run_meeting(db, meeting, user_id=user_id)
            await db.commit()
            logger.info("Meeting %s completed", meeting_id)
        except MeetingCancelled:
            await db.commit()
            logger.info("Meeting %s cancelled", meeting_id)
        except MeetingAborted as exc:
            await db.commit()
            logger.warning("Meeting %s aborted: %s", meeting_id, exc)
        except Exception:
            # Unexpected: the orchestrator already persisted a failure event
            # for anything it anticipated, so this is a genuine bug. Roll back
            # and leave the meeting visibly failed rather than stuck running.
            logger.exception("Meeting %s crashed", meeting_id)
            await db.rollback()
            async with AsyncSessionLocal() as recovery:
                found = await recovery.get(Meeting, meeting_id)
                if found is not None and found.status is MeetingStatus.RUNNING:
                    found.status = MeetingStatus.FAILED
                    found.failure_reason = "Unexpected orchestrator error; see server logs."
                    await recovery.commit()


def participant_display(agent_id: str) -> str:
    try:
        return REGISTRY[AgentId(agent_id)].display_name
    except (ValueError, KeyError):
        return agent_id


__all__ = [
    "MeetingError",
    "cancel_meeting",
    "create_meeting",
    "get_meeting",
    "get_meeting_contributions",
    "list_events",
    "participant_display",
    "persist_decision",
    "run_meeting",
    "run_meeting_in_background",
]
