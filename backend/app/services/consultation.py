"""One-on-one executive consultations.

Orchestrates a single agent turn: load authorized context, replay prior
messages, run that executive's own agent, persist both sides of the exchange,
and record usage. Nothing here touches more than one agent.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass

from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.deps import CompanyContext, GhostBoardDeps
from app.agents.factory import build_bundle, get_bundle
from app.agents.pricing import estimate_cost
from app.agents.provider import ProviderNotConfigured
from app.agents.registry import AgentId, get_definition
from app.agents.schemas import ConsultationResponse
from app.core.config import settings
from app.mcp.context import ToolContext, bind_context
from app.models.consultation import Consultation, ConsultationMessage
from app.models.identity import CompanyProfile
from app.models.usage import LLMUsageRecord

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 12


class ConsultationError(RuntimeError):
    """A consultation turn failed in a way the user should be told about."""

    def __init__(self, message: str, *, code: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(slots=True)
class TurnResult:
    user_message: ConsultationMessage
    agent_message: ConsultationMessage
    response: ConsultationResponse


def _goal_strings(raw: list[dict] | None) -> tuple[str, ...]:
    """CompanyProfile stores these as JSONB dicts of varying shape."""
    if not raw:
        return ()
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            text = item.get("text") or item.get("title") or item.get("description")
            if text:
                out.append(str(text))
        elif isinstance(item, str):
            out.append(item)
    return tuple(out)


async def load_company_context(db: AsyncSession, organization_id: uuid.UUID) -> CompanyContext:
    """Build the authorized context slice for one organization."""
    profile = (
        await db.execute(
            select(CompanyProfile).where(CompanyProfile.organization_id == organization_id)
        )
    ).scalar_one_or_none()

    if profile is None:
        return CompanyContext()

    return CompanyContext(
        company_name=profile.company_name,
        industry=profile.industry,
        business_model=profile.business_model,
        stage=profile.stage,
        headcount=profile.headcount,
        description=profile.description,
        revenue_model=profile.revenue_model,
        arr_usd=profile.arr_usd,
        monthly_burn_usd=profile.monthly_burn_usd,
        cash_on_hand_usd=profile.cash_on_hand_usd,
        runway_months=profile.runway_months,
        annual_churn_rate=profile.annual_churn_rate,
        goals=_goal_strings(profile.goals),
        challenges=_goal_strings(profile.challenges),
        constraints=_goal_strings(profile.constraints),
    )


async def create_consultation(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    agent_id: str,
    title: str | None = None,
) -> Consultation:
    """Open a consultation with one roster executive."""
    definition = get_definition(agent_id)  # raises KeyError for anything invented
    if not definition.can_consult_one_on_one:
        raise ConsultationError(
            f"{definition.display_name} does not take one-on-one consultations.",
            code="agent_not_consultable",
            status_code=400,
        )

    consultation = Consultation(
        organization_id=organization_id,
        created_by_user_id=user_id,
        agent_id=definition.agent_id.value,
        title=title or f"Consultation with {definition.short_title}",
    )
    db.add(consultation)
    await db.flush()
    await db.refresh(consultation)
    return consultation


async def get_consultation(
    db: AsyncSession, consultation_id: uuid.UUID, organization_id: uuid.UUID
) -> Consultation | None:
    """Fetch with messages, scoped to the caller's organization."""
    return (
        await db.execute(
            select(Consultation)
            .where(
                Consultation.id == consultation_id,
                # Org scope is part of the query, not an afterthought check.
                Consultation.organization_id == organization_id,
            )
            .options(selectinload(Consultation.messages))
        )
    ).scalar_one_or_none()


async def _replay_history(db: AsyncSession, consultation_id: uuid.UUID) -> list[ModelMessage]:
    """Rebuild Pydantic AI message history from persisted turns."""
    rows = (
        (
            await db.execute(
                select(ConsultationMessage)
                .where(
                    ConsultationMessage.consultation_id == consultation_id,
                    ConsultationMessage.model_messages.is_not(None),
                )
                .order_by(ConsultationMessage.created_at)
            )
        )
        .scalars()
        .all()
    )

    history: list[ModelMessage] = []
    for row in rows[-MAX_HISTORY_TURNS:]:
        try:
            history.extend(ModelMessagesTypeAdapter.validate_python(row.model_messages))
        except Exception:  # noqa: BLE001 - a corrupt row must not kill the turn
            logger.warning(
                "Skipping unreadable message history on consultation message %s", row.id
            )
    return history


async def send_message(
    db: AsyncSession,
    *,
    consultation: Consultation,
    content: str,
    user_id: uuid.UUID | None,
    model: Model | None = None,
) -> TurnResult:
    """Run one consultation turn against this executive's own agent.

    ``model`` is injected by tests to run deterministically; production passes
    None and the agent uses the configured provider.
    """
    agent_id = AgentId(consultation.agent_id)
    definition = get_definition(consultation.agent_id)

    # A test-supplied model needs a freshly built agent; the cached one is
    # already bound to the configured provider.
    bundle = build_bundle(definition, model) if model is not None else get_bundle(agent_id)

    deps = GhostBoardDeps(
        organization_id=consultation.organization_id,
        user_id=user_id,
        agent_id=agent_id,
        company=await load_company_context(db, consultation.organization_id),
        consultation_id=consultation.id,
        allowed_tool_scopes=tuple(definition.tool_scopes),
    )

    history = await _replay_history(db, consultation.id)

    user_message = ConsultationMessage(
        consultation_id=consultation.id, role="user", content=content
    )
    db.add(user_message)
    await db.flush()

    started = time.perf_counter()
    try:
        with bind_context(
            ToolContext(
                organization_id=consultation.organization_id,
                agent_id=agent_id,
                allowed_scopes=frozenset(definition.tool_scopes),
                user_id=user_id,
                consultation_id=consultation.id,
            )
        ):
            async with bundle.consultation_agent:
                result = await bundle.consultation_agent.run(
                    content,
                    deps=deps,
                    message_history=history,
                    timeout=float(settings.model_timeout_seconds),
                )
    except ProviderNotConfigured as exc:
        raise ConsultationError(str(exc), code="provider_not_configured", status_code=503) from exc
    except UsageLimitExceeded as exc:
        raise ConsultationError(
            f"This consultation hit its usage limit: {exc}", code="usage_limit", status_code=429
        ) from exc
    except ModelHTTPError as exc:
        logger.exception("Model HTTP error for agent %s", agent_id)
        raise ConsultationError(
            f"The model provider returned an error ({exc.status_code}).",
            code="provider_error",
            status_code=502,
        ) from exc
    except UnexpectedModelBehavior as exc:
        logger.exception("Model produced unusable output for agent %s", agent_id)
        raise ConsultationError(
            "The model did not return a valid structured response after retries.",
            code="invalid_model_output",
            status_code=502,
        ) from exc
    except TimeoutError as exc:
        raise ConsultationError(
            f"The model did not respond within {settings.model_timeout_seconds}s.",
            code="model_timeout",
            status_code=504,
        ) from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    response: ConsultationResponse = result.output

    agent_message = ConsultationMessage(
        consultation_id=consultation.id,
        role="agent",
        agent_id=definition.agent_id.value,
        content=response.answer,
        structured_output=response.model_dump(mode="json"),
        model_messages=_as_jsonable(result),
    )
    db.add(agent_message)

    usage = result.usage
    db.add(
        LLMUsageRecord(
            organization_id=consultation.organization_id,
            consultation_id=consultation.id,
            agent_id=definition.agent_id.value,
            model_name=getattr(bundle.consultation_agent.model, "model_name", "unknown"),
            stage="consultation",
            request_count=usage.requests,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
            estimated_cost_usd=_cost_of(
                usage, getattr(bundle.consultation_agent.model, "model_name", "unknown")
            ),
            duration_ms=duration_ms,
        )
    )

    await db.flush()
    await db.refresh(agent_message)
    await db.refresh(user_message)

    logger.info(
        "Consultation %s turn complete: agent=%s tokens=%s duration=%sms",
        consultation.id,
        definition.agent_id.value,
        usage.input_tokens + usage.output_tokens,
        duration_ms,
    )
    return TurnResult(user_message=user_message, agent_message=agent_message, response=response)


def _as_jsonable(result: object) -> list:
    """Serialize this turn's new messages for replay on the next one."""
    return json.loads(result.new_messages_json())  # type: ignore[attr-defined]


def _cost_of(usage: object, model_name: str) -> float:
    """Provider cost, or 0.0 when no price is configured for this model.

    Previously this tried to read a cost off the usage object and always got
    nothing, so every row said 0.00 and nobody could tell that apart from a
    free call. Now the price table decides, and an unpriced model records 0.0
    with `pricing_is_configured()` available to say why.
    """
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    return estimate_cost(model_name, inp, out) or 0.0
