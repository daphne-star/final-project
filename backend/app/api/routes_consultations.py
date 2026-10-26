"""One-on-one consultation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import AgentModel, CurrentOrg, CurrentUser, DbSession
from app.models.consultation import Consultation, ConsultationMessage
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationDetail,
    ConsultationRead,
    ConsultationSummary,
    MessageCreate,
    TurnResponse,
)
from app.services import consultation as svc

router = APIRouter(tags=["consultations"])


def _as_http(exc: svc.ConsultationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post(
    "/consultations", response_model=ConsultationDetail, status_code=status.HTTP_201_CREATED
)
async def create_consultation(
    payload: ConsultationCreate,
    org: CurrentOrg,
    user: CurrentUser,
    db: DbSession,
    model: AgentModel,
) -> ConsultationDetail:
    try:
        consultation = await svc.create_consultation(
            db,
            organization_id=org.id,
            user_id=user.id,
            agent_id=payload.agent_id,
            title=payload.title,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No executive with id {payload.agent_id!r}",
        )
    except svc.ConsultationError as exc:
        raise _as_http(exc)

    if payload.opening_message:
        try:
            await svc.send_message(
                db,
                consultation=consultation,
                content=payload.opening_message,
                user_id=user.id,
                model=model,
            )
        except svc.ConsultationError as exc:
            # The consultation itself was created; surface the turn failure but
            # do not roll the whole thing back, so the user can retry the ask.
            raise _as_http(exc)

    loaded = await svc.get_consultation(db, consultation.id, org.id)
    assert loaded is not None
    return ConsultationDetail.model_validate(loaded)


@router.get("/consultations", response_model=list[ConsultationSummary])
async def list_consultations(
    org: CurrentOrg,
    db: DbSession,
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ConsultationSummary]:
    stmt = (
        select(
            Consultation,
            func.count(ConsultationMessage.id).label("message_count"),
            func.max(ConsultationMessage.created_at).label("last_message_at"),
        )
        .outerjoin(ConsultationMessage)
        .where(Consultation.organization_id == org.id)
        .group_by(Consultation.id)
        .order_by(Consultation.updated_at.desc())
        .limit(limit)
    )
    if agent_id:
        stmt = stmt.where(Consultation.agent_id == agent_id)

    rows = (await db.execute(stmt)).all()
    # Validate against ConsultationRead, not ConsultationDetail: the latter
    # would touch `messages`, which is not eager-loaded here and would trigger
    # a lazy load outside the async context.
    return [
        ConsultationSummary(
            **ConsultationRead.model_validate(c).model_dump(),
            message_count=count,
            last_message_at=last,
        )
        for c, count, last in rows
    ]


@router.get("/consultations/{consultation_id}", response_model=ConsultationDetail)
async def get_consultation(
    consultation_id: uuid.UUID, org: CurrentOrg, db: DbSession
) -> ConsultationDetail:
    consultation = await svc.get_consultation(db, consultation_id, org.id)
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return ConsultationDetail.model_validate(consultation)


@router.post("/consultations/{consultation_id}/messages", response_model=TurnResponse)
async def post_message(
    consultation_id: uuid.UUID,
    payload: MessageCreate,
    org: CurrentOrg,
    user: CurrentUser,
    db: DbSession,
    model: AgentModel,
) -> TurnResponse:
    """Ask this executive a question and get its structured answer."""
    consultation = await svc.get_consultation(db, consultation_id, org.id)
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

    try:
        turn = await svc.send_message(
            db,
            consultation=consultation,
            content=payload.content,
            user_id=user.id,
            model=model,
        )
    except svc.ConsultationError as exc:
        raise _as_http(exc)

    return TurnResponse(
        user_message=turn.user_message,  # type: ignore[arg-type]
        agent_message=turn.agent_message,  # type: ignore[arg-type]
        structured=turn.response,
    )
