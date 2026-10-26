"""Board meeting endpoints.

Meetings run as background tasks: a full workflow is ~10 model calls and takes
far longer than a reasonable HTTP request. The client starts one and then
follows the persisted event log, which is also what Phase 4's SSE stream will
read from.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentOrg, CurrentUser, DbSession
from app.models.decision import StrategicDecision
from app.models.enums import MeetingStatus
from app.models.meeting import Meeting, MeetingParticipant
from app.schemas.meeting import (
    AssessmentRead,
    DecisionRead,
    DecisionUpdate,
    MeetingCreate,
    MeetingDetail,
    MeetingEventRead,
    MeetingRead,
    ObjectionRead,
    ParticipantRead,
    RevisionRead,
)
from app.services import meeting as svc

router = APIRouter(tags=["meetings"])


async def _load_or_404(db: DbSession, meeting_id: uuid.UUID, org_id: uuid.UUID) -> Meeting:
    meeting = await svc.get_meeting(db, meeting_id, org_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


async def _detail(db: DbSession, meeting: Meeting) -> MeetingDetail:
    parts = await svc.get_meeting_contributions(db, meeting.id)
    # Query participants rather than reading meeting.participants: a freshly
    # created meeting has not been through the eager-loading path, and the
    # lazy load would fail outside the async context.
    participants = (
        (
            await db.execute(
                select(MeetingParticipant)
                .where(MeetingParticipant.meeting_id == meeting.id)
                .order_by(MeetingParticipant.speaking_order)
            )
        )
        .scalars()
        .all()
    )
    return MeetingDetail(
        **MeetingRead.model_validate(meeting).model_dump(),
        participants=[ParticipantRead.model_validate(p) for p in participants],
        assessments=[AssessmentRead.model_validate(a) for a in parts["assessments"]],
        objections=[ObjectionRead.model_validate(o) for o in parts["objections"]],
        revisions=[RevisionRead.model_validate(r) for r in parts["revisions"]],
        decision=DecisionRead.model_validate(parts["decision"]) if parts["decision"] else None,
    )


@router.post("/meetings", response_model=MeetingDetail, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreate, org: CurrentOrg, user: CurrentUser, db: DbSession
) -> MeetingDetail:
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=payload.question,
        title=payload.title,
        mode=payload.mode,
    )

    if payload.start_immediately:
        # Commit first: the background task opens its own session and must be
        # able to see this meeting.
        await db.commit()
        _spawn(meeting.id, org.id, user.id)
        await db.refresh(meeting)

    return await _detail(db, meeting)


@router.post("/meetings/{meeting_id}/start", response_model=MeetingRead, status_code=202)
async def start_meeting(
    meeting_id: uuid.UUID, org: CurrentOrg, user: CurrentUser, db: DbSession
) -> MeetingRead:
    meeting = await _load_or_404(db, meeting_id, org.id)
    if meeting.status not in (MeetingStatus.DRAFT, MeetingStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Meeting is {meeting.status.value} and cannot be started.",
        )
    await db.commit()
    _spawn(meeting.id, org.id, user.id)
    await db.refresh(meeting)
    return MeetingRead.model_validate(meeting)


def _spawn(meeting_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire-and-forget the orchestrator.

    The reference is held on the task object by asyncio until completion; the
    service logs and records any failure itself, so nothing is swallowed.
    """
    task = asyncio.create_task(svc.run_meeting_in_background(meeting_id, org_id, user_id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


_BACKGROUND_TASKS: set[asyncio.Task] = set()


@router.get("/meetings", response_model=list[MeetingRead])
async def list_meetings(
    org: CurrentOrg, db: DbSession, limit: int = Query(default=50, ge=1, le=200)
) -> list[MeetingRead]:
    rows = (
        (
            await db.execute(
                select(Meeting)
                .where(Meeting.organization_id == org.id)
                .order_by(Meeting.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [MeetingRead.model_validate(m) for m in rows]


@router.get("/meetings/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(meeting_id: uuid.UUID, org: CurrentOrg, db: DbSession) -> MeetingDetail:
    meeting = await _load_or_404(db, meeting_id, org.id)
    return await _detail(db, meeting)


@router.get("/meetings/{meeting_id}/events", response_model=list[MeetingEventRead])
async def get_meeting_events(
    meeting_id: uuid.UUID,
    org: CurrentOrg,
    db: DbSession,
    after: int = Query(default=0, ge=0, description="Return events after this sequence number"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[MeetingEventRead]:
    """Replayable log. ``after`` is the reconnection cursor."""
    await _load_or_404(db, meeting_id, org.id)
    events = await svc.list_events(db, meeting_id, after_sequence=after, limit=limit)
    return [MeetingEventRead.model_validate(e) for e in events]


@router.post("/meetings/{meeting_id}/cancel", response_model=MeetingRead)
async def cancel_meeting(
    meeting_id: uuid.UUID, org: CurrentOrg, db: DbSession
) -> MeetingRead:
    """Request cancellation; the orchestrator stops at its next checkpoint."""
    meeting = await _load_or_404(db, meeting_id, org.id)
    try:
        await svc.cancel_meeting(db, meeting)
    except svc.MeetingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return MeetingRead.model_validate(meeting)


@router.get("/decisions", response_model=list[DecisionRead])
async def list_decisions(
    org: CurrentOrg, db: DbSession, limit: int = Query(default=50, ge=1, le=200)
) -> list[DecisionRead]:
    rows = (
        (
            await db.execute(
                select(StrategicDecision)
                .where(StrategicDecision.organization_id == org.id)
                .options(
                    selectinload(StrategicDecision.positions),
                    selectinload(StrategicDecision.action_items),
                )
                .order_by(StrategicDecision.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [DecisionRead.model_validate(d) for d in rows]


@router.get("/decisions/{decision_id}", response_model=DecisionRead)
async def get_decision(
    decision_id: uuid.UUID, org: CurrentOrg, db: DbSession
) -> DecisionRead:
    decision = await _load_decision(db, decision_id, org.id)
    return DecisionRead.model_validate(decision)


@router.patch("/decisions/{decision_id}", response_model=DecisionRead)
async def update_decision(
    decision_id: uuid.UUID,
    payload: DecisionUpdate,
    org: CurrentOrg,
    user: CurrentUser,
    db: DbSession,
) -> DecisionRead:
    """Accept, reject, or defer. Human authority over the board's advice."""
    decision = await _load_decision(db, decision_id, org.id)
    decision.status = payload.status
    decision.decided_by_user_id = user.id
    if payload.decision_notes is not None:
        decision.decision_notes = payload.decision_notes
    await db.flush()
    await db.refresh(decision)
    return DecisionRead.model_validate(decision)


async def _load_decision(
    db: DbSession, decision_id: uuid.UUID, org_id: uuid.UUID
) -> StrategicDecision:
    decision = (
        await db.execute(
            select(StrategicDecision)
            .where(
                StrategicDecision.id == decision_id,
                StrategicDecision.organization_id == org_id,
            )
            .options(
                selectinload(StrategicDecision.positions),
                selectinload(StrategicDecision.action_items),
            )
        )
    ).scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return decision
