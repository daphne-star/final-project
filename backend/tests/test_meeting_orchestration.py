"""The meeting engine: stages, independence, debate, revision, persistence."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents.deps import CompanyContext
from app.agents.factory import reset_agent_cache
from app.agents.registry import REGISTRY, AgentId
from app.models.enums import MeetingMode, MeetingStage, MeetingStatus, ParticipantStatus
from app.models.meeting import (
    MeetingEvent,
    MeetingParticipant,
)
from app.models.usage import LLMUsageRecord
from app.orchestration.events import EventType
from app.orchestration.meeting import (
    MeetingAborted,
    MeetingCancelled,
    MeetingLimits,
    MeetingOrchestrator,
    summarize_agent_error,
)
from app.services import meeting as svc
from app.services.consultation import load_company_context
from tests.board_model import agent_ids_seen, scripted_board

QUESTION = (
    "Should we prioritise improving retention, international expansion, "
    "or launching a new product?"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


async def _make_meeting(db, org, user):
    return await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        mode=MeetingMode.EXECUTIVE_MEETING,
    )


async def _run(db, org, user, **board_kwargs):
    """Run a full meeting against the scripted board."""
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board(**board_kwargs)
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=model,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
        user_id=user.id,
    )
    brief = await orch.run()
    return meeting, board, orch, brief


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


async def test_meeting_runs_every_stage_in_order(db, org_and_user):
    org, user = org_and_user
    meeting, board, _, brief = await _run(db, org, user)

    assert meeting.status is MeetingStatus.COMPLETED
    assert meeting.stage is MeetingStage.PERSISTED
    assert brief.recommended_option_id == "retention"

    # Agenda, four assessments, debate plan, objections, revisions, synthesis.
    kinds = board.kinds()
    assert kinds[0] == "agenda"
    assert kinds.count("assessment") == 4
    assert "debate_plan" in kinds
    assert kinds.count("objection") == 2
    assert kinds[-1] == "synthesis"
    # Stage order is not interleaved: all assessments precede the debate plan.
    assert max(i for i, k in enumerate(kinds) if k == "assessment") < kinds.index("debate_plan")


async def test_model_call_count_is_small_and_predictable(db, org_and_user):
    """A simple meeting should not balloon into dozens of calls."""
    org, user = org_and_user
    _, board, orch, _ = await _run(db, org, user)

    # 1 agenda + 4 assessments + 1 debate plan + 2 objections + 1 revision
    # (both challenges target the CEO, who revises once) + 1 synthesis.
    assert len(board.calls) == 10
    assert orch.budget.model_requests == 10


# --------------------------------------------------------------------------
# Independence — the property the whole product rests on
# --------------------------------------------------------------------------


async def test_assessments_are_produced_without_seeing_colleagues(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user)

    assessment_calls = board.of_kind("assessment")
    assert len(assessment_calls) == 4

    other_positions = [
        "Launch the new product; it is the only option",
        "Improve retention; we do not have the delivery capacity",
        "a false choice",
    ]
    for call in assessment_calls:
        for fragment in other_positions:
            assert fragment not in call.prompt, (
                f"{call.agent_id} saw a colleague's position during independent analysis"
            )
        # Nor are colleagues named as having concluded anything.
        assert "concluded" not in call.prompt


async def test_each_assessment_goes_to_a_different_executive(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user)
    assert agent_ids_seen(board, "assessment") == {"ceo", "coo", "cfo", "strategy_consultant"}


async def test_only_the_chairperson_runs_agenda_and_synthesis(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user)
    chair = REGISTRY[AgentId.CHAIRPERSON].display_name

    for kind in ("agenda", "debate_plan", "synthesis"):
        for call in board.of_kind(kind):
            assert chair in call.instructions
    # And the Chair never produces an assessment.
    assert "chairperson" not in agent_ids_seen(board, "assessment")


# --------------------------------------------------------------------------
# Debate and revision
# --------------------------------------------------------------------------


async def test_challengers_receive_the_actual_claim_being_challenged(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user)

    for call in board.of_kind("objection"):
        # The target's real position text, not a summary of it.
        assert "Launch the new product" in call.prompt
        assert "Marcus Lindqvist" in call.prompt  # the CEO, by name
        assert "The Chair has asked you to respond" in call.prompt


async def test_revision_prompt_contains_the_objection_raised(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user)

    revisions = board.of_kind("revision")
    assert len(revisions) == 1
    prompt = revisions[0].prompt
    assert "consumes runway" in prompt
    assert "Your position was" in prompt


async def test_agreement_produces_no_manufactured_debate(db, org_and_user):
    """When the Chair finds no conflict, nobody is told to argue."""
    org, user = org_and_user
    _, board, _, brief = await _run(db, org, user, produce_conflict=False)

    assert board.of_kind("objection") == []
    assert board.of_kind("revision") == []
    assert brief.recommended_option_id == "retention"
    assert len(board.calls) == 7  # agenda + 4 assessments + debate plan + synthesis


async def test_chair_cannot_assign_a_challenge_to_an_invented_agent(db, org_and_user):
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board()
    board._debate_plan = lambda _: {  # type: ignore[method-assign]
        "conflicts_found": True,
        "assignments": [
            {
                "challenger_agent_id": "head_of_vibes",
                "target_agent_id": "ceo",
                "claim_to_challenge": "x",
                "why_this_conflict_matters": "y",
            },
            {
                "challenger_agent_id": "cfo",
                "target_agent_id": "cfo",
                "claim_to_challenge": "self challenge",
                "why_this_conflict_matters": "y",
            },
        ],
        "rationale": "invented",
    }
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(db, meeting, company, model=model, user_id=user.id)
    await orch.run()

    # Unknown agent dropped, self-challenge dropped, so no objections ran.
    assert orch.objections == []
    assert board.of_kind("objection") == []


# --------------------------------------------------------------------------
# Persistence and retrieval
# --------------------------------------------------------------------------


async def test_all_contributions_are_retrievable_after_completion(db, org_and_user):
    org, user = org_and_user
    meeting, _, orch, brief = await _run(db, org, user)
    decision = await svc.persist_decision(db, meeting, brief, orch)

    parts = await svc.get_meeting_contributions(db, meeting.id)
    assert len(parts["assessments"]) == 4
    assert len(parts["objections"]) == 2
    assert len(parts["revisions"]) == 1
    assert parts["decision"] is not None
    assert parts["decision"].id == decision.id

    stored = parts["assessments"][0]
    assert stored.summary
    assert stored.recommended_position
    assert stored.assumptions and stored.risks


async def test_participants_are_persisted_with_final_status(db, org_and_user):
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user)

    rows = (
        (
            await db.execute(
                select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting.id)
            )
        )
        .scalars()
        .all()
    )
    by_id = {p.agent_id: p for p in rows}
    assert set(by_id) == {"chairperson", "ceo", "coo", "cfo", "strategy_consultant"}
    for agent_id in ("ceo", "coo", "cfo", "strategy_consultant"):
        assert by_id[agent_id].status is ParticipantStatus.COMPLETED
        assert by_id[agent_id].selection_reason


async def test_events_are_persisted_in_sequence(db, org_and_user):
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user)

    events = await svc.list_events(db, meeting.id)
    sequences = [e.sequence_number for e in events]
    assert sequences == sorted(sequences)
    assert sequences == list(range(1, len(sequences) + 1))

    types = [e.event_type for e in events]
    assert types[0] == EventType.MEETING_STARTED.value
    assert types[-1] == EventType.MEETING_COMPLETED.value
    for expected in (
        EventType.AGENDA_CREATED,
        EventType.OBJECTION_RAISED,
        EventType.POSITION_REVISED,
        EventType.DECISION_GENERATED,
    ):
        assert expected.value in types


async def test_events_can_be_replayed_from_a_cursor(db, org_and_user):
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user)

    everything = await svc.list_events(db, meeting.id)
    tail = await svc.list_events(db, meeting.id, after_sequence=5)
    assert [e.sequence_number for e in tail] == [
        e.sequence_number for e in everything if e.sequence_number > 5
    ]


async def test_decision_brief_records_dissent_and_open_questions(db, org_and_user):
    org, user = org_and_user
    meeting, _, orch, brief = await _run(db, org, user)
    decision = await svc.persist_decision(db, meeting, brief, orch)

    assert decision.dissenting_opinions
    assert decision.dissenting_opinions[0]["agent_id"] == "ceo"
    assert decision.unresolved_questions
    assert len(decision.strategic_options) == 2

    # Dissent is attributed on the per-agent positions too.
    dissenters = [p for p in decision.positions if p.is_dissent]
    assert [p.agent_id for p in dissenters] == ["ceo"]
    assert len(decision.positions) == 4


async def test_action_plan_is_split_into_30_60_90(db, org_and_user):
    org, user = org_and_user
    meeting, _, orch, brief = await _run(db, org, user)
    decision = await svc.persist_decision(db, meeting, brief, orch)

    windows = sorted(
        next(d for d in item.dependencies if d.startswith("window:"))
        for item in decision.action_items
    )
    assert windows == ["window:0-30 days", "window:30-60 days", "window:60-90 days"]


async def test_usage_is_recorded_per_agent_and_stage(db, org_and_user):
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user)

    records = (
        (await db.execute(select(LLMUsageRecord).where(LLMUsageRecord.meeting_id == meeting.id)))
        .scalars()
        .all()
    )
    assert len(records) == 10
    stages = {r.stage for r in records}
    assert stages == {"agenda", "assessment", "debate_plan", "objection", "revision", "synthesis"}
    assert meeting.model_requests_used == 10


async def test_the_meeting_keeps_its_own_token_total(db, org_and_user):
    """The figure the UI shows has to survive the meeting ending.

    Per-call counts were already on llm_usage_records, but nothing summed
    them onto the meeting, so reopening a finished one had only a request
    count to show.
    """
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user)

    records = (
        (await db.execute(select(LLMUsageRecord).where(LLMUsageRecord.meeting_id == meeting.id)))
        .scalars()
        .all()
    )
    assert meeting.input_tokens_used == sum(r.input_tokens for r in records)
    assert meeting.output_tokens_used == sum(r.output_tokens for r in records)
    assert meeting.total_tokens_used == meeting.input_tokens_used + meeting.output_tokens_used
    # A real run cannot cost nothing; a zero here would mean the model is not
    # reporting usage and the display would be quietly wrong.
    assert meeting.total_tokens_used > 0


async def test_a_running_meeting_reports_tokens_as_it_goes(db, org_and_user):
    """Stage changes carry the running total, so the count is live."""
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user)

    totals = [
        e.payload.get("total_tokens")
        for e in (
            await db.execute(
                select(MeetingEvent)
                .where(
                    MeetingEvent.meeting_id == meeting.id,
                    MeetingEvent.event_type == EventType.STAGE_CHANGED.value,
                )
                .order_by(MeetingEvent.sequence_number)
            )
        )
        .scalars()
        .all()
    ]

    assert all(t is not None for t in totals), "a stage change carried no token total"
    assert totals == sorted(totals), "the running total went backwards"
    assert totals[-1] > 0
    # The last stage change precedes synthesis, so it cannot already hold the
    # final figure -- but it must not exceed it either.
    assert totals[-1] <= meeting.total_tokens_used


async def test_a_failed_meeting_still_reports_what_it_spent(db, org_and_user):
    """Tokens are spent whether or not a brief comes out the other end."""
    from pydantic_ai.models.function import FunctionModel

    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)

    async def always_fails(messages, info):
        raise RuntimeError("provider exploded")

    orch = MeetingOrchestrator(
        db,
        meeting,
        await load_company_context(db, org.id),
        model=FunctionModel(always_fails, model_name="failing"),
        user_id=user.id,
    )
    with pytest.raises(MeetingAborted):
        await orch.run()

    assert meeting.status is MeetingStatus.FAILED
    # Nothing succeeded, so nothing was billed -- but the columns must exist
    # and be honest rather than absent.
    assert meeting.total_tokens_used == 0


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------


async def test_one_agent_failing_does_not_stop_the_meeting(db, org_and_user):
    """The COO blows up; the other three carry on and a brief still lands."""
    org, user = org_and_user
    meeting, _board, orch, brief = await _run(db, org, user, fail={"coo": "assessment"})

    assert meeting.status is MeetingStatus.COMPLETED
    assert set(orch.assessments) == {AgentId.CEO, AgentId.CFO, AgentId.STRATEGY_CONSULTANT}
    assert brief.recommended_option_id == "retention"
    assert "coo/assessment" in orch.budget.failures


async def test_a_failed_agent_is_marked_skipped_and_recorded(db, org_and_user):
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user, fail={"coo": "assessment"})

    participant = (
        await db.execute(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting.id,
                MeetingParticipant.agent_id == "coo",
            )
        )
    ).scalar_one()
    assert participant.status is ParticipantStatus.SKIPPED

    failures = (
        (
            await db.execute(
                select(MeetingEvent).where(
                    MeetingEvent.meeting_id == meeting.id,
                    MeetingEvent.event_type == EventType.AGENT_FAILED.value,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(failures) == 1
    assert failures[0].agent_id == "coo"
    assert "scripted failure" in failures[0].payload["error"]

    # The failure is in the usage log too, with no tokens attributed.
    record = (
        await db.execute(
            select(LLMUsageRecord).where(
                LLMUsageRecord.meeting_id == meeting.id,
                LLMUsageRecord.agent_id == "coo",
            )
        )
    ).scalar_one()
    assert record.request_count == 0
    assert record.error_message


async def test_the_meeting_is_not_retried_wholesale_after_one_failure(db, org_and_user):
    """Each surviving agent is asked exactly once, not re-run."""
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user, fail={"coo": "assessment"})

    assessment_agents = [c.agent_id for c in board.of_kind("assessment")]
    assert sorted(assessment_agents) == ["ceo", "cfo", "coo", "strategy_consultant"]
    assert len(assessment_agents) == len(set(assessment_agents))


async def test_too_many_failures_aborts_rather_than_faking_a_meeting(db, org_and_user):
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board(
        fail={"ceo": "assessment", "coo": "assessment", "cfo": "assessment"}
    )
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(db, meeting, company, model=model, user_id=user.id)

    with pytest.raises(MeetingAborted) as excinfo:
        await orch.run()

    assert excinfo.value.code == "insufficient_assessments"
    assert meeting.status is MeetingStatus.FAILED
    assert meeting.failure_reason
    # No synthesis was attempted on one opinion.
    assert board.of_kind("synthesis") == []


async def test_chair_failure_on_agenda_aborts_cleanly(db, org_and_user):
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board(fail={"chairperson": "agenda"})
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(db, meeting, company, model=model, user_id=user.id)

    with pytest.raises(MeetingAborted) as excinfo:
        await orch.run()

    assert excinfo.value.code == "agenda_failed"
    assert meeting.status is MeetingStatus.FAILED
    assert board.of_kind("assessment") == []


async def test_debate_planning_failure_degrades_to_synthesis(db, org_and_user):
    """A broken debate stage loses the argument, not the meeting."""
    org, user = org_and_user
    meeting, board, orch, brief = await _run(
        db, org, user, fail={"chairperson": "debate_plan"}
    )

    assert meeting.status is MeetingStatus.COMPLETED
    assert orch.objections == []
    assert brief.executive_summary
    assert board.of_kind("synthesis")


# --------------------------------------------------------------------------
# Limits and cancellation
# --------------------------------------------------------------------------


async def test_cancellation_stops_at_the_next_checkpoint(db, org_and_user):
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board()
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(db, meeting, company, model=model, user_id=user.id)

    # Cancel as soon as the agenda is done, the way the API endpoint would.
    original = orch._stage_agenda

    async def agenda_then_cancel():
        result = await original()
        meeting.status = MeetingStatus.CANCELLED
        await db.flush()
        return result

    orch._stage_agenda = agenda_then_cancel  # type: ignore[method-assign]

    with pytest.raises(MeetingCancelled):
        await orch.run()

    assert meeting.status is MeetingStatus.CANCELLED
    assert board.of_kind("assessment") == []
    events = await svc.list_events(db, meeting.id)
    assert EventType.MEETING_CANCELLED.value in [e.event_type for e in events]


async def test_model_request_ceiling_aborts_the_meeting(db, org_and_user):
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    _, model = scripted_board()
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=model,
        limits=MeetingLimits(max_model_requests=3, model_timeout_seconds=10),
        user_id=user.id,
    )

    with pytest.raises(MeetingAborted) as excinfo:
        await orch.run()
    assert excinfo.value.code == "usage_limit"
    assert "model request ceiling" in str(excinfo.value)
    assert meeting.status is MeetingStatus.FAILED


async def test_the_token_ceiling_is_enforceable_without_pricing(db, org_and_user):
    """Tokens are always known, so this ceiling works even when cost does not."""
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    _board, model = scripted_board()
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=model,
        limits=MeetingLimits(max_total_tokens=1, model_timeout_seconds=10),
        user_id=user.id,
    )

    with pytest.raises(MeetingAborted) as excinfo:
        await orch.run()
    assert excinfo.value.code == "usage_limit"
    assert "token ceiling" in str(excinfo.value)


async def test_cost_is_unknown_rather_than_zero_without_a_price(db, org_and_user):
    org, user = org_and_user
    _meeting, _board, orch, _ = await _run(db, org, user)
    # No MODEL_PRICES configured in the test environment.
    assert orch.budget.cost_known is False
    assert orch.budget.estimated_cost_usd == 0.0


async def test_debate_rounds_are_bounded(db, org_and_user):
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board()
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=model,
        limits=MeetingLimits(max_debate_rounds=3, max_challenges_per_round=2),
        user_id=user.id,
    )
    await orch.run()

    # Three rounds allowed, so at most three debate plans — never unbounded.
    assert len(board.of_kind("debate_plan")) <= 3
    assert meeting.debate_rounds_used <= 3


async def test_assessments_run_concurrently(db, org_and_user):
    """Stage 2 fans out. Measured by overlap, not asserted by faith.

    Each assessment call yields to the loop mid-flight; if the stage were
    serial, peak in-flight would be 1.
    """
    import asyncio

    from pydantic_ai.models.function import FunctionModel

    from tests.board_model import _schema_kind

    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, _model = scripted_board()

    in_flight = 0
    peak = 0

    async def tracking_call(messages, info):
        nonlocal in_flight, peak
        is_assessment = _schema_kind(info) == "assessment"
        if is_assessment:
            in_flight += 1
            peak = max(peak, in_flight)
        try:
            # Yield so sibling assessments can start before this one returns.
            await asyncio.sleep(0.01)
            return board(messages, info)
        finally:
            if is_assessment:
                in_flight -= 1

    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=FunctionModel(tracking_call, model_name="tracking"),
        user_id=user.id,
    )
    await orch.run()

    assert len(board.of_kind("assessment")) == 4
    assert peak > 1, f"assessments ran serially (peak in-flight {peak})"
    assert peak <= 4


async def test_assessment_concurrency_respects_the_limit(db, org_and_user):
    """The semaphore actually bounds the fan-out."""
    import asyncio

    from pydantic_ai.models.function import FunctionModel

    from tests.board_model import _schema_kind

    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, _model = scripted_board()

    in_flight = 0
    peak = 0

    async def tracking_call(messages, info):
        nonlocal in_flight, peak
        is_assessment = _schema_kind(info) == "assessment"
        if is_assessment:
            in_flight += 1
            peak = max(peak, in_flight)
        try:
            await asyncio.sleep(0.01)
            return board(messages, info)
        finally:
            if is_assessment:
                in_flight -= 1

    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=FunctionModel(tracking_call, model_name="tracking"),
        limits=MeetingLimits(max_assessment_concurrency=2),
        user_id=user.id,
    )
    await orch.run()

    assert peak <= 2, f"semaphore did not bound concurrency (peak {peak})"


async def test_company_context_reaches_every_executive(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user)

    for call in board.of_kind("assessment"):
        assert "Northstar Labs" in call.instructions
        assert "2,000,000" in call.instructions


async def test_orchestrator_uses_company_context_passed_in(db, org_and_user):
    """An empty profile must not silently become invented facts."""
    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)
    board, model = scripted_board()
    orch = MeetingOrchestrator(
        db, meeting, CompanyContext(), model=model, user_id=user.id
    )
    await orch.run()

    for call in board.of_kind("assessment"):
        assert "No company profile has been entered" in call.instructions


# ---------------------------------------------------------------------------
# What a failure says to the user
# ---------------------------------------------------------------------------


class _ModelHTTPError(Exception):
    """Stands in for a provider error, which carries the response body."""


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (
            _ModelHTTPError("status_code: 429, body: {'message': 'Rate limit reached'}"),
            "rate-limiting",
        ),
        (
            _ModelHTTPError("status_code: 401, body: {'code': 'invalid_api_key'}"),
            "credentials",
        ),
        (TimeoutError(), "within the time limit"),
        (_ModelHTTPError("Connection refused"), "could not be reached"),
    ],
)
def test_provider_failures_are_explained_not_dumped(exc, expected):
    summary = summarize_agent_error(exc)
    assert expected in summary
    # The exception type stays, so a log line can still be matched to it.
    assert type(exc).__name__ in summary


def test_an_unrecognised_failure_keeps_its_first_line_and_is_bounded():
    """A raw provider blob would otherwise reach the exported brief verbatim."""
    exc = ValueError("Could not parse output\n" + "detail " * 500)
    summary = summarize_agent_error(exc)
    assert summary == "ValueError: Could not parse output"
    assert len(summary) <= 200


def test_a_failure_with_no_message_still_names_itself():
    assert summarize_agent_error(RuntimeError()) == "RuntimeError"


async def test_a_chair_failure_reaches_the_user_as_a_sentence(db, org_and_user):
    """failure_reason is shown in the boardroom and exported; keep it short."""
    from pydantic_ai.models.function import FunctionModel

    org, user = org_and_user
    meeting = await _make_meeting(db, org, user)

    async def always_fails(messages, info):
        raise _ModelHTTPError("status_code: 429, body: {'message': 'Rate limit reached'}")

    orch = MeetingOrchestrator(
        db,
        meeting,
        await load_company_context(db, org.id),
        model=FunctionModel(always_fails, model_name="failing"),
        user_id=user.id,
    )
    with pytest.raises(MeetingAborted):
        await orch.run()

    assert meeting.status is MeetingStatus.FAILED
    assert "rate-limiting" in (meeting.failure_reason or "")
    assert len(meeting.failure_reason or "") < 400
