"""The board meeting state machine.

Plain asynchronous Python driving Pydantic AI agents through six stages. No
graph framework: the stages are sequential, the branching is shallow, and the
whole workflow fits in one readable file (spec section 6).

Two properties the design protects above convenience:

* **Independent assessments really are independent.** Stage 2 agents each get
  the question and the company context and nothing else — no colleague has
  spoken into their prompt. The isolation is structural, not a prompt request.
* **One agent failing does not restart the meeting.** Failures are recorded,
  the participant is marked skipped, and the meeting continues if enough
  executives remain to make the discussion meaningful.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.deps import CompanyContext, GhostBoardDeps
from app.agents.factory import build_bundle, build_chair_agents, get_bundle, get_chair_agents
from app.agents.meeting_schemas import (
    DebateAssignment,
    DebatePlanOutput,
    DecisionBriefOutput,
    MeetingAgendaOutput,
    ObjectionOutput,
    RevisionOutput,
)
from app.agents.registry import REGISTRY, AgentId, validate_agent_ids
from app.agents.schemas import AgentAssessmentOutput
from app.core.config import settings
from app.models.enums import (
    MeetingStage,
    MeetingStatus,
    ParticipantStatus,
)
from app.models.meeting import (
    AgentAssessment,
    AgentObjection,
    AgentRevision,
    Meeting,
    MeetingEvent,
    MeetingParticipant,
)
from app.models.usage import LLMUsageRecord
from app.orchestration.events import EventSink, EventType, MeetingEventModel, noop_sink

logger = logging.getLogger(__name__)

#: Executives who sit on the first working meeting (spec session 3).
DEFAULT_PARTICIPANTS: tuple[AgentId, ...] = (
    AgentId.CEO,
    AgentId.COO,
    AgentId.CFO,
    AgentId.STRATEGY_CONSULTANT,
)

#: Below this many completed assessments there is no board discussion to have.
MIN_ASSESSMENTS = 2


class MeetingCancelled(Exception):
    """Raised at a checkpoint when the user cancelled the meeting."""


class MeetingAborted(Exception):
    """The meeting cannot continue. Distinct from one agent failing."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class MeetingLimits:
    """Bounded execution. Defaults come from settings; tests shrink them."""

    max_debate_rounds: int = 1
    max_challenges_per_round: int = 4
    max_model_requests: int = 60
    model_timeout_seconds: float = 120.0
    max_assessment_concurrency: int = 4
    cost_limit_usd: float = 5.0

    @classmethod
    def from_settings(cls) -> MeetingLimits:
        return cls(
            max_debate_rounds=settings.max_debate_rounds,
            max_model_requests=settings.max_model_requests_per_meeting,
            model_timeout_seconds=float(settings.model_timeout_seconds),
            cost_limit_usd=settings.meeting_cost_limit_usd,
        )


@dataclass(slots=True)
class Budget:
    """Running tally across the whole meeting."""

    limits: MeetingLimits
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    failures: list[str] = field(default_factory=list)

    def would_exceed(self) -> bool:
        return self.model_requests >= self.limits.max_model_requests

    def record(self, usage: Any) -> None:
        self.model_requests += getattr(usage, "requests", 1) or 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0


@dataclass(slots=True)
class AgentRunOutcome[T]:
    """Either a validated output, or a recorded failure. Never an exception
    that unwinds the whole meeting."""

    agent_id: AgentId
    output: T | None = None
    error: str | None = None
    duration_ms: int = 0
    stage: str = ""
    model_name: str = "unknown"
    usage: Any = None

    @property
    def ok(self) -> bool:
        return self.output is not None


class MeetingOrchestrator:
    """Runs one meeting from question to decision brief."""

    def __init__(
        self,
        db: AsyncSession,
        meeting: Meeting,
        company: CompanyContext,
        *,
        limits: MeetingLimits | None = None,
        model: Model | None = None,
        sink: EventSink = noop_sink,
        user_id: uuid.UUID | None = None,
        candidates: tuple[AgentId, ...] = DEFAULT_PARTICIPANTS,
    ) -> None:
        self.db = db
        self.meeting = meeting
        self.company = company
        self.limits = limits or MeetingLimits.from_settings()
        self.model = model
        self.sink = sink
        self.user_id = user_id
        self.budget = Budget(limits=self.limits)
        self._sequence = 0
        # The Chair chooses from this pool, not the whole roster. Keeping
        # it explicit is what makes the call count predictable: an
        # Executive Meeting is four assessments, not nine.
        self.candidates = tuple(a for a in candidates if a is not AgentId.CHAIRPERSON)

        # A test-supplied model needs freshly built agents; the cached ones are
        # already bound to the configured provider.
        self._chair = build_chair_agents(model) if model is not None else get_chair_agents()

        self.assessments: dict[AgentId, AgentAssessmentOutput] = {}
        self.objections: list[tuple[DebateAssignment, ObjectionOutput]] = []
        self.revisions: dict[AgentId, RevisionOutput] = {}
        self.agenda: MeetingAgendaOutput | None = None

    # -- infrastructure ----------------------------------------------------

    def _bundle(self, agent_id: AgentId):
        definition = REGISTRY[agent_id]
        return build_bundle(definition, self.model) if self.model is not None else get_bundle(agent_id)

    def _deps(self, agent_id: AgentId) -> GhostBoardDeps:
        definition = REGISTRY[agent_id]
        return GhostBoardDeps(
            organization_id=self.meeting.organization_id,
            user_id=self.user_id,
            agent_id=agent_id,
            company=self.company,
            meeting_id=self.meeting.id,
            allowed_tool_scopes=tuple(definition.tool_scopes),
        )

    async def _emit(
        self, event_type: EventType, *, agent_id: AgentId | str | None = None, **payload: Any
    ) -> None:
        """Persist an event, then hand it to the sink. Order matters: a listener
        must never see something the database does not have."""
        self._sequence += 1
        event = MeetingEventModel(
            meeting_id=self.meeting.id,
            sequence_number=self._sequence,
            event_type=event_type,
            agent_id=str(agent_id) if agent_id else None,
            payload=payload,
        )
        self.db.add(
            MeetingEvent(
                id=event.event_id,
                meeting_id=event.meeting_id,
                sequence_number=event.sequence_number,
                event_type=event.event_type.value,
                agent_id=event.agent_id,
                payload=event.payload,
                timestamp=event.timestamp,
            )
        )
        await self.db.flush()
        await self.sink(event)

    async def _checkpoint(self) -> None:
        """Cancellation and budget check, between stages and before each wave."""
        await self.db.refresh(self.meeting, ["status"])
        if self.meeting.status is MeetingStatus.CANCELLED:
            raise MeetingCancelled
        if self.budget.would_exceed():
            raise MeetingAborted(
                f"Meeting hit its model request ceiling "
                f"({self.budget.model_requests}/{self.limits.max_model_requests}).",
                code="model_request_limit",
            )

    async def _set_stage(self, stage: MeetingStage) -> None:
        self.meeting.stage = stage
        await self.db.flush()
        await self._emit(EventType.STAGE_CHANGED, stage=stage.value)

    async def _set_participant_status(
        self, agent_id: AgentId, status: ParticipantStatus
    ) -> None:
        participant = (
            await self.db.execute(
                select(MeetingParticipant).where(
                    MeetingParticipant.meeting_id == self.meeting.id,
                    MeetingParticipant.agent_id == agent_id.value,
                )
            )
        ).scalar_one_or_none()
        if participant is not None:
            participant.status = status
            await self.db.flush()
        await self._emit(EventType.AGENT_STATUS_CHANGED, agent_id=agent_id, status=status.value)

    async def _invoke_agent[T: BaseModel](
        self,
        agent: Agent[GhostBoardDeps, T],
        agent_id: AgentId,
        prompt: str,
        *,
        stage: str,
    ) -> AgentRunOutcome[T]:
        """Call one agent. Touches no database.

        This is the partial-failure boundary: nothing below it raises past
        here except cancellation, so a single bad agent cannot take down the
        meeting or trigger a whole-meeting retry.

        Keeping it DB-free is what makes Stage 2 safe to run concurrently —
        an AsyncSession cannot be shared across simultaneous coroutines, so
        every write happens on the serial path in ``_record_outcome``.
        """
        started = time.perf_counter()
        model_name = getattr(agent.model, "model_name", "unknown")
        try:
            result = await agent.run(
                prompt, deps=self._deps(agent_id), timeout=self.limits.model_timeout_seconds
            )
        # Deliberately broad. Any failure of one agent — a provider error, an
        # unparseable response, a timeout, or a bug in a tool — is one
        # executive missing from the room, not a reason to restart the
        # meeting. asyncio.CancelledError is a BaseException and still
        # propagates, so real cancellation is unaffected.
        except Exception as exc:  # noqa: BLE001
            duration = int((time.perf_counter() - started) * 1000)
            message = f"{type(exc).__name__}: {exc}"
            logger.warning("Agent %s failed during %s: %s", agent_id.value, stage, message)
            return AgentRunOutcome(
                agent_id=agent_id,
                error=message,
                duration_ms=duration,
                stage=stage,
                model_name=model_name,
            )

        return AgentRunOutcome(
            agent_id=agent_id,
            output=result.output,
            duration_ms=int((time.perf_counter() - started) * 1000),
            stage=stage,
            model_name=model_name,
            usage=result.usage,
        )

    async def _record_outcome(self, outcome: AgentRunOutcome[Any]) -> None:
        """Persist usage and, on failure, the failure event. Serial only."""
        if outcome.ok:
            self.budget.record(outcome.usage)
            inp = getattr(outcome.usage, "input_tokens", 0) or 0
            out = getattr(outcome.usage, "output_tokens", 0) or 0
            self.db.add(
                LLMUsageRecord(
                    organization_id=self.meeting.organization_id,
                    meeting_id=self.meeting.id,
                    agent_id=outcome.agent_id.value,
                    model_name=outcome.model_name,
                    stage=outcome.stage,
                    request_count=getattr(outcome.usage, "requests", 1) or 1,
                    input_tokens=inp,
                    output_tokens=out,
                    total_tokens=inp + out,
                    duration_ms=outcome.duration_ms,
                )
            )
            await self.db.flush()
            return

        self.budget.failures.append(f"{outcome.agent_id.value}/{outcome.stage}")
        self.db.add(
            LLMUsageRecord(
                organization_id=self.meeting.organization_id,
                meeting_id=self.meeting.id,
                agent_id=outcome.agent_id.value,
                model_name=outcome.model_name,
                stage=outcome.stage,
                request_count=0,
                duration_ms=outcome.duration_ms,
                error_message=(outcome.error or "")[:2000],
            )
        )
        await self._emit(
            EventType.AGENT_FAILED,
            agent_id=outcome.agent_id,
            stage=outcome.stage,
            error=(outcome.error or "")[:500],
        )

    async def _run_agent[T: BaseModel](
        self,
        agent: Agent[GhostBoardDeps, T],
        agent_id: AgentId,
        prompt: str,
        *,
        stage: str,
    ) -> AgentRunOutcome[T]:
        """Call an agent and record the result. For serial stages only."""
        outcome = await self._invoke_agent(agent, agent_id, prompt, stage=stage)
        await self._record_outcome(outcome)
        return outcome

    # -- stages ------------------------------------------------------------

    async def _stage_agenda(self) -> list[AgentId]:
        """Stage 1. The Chair frames the question and picks the room."""
        await self._set_stage(MeetingStage.AGENDA)
        await self._emit(EventType.AGENT_STARTED, agent_id=AgentId.CHAIRPERSON, stage="agenda")

        roster_lines = "\n".join(
            f"- {d.agent_id.value}: {d.title} — {d.expertise_descriptor}"
            for d in REGISTRY.values()
            if not d.can_chair
        )
        prompt = (
            f"The founder asks:\n\n{self.meeting.question}\n\n"
            f"Executives available:\n{roster_lines}\n\n"
            "Frame the meeting: restate the real question, set the agenda, and "
            "choose who should contribute."
        )

        outcome = await self._run_agent(
            self._chair.agenda_agent, AgentId.CHAIRPERSON, prompt, stage="agenda"
        )
        if not outcome.ok:
            raise MeetingAborted(
                f"The Chairperson could not produce an agenda: {outcome.error}",
                code="agenda_failed",
            )

        agenda = outcome.output
        assert agenda is not None
        self.agenda = agenda

        # The model proposes participants; the registry decides who exists.
        proposed = validate_agent_ids([p.agent_id for p in agenda.participants])
        # Intersect with the candidate pool: the registry says who exists, the
        # pool says who is in the room today. A model-proposed id satisfies
        # neither on its own.
        selected = [
            a for a in proposed if a is not AgentId.CHAIRPERSON and a in self.candidates
        ]
        if not selected:
            logger.warning("Chair selected no valid participants; falling back to the pool")
            selected = list(self.candidates)

        self.meeting.agenda = agenda.model_dump(mode="json")
        await self._persist_participants(selected, agenda)
        await self._emit(
            EventType.AGENDA_CREATED,
            agent_id=AgentId.CHAIRPERSON,
            reframed_question=agenda.reframed_question,
            agenda_items=[i.model_dump(mode="json") for i in agenda.agenda_items],
            participants=[a.value for a in selected],
            tensions_to_test=agenda.tensions_to_test,
        )
        return selected

    async def _persist_participants(
        self, selected: list[AgentId], agenda: MeetingAgendaOutput
    ) -> None:
        reasons = {p.agent_id: p.reason for p in agenda.participants}
        existing = {
            p.agent_id
            for p in (
                await self.db.execute(
                    select(MeetingParticipant).where(
                        MeetingParticipant.meeting_id == self.meeting.id
                    )
                )
            )
            .scalars()
            .all()
        }
        for order, agent_id in enumerate([AgentId.CHAIRPERSON, *selected]):
            if agent_id.value in existing:
                continue
            self.db.add(
                MeetingParticipant(
                    meeting_id=self.meeting.id,
                    agent_id=agent_id.value,
                    selection_reason=(
                        "Chairs the meeting"
                        if agent_id is AgentId.CHAIRPERSON
                        else reasons.get(agent_id.value)
                    ),
                    speaking_order=order,
                    status=ParticipantStatus.WAITING,
                )
            )
        await self.db.flush()

    async def _stage_assessments(self, participants: list[AgentId]) -> None:
        """Stages 2 and 3. Independent analysis, run concurrently, then persisted.

        Each agent sees only the question and the company context. No
        colleague's output is in scope here — that is the whole point.
        """
        await self._set_stage(MeetingStage.ASSESSMENTS)

        question = self.agenda.reframed_question if self.agenda else self.meeting.question
        agenda_block = ""
        if self.agenda:
            agenda_block = "\n".join(
                f"- {item.title}: {item.question}" for item in self.agenda.agenda_items
            )

        prompt = (
            f"The board is deciding:\n\n{question}\n\n"
            f"The founder originally asked:\n{self.meeting.question}\n\n"
            + (f"Agenda:\n{agenda_block}\n\n" if agenda_block else "")
            + "Give your independent assessment."
        )

        # Announce everyone first, serially, then fan out. The agent calls
        # below run concurrently and must not touch the session.
        for agent_id in participants:
            await self._set_participant_status(agent_id, ParticipantStatus.SPEAKING)
            await self._emit(EventType.AGENT_STARTED, agent_id=agent_id, stage="assessment")

        semaphore = asyncio.Semaphore(self.limits.max_assessment_concurrency)

        async def one(agent_id: AgentId) -> AgentRunOutcome[AgentAssessmentOutput]:
            async with semaphore:
                return await self._invoke_agent(
                    self._bundle(agent_id).assessment_agent,
                    agent_id,
                    prompt,
                    stage="assessment",
                )

        await self._checkpoint()
        outcomes = await asyncio.gather(*(one(a) for a in participants))

        # Back on the serial path: every database write happens here.
        for outcome in outcomes:
            await self._record_outcome(outcome)
            if not outcome.ok:
                await self._set_participant_status(outcome.agent_id, ParticipantStatus.SKIPPED)
                continue
            assessment = outcome.output
            assert assessment is not None
            self.assessments[outcome.agent_id] = assessment
            await self._persist_assessment(outcome.agent_id, assessment, round_number=0)
            await self._set_participant_status(outcome.agent_id, ParticipantStatus.COMPLETED)
            await self._emit(
                EventType.AGENT_MESSAGE_COMPLETED,
                agent_id=outcome.agent_id,
                stage="assessment",
                summary=assessment.summary,
                recommended_position=assessment.recommended_position,
                confidence_level=assessment.confidence_level.value,
            )

        if len(self.assessments) < MIN_ASSESSMENTS:
            raise MeetingAborted(
                f"Only {len(self.assessments)} executive(s) completed an assessment; "
                f"at least {MIN_ASSESSMENTS} are needed for a board discussion.",
                code="insufficient_assessments",
            )

    async def _persist_assessment(
        self, agent_id: AgentId, assessment: AgentAssessmentOutput, *, round_number: int
    ) -> None:
        self.db.add(
            AgentAssessment(
                meeting_id=self.meeting.id,
                agent_id=agent_id.value,
                round_number=round_number,
                summary=assessment.summary,
                recommended_position=assessment.recommended_position,
                supporting_arguments=[a.model_dump(mode="json") for a in assessment.supporting_arguments],
                evidence_references=[e.model_dump(mode="json") for e in assessment.evidence_references],
                assumptions=[a.model_dump(mode="json") for a in assessment.assumptions],
                risks=[r.model_dump(mode="json") for r in assessment.risks],
                opportunities=[o.model_dump(mode="json") for o in assessment.opportunities],
                open_questions=[q.model_dump(mode="json") for q in assessment.open_questions],
                confidence_level=assessment.confidence_level,
            )
        )
        await self.db.flush()

    def _positions_block(self, exclude: AgentId | None = None) -> str:
        """The actual structured positions, rendered for a colleague to read."""
        blocks: list[str] = []
        for agent_id, assessment in self.assessments.items():
            if agent_id is exclude:
                continue
            definition = REGISTRY[agent_id]
            risks = "; ".join(r.description for r in assessment.risks[:3]) or "none stated"
            assumptions = (
                "; ".join(a.statement for a in assessment.assumptions[:3]) or "none stated"
            )
            blocks.append(
                f"### {definition.display_name} ({definition.title}) "
                f"[agent_id: {agent_id.value}]\n"
                f"Position: {assessment.recommended_position}\n"
                f"Summary: {assessment.summary}\n"
                f"Key assumptions: {assumptions}\n"
                f"Risks they flag: {risks}\n"
                f"Confidence: {assessment.confidence_level.value}"
            )
        return "\n\n".join(blocks)

    async def _stage_debate(self, round_number: int) -> list[DebateAssignment]:
        """Stage 4. The Chair finds real conflicts; challengers respond to them."""
        await self._set_stage(MeetingStage.DEBATE)
        await self._emit(EventType.AGENT_STARTED, agent_id=AgentId.CHAIRPERSON, stage="debate_plan")

        prompt = (
            f"Question before the board:\n{self.agenda.reframed_question if self.agenda else self.meeting.question}\n\n"
            f"Independent assessments:\n\n{self._positions_block()}\n\n"
            "Identify the genuine conflicts and assign challenges. If they "
            "substantially agree, return no assignments."
        )
        plan_outcome = await self._run_agent(
            self._chair.debate_agent, AgentId.CHAIRPERSON, prompt, stage="debate_plan"
        )

        if not plan_outcome.ok:
            # A failed debate plan degrades the meeting; it does not end it.
            logger.warning("Debate planning failed; proceeding to synthesis")
            return []

        plan: DebatePlanOutput = plan_outcome.output  # type: ignore[assignment]
        assignments = self._validate_assignments(plan.assignments)
        await self._emit(
            EventType.AGENT_MESSAGE_COMPLETED,
            agent_id=AgentId.CHAIRPERSON,
            stage="debate_plan",
            conflicts_found=plan.conflicts_found,
            rationale=plan.rationale,
            assignment_count=len(assignments),
        )
        if not assignments:
            return []

        for assignment in assignments:
            await self._checkpoint()
            challenger = AgentId(assignment.challenger_agent_id)
            target = AgentId(assignment.target_agent_id)
            target_assessment = self.assessments[target]
            target_def = REGISTRY[target]

            await self._set_participant_status(challenger, ParticipantStatus.CHALLENGING)
            prompt = (
                f"Question before the board:\n"
                f"{self.agenda.reframed_question if self.agenda else self.meeting.question}\n\n"
                f"{target_def.display_name}, {target_def.title}, concluded:\n"
                f"Position: {target_assessment.recommended_position}\n"
                f"Reasoning: {target_assessment.summary}\n"
                f"Their assumptions: "
                f"{'; '.join(a.statement for a in target_assessment.assumptions) or 'none stated'}\n\n"
                f"The Chair has asked you to respond to this specific claim:\n"
                f'"{assignment.claim_to_challenge}"\n\n'
                f"Why it matters: {assignment.why_this_conflict_matters}\n\n"
                f"Your own position was:\n"
                f"{self.assessments[challenger].recommended_position}\n\n"
                "Respond to their claim."
            )
            outcome = await self._run_agent(
                self._bundle(challenger).objection_agent,
                challenger,
                prompt,
                stage="objection",
            )
            if not outcome.ok:
                await self._set_participant_status(challenger, ParticipantStatus.COMPLETED)
                continue

            objection: ObjectionOutput = outcome.output  # type: ignore[assignment]
            self.objections.append((assignment, objection))
            self.db.add(
                AgentObjection(
                    meeting_id=self.meeting.id,
                    source_agent_id=challenger.value,
                    target_agent_id=target.value,
                    round_number=round_number,
                    challenged_claim=objection.challenged_claim,
                    objection=objection.objection,
                    supporting_evidence=objection.supporting_evidence,
                    severity=objection.severity,
                    proposed_resolution=objection.proposed_resolution,
                )
            )
            await self.db.flush()
            await self._set_participant_status(challenger, ParticipantStatus.COMPLETED)
            await self._emit(
                EventType.OBJECTION_RAISED,
                agent_id=challenger,
                target_agent_id=target.value,
                stance=objection.stance,
                challenged_claim=objection.challenged_claim,
                objection=objection.objection,
                severity=objection.severity.value,
            )

        return assignments

    def _validate_assignments(
        self, assignments: list[DebateAssignment]
    ) -> list[DebateAssignment]:
        """Drop anything the Chair invented: unknown ids, absent executives,
        self-challenges, or challenges to someone with no assessment."""
        valid: list[DebateAssignment] = []
        for assignment in assignments:
            try:
                challenger = AgentId(assignment.challenger_agent_id)
                target = AgentId(assignment.target_agent_id)
            except ValueError:
                logger.warning("Chair proposed an unknown agent id; dropping assignment")
                continue
            if challenger == target:
                continue
            if challenger not in self.assessments or target not in self.assessments:
                logger.warning(
                    "Chair assigned a challenge involving an agent with no assessment; dropping"
                )
                continue
            valid.append(assignment)
            if len(valid) >= self.limits.max_challenges_per_round:
                break
        return valid

    async def _stage_revisions(self, assignments: list[DebateAssignment], round_number: int) -> None:
        """Stage 5. Challenged executives get to move, or to hold."""
        await self._set_stage(MeetingStage.REVISIONS)

        # Only agents who were actually challenged are asked to reconsider.
        challenged: dict[AgentId, list[tuple[DebateAssignment, ObjectionOutput]]] = {}
        for assignment, objection in self.objections:
            target = AgentId(assignment.target_agent_id)
            challenged.setdefault(target, []).append((assignment, objection))

        for target, items in challenged.items():
            await self._checkpoint()
            original = self.assessments[target]
            objection_block = "\n\n".join(
                f"{REGISTRY[AgentId(a.challenger_agent_id)].display_name} "
                f"({REGISTRY[AgentId(a.challenger_agent_id)].title}) says:\n"
                f"Stance: {o.stance}\n"
                f"On your claim: {o.challenged_claim}\n"
                f"Their argument: {o.objection}\n"
                f"Severity if they are right: {o.severity.value}"
                for a, o in items
            )
            prompt = (
                f"Your position was:\n{original.recommended_position}\n\n"
                f"Your reasoning was:\n{original.summary}\n\n"
                f"You have been challenged:\n\n{objection_block}\n\n"
                "Where do you stand now?"
            )
            outcome = await self._run_agent(
                self._bundle(target).revision_agent, target, prompt, stage="revision"
            )
            if not outcome.ok:
                continue

            revision: RevisionOutput = outcome.output  # type: ignore[assignment]
            self.revisions[target] = revision
            self.db.add(
                AgentRevision(
                    meeting_id=self.meeting.id,
                    agent_id=target.value,
                    round_number=round_number,
                    original_position=original.recommended_position,
                    updated_position=revision.updated_position,
                    reason_for_change=revision.reason_for_change,
                    evidence_considered=revision.evidence_considered,
                )
            )
            await self.db.flush()
            await self._emit(
                EventType.POSITION_REVISED,
                agent_id=target,
                position_changed=revision.position_changed,
                original_position=original.recommended_position,
                updated_position=revision.updated_position,
                reason_for_change=revision.reason_for_change,
            )

    async def _stage_synthesis(self) -> DecisionBriefOutput:
        """Stage 6. The Chair writes the brief from what was actually said."""
        await self._set_stage(MeetingStage.SYNTHESIS)
        await self._emit(EventType.AGENT_STARTED, agent_id=AgentId.CHAIRPERSON, stage="synthesis")

        objection_block = (
            "\n\n".join(
                f"{REGISTRY[AgentId(a.challenger_agent_id)].display_name} → "
                f"{REGISTRY[AgentId(a.target_agent_id)].display_name}\n"
                f"Stance: {o.stance} (severity {o.severity.value})\n"
                f"Claim challenged: {o.challenged_claim}\n"
                f"Argument: {o.objection}"
                for a, o in self.objections
            )
            or "No objections were raised; the executives substantially agreed."
        )
        revision_block = (
            "\n\n".join(
                f"{REGISTRY[agent_id].display_name}: "
                f"{'CHANGED' if r.position_changed else 'HELD'}\n"
                f"Now: {r.updated_position}\n"
                f"Why: {r.reason_for_change}"
                for agent_id, r in self.revisions.items()
            )
            or "No executive revised a position."
        )

        prompt = (
            f"Original question from the founder:\n{self.meeting.question}\n\n"
            f"How you reframed it:\n"
            f"{self.agenda.reframed_question if self.agenda else '(no reframing)'}\n\n"
            f"=== Independent assessments ===\n\n{self._positions_block()}\n\n"
            f"=== Objections raised in debate ===\n\n{objection_block}\n\n"
            f"=== Revisions after debate ===\n\n{revision_block}\n\n"
            "Write the decision brief."
        )

        outcome = await self._run_agent(
            self._chair.synthesis_agent, AgentId.CHAIRPERSON, prompt, stage="synthesis"
        )
        if not outcome.ok:
            raise MeetingAborted(
                f"The Chairperson could not produce a decision brief: {outcome.error}",
                code="synthesis_failed",
            )
        brief: DecisionBriefOutput = outcome.output  # type: ignore[assignment]
        await self._emit(
            EventType.DECISION_GENERATED,
            agent_id=AgentId.CHAIRPERSON,
            recommended_option_id=brief.recommended_option_id,
            option_count=len(brief.strategic_options),
            dissent_count=len(brief.dissenting_opinions),
            confidence_level=brief.confidence_level.value,
        )
        return brief

    # -- entry point -------------------------------------------------------

    async def run(self) -> DecisionBriefOutput:
        """Execute the meeting. Raises MeetingAborted or MeetingCancelled."""
        self.meeting.status = MeetingStatus.RUNNING
        self.meeting.started_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(
            EventType.MEETING_STARTED,
            question=self.meeting.question,
            mode=self.meeting.mode.value,
        )

        try:
            participants = await self._stage_agenda()

            await self._checkpoint()
            await self._stage_assessments(participants)

            rounds = max(1, self.limits.max_debate_rounds)
            for round_number in range(1, rounds + 1):
                await self._checkpoint()
                assignments = await self._stage_debate(round_number)
                if not assignments:
                    # Nothing to argue about; further rounds would only invite
                    # the Chair to invent a conflict.
                    break
                await self._checkpoint()
                await self._stage_revisions(assignments, round_number)
                self.meeting.debate_rounds_used = round_number

            await self._checkpoint()
            brief = await self._stage_synthesis()

        except MeetingCancelled:
            self.meeting.status = MeetingStatus.CANCELLED
            await self._finalise()
            await self._emit(EventType.MEETING_CANCELLED)
            raise
        except MeetingAborted as exc:
            self.meeting.status = MeetingStatus.FAILED
            self.meeting.failure_reason = str(exc)
            await self._finalise()
            await self._emit(EventType.MEETING_FAILED, code=exc.code, reason=str(exc))
            raise

        self.meeting.status = MeetingStatus.COMPLETED
        self.meeting.stage = MeetingStage.PERSISTED
        self.meeting.completed_at = datetime.now(UTC)
        await self._finalise()
        await self._emit(
            EventType.MEETING_COMPLETED,
            model_requests=self.budget.model_requests,
            total_tokens=self.budget.input_tokens + self.budget.output_tokens,
            assessments=len(self.assessments),
            objections=len(self.objections),
            revisions=len(self.revisions),
            agent_failures=self.budget.failures,
        )
        return brief

    async def _finalise(self) -> None:
        self.meeting.model_requests_used = self.budget.model_requests
        self.meeting.estimated_cost_usd = self.budget.estimated_cost_usd
        await self.db.flush()
