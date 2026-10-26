"""The five meeting modes: who attends, what they are asked, what comes out."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents.factory import reset_agent_cache
from app.agents.registry import AgentId
from app.models.enums import MeetingMode, MeetingStatus
from app.models.meeting import AgentAssessment, MeetingParticipant
from app.orchestration.meeting import MeetingAborted, MeetingLimits, MeetingOrchestrator
from app.orchestration.modes import ALL_SPECIALISTS, MODE_PROFILES, profile_for
from app.services import meeting as svc
from app.services.consultation import load_company_context
from tests.board_model import scripted_board

QUESTION = (
    "Should we prioritise improving retention, international expansion, "
    "or launching a new product?"
)

ALL_IDS = tuple(a.value for a in ALL_SPECIALISTS)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


async def _run(db, org, user, mode, *, subject_id=None, participants=ALL_IDS, **kw):
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        mode=mode,
        subject_decision_id=subject_id,
    )
    board, model = scripted_board(participants=participants, **kw)
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(
            max_debate_rounds=1,
            model_timeout_seconds=10,
            max_model_requests=200,
            max_challenges_per_round=4,
        ),
    )
    brief = await orch.run()
    return meeting, board, orch, brief


async def _completed_executive_meeting(db, org, user):
    """A finished meeting, so Devil's Advocate has something to attack."""
    meeting, _, orch, brief = await _run(
        db, org, user, MeetingMode.EXECUTIVE_MEETING, participants=("ceo", "coo", "cfo")
    )
    return await svc.persist_decision(db, meeting, brief, orch)


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------


def test_every_mode_has_a_profile():
    assert set(MODE_PROFILES) == set(MeetingMode)


def test_full_board_seats_every_specialist():
    profile = profile_for(MeetingMode.FULL_BOARD)
    assert set(profile.candidates) == set(ALL_SPECIALISTS)
    assert len(profile.candidates) == 8
    assert profile.min_participants == 8


def test_only_devils_advocate_requires_a_subject():
    requiring = [m for m, p in MODE_PROFILES.items() if p.requires_subject]
    assert requiring == [MeetingMode.DEVILS_ADVOCATE]


def test_only_strategy_workshop_runs_the_roadmap_stage():
    with_roadmap = [m for m, p in MODE_PROFILES.items() if p.roadmap_stage]
    assert with_roadmap == [MeetingMode.STRATEGY_WORKSHOP]


def test_modes_have_distinct_assessment_framing():
    tasks = {m: p.assessment_task for m, p in MODE_PROFILES.items()}
    assert len(set(tasks.values())) == len(tasks)
    assert "how this recommendation fails" in tasks[MeetingMode.DEVILS_ADVOCATE]
    assert "Propose alternatives" in tasks[MeetingMode.STRATEGY_WORKSHOP]


def test_bigger_rooms_get_bigger_budgets():
    assert (
        profile_for(MeetingMode.FULL_BOARD).model_request_budget
        > profile_for(MeetingMode.EXECUTIVE_MEETING).model_request_budget
        > profile_for(MeetingMode.QUICK_CONSULTATION).model_request_budget
    )


# --------------------------------------------------------------------------
# Full Board
# --------------------------------------------------------------------------


async def test_full_board_runs_all_nine_agents(db, org_and_user):
    """Phase 6 acceptance: every executive participates."""
    org, user = org_and_user
    meeting, board, orch, _ = await _run(db, org, user, MeetingMode.FULL_BOARD)

    assert meeting.status is MeetingStatus.COMPLETED
    assert set(orch.assessments) == set(ALL_SPECIALISTS)
    assert len(orch.assessments) == 8

    # Plus the Chair, who runs agenda, debate planning, and synthesis.
    chair_stages = {c.kind for c in board.calls if c.agent_id == "chairperson"}
    assert chair_stages == {"agenda", "debate_plan", "synthesis"}


async def test_full_board_seats_everyone_even_if_the_chair_picks_fewer(db, org_and_user):
    """A full board is not the Chair's call; the mode decides."""
    org, user = org_and_user
    # The scripted Chair only nominates three.
    _, _, orch, _ = await _run(
        db, org, user, MeetingMode.FULL_BOARD, participants=("ceo", "cfo", "coo")
    )
    assert len(orch.assessments) == 8


async def test_full_board_persists_nine_participants(db, org_and_user):
    org, user = org_and_user
    meeting, _, _, _ = await _run(db, org, user, MeetingMode.FULL_BOARD)

    rows = (
        (
            await db.execute(
                select(MeetingParticipant).where(
                    MeetingParticipant.meeting_id == meeting.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 9
    assert "chairperson" in {r.agent_id for r in rows}


async def test_every_executive_is_told_it_is_a_full_board(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(db, org, user, MeetingMode.FULL_BOARD)
    for call in board.of_kind("assessment"):
        assert "Full Board Meeting" in call.prompt
        assert "stay tightly inside your own function" in call.prompt


# --------------------------------------------------------------------------
# Executive Meeting still selects relevantly
# --------------------------------------------------------------------------


async def test_executive_meeting_can_now_draw_on_the_whole_roster(db, org_and_user):
    """Relevant selection: the Chair picks from all eight, not a fixed four."""
    org, user = org_and_user
    _, _, orch, _ = await _run(
        db,
        org,
        user,
        MeetingMode.EXECUTIVE_MEETING,
        participants=("customer_advocate", "competitive_intel", "general_counsel"),
    )
    assert set(orch.assessments) == {
        AgentId.CUSTOMER_ADVOCATE,
        AgentId.COMPETITIVE_INTEL,
        AgentId.GENERAL_COUNSEL,
    }


async def test_an_under_seated_room_is_topped_up_to_the_mode_minimum(db, org_and_user):
    """min_participants is a promise, not a suggestion."""
    org, user = org_and_user
    decision = await _completed_executive_meeting(db, org, user)
    # The scripted Chair nominates only two attackers.
    _, _, orch, _ = await _run(
        db,
        org,
        user,
        MeetingMode.DEVILS_ADVOCATE,
        subject_id=decision.id,
        participants=("cfo", "coo"),
    )
    assert len(orch.assessments) >= profile_for(MeetingMode.DEVILS_ADVOCATE).min_participants


async def test_executive_meeting_trims_an_oversized_room(db, org_and_user):
    org, user = org_and_user
    _, _, orch, _ = await _run(db, org, user, MeetingMode.EXECUTIVE_MEETING)
    # The scripted Chair nominates all eight; the mode caps at six.
    assert len(orch.assessments) == profile_for(MeetingMode.EXECUTIVE_MEETING).max_participants


# --------------------------------------------------------------------------
# Devil's Advocate
# --------------------------------------------------------------------------


async def test_devils_advocate_needs_a_decision_to_attack(db, org_and_user):
    org, user = org_and_user
    with pytest.raises(svc.MeetingError) as excinfo:
        await svc.create_meeting(
            db,
            organization_id=org.id,
            user_id=user.id,
            question=QUESTION,
            mode=MeetingMode.DEVILS_ADVOCATE,
        )
    assert excinfo.value.code == "subject_required"


async def test_devils_advocate_rejects_a_decision_from_another_org(db, org_and_user):
    import uuid

    org, user = org_and_user
    with pytest.raises(svc.MeetingError) as excinfo:
        await svc.create_meeting(
            db,
            organization_id=org.id,
            user_id=user.id,
            question=QUESTION,
            mode=MeetingMode.DEVILS_ADVOCATE,
            subject_decision_id=uuid.uuid4(),
        )
    assert excinfo.value.code == "subject_not_found"


async def test_devils_advocate_puts_the_recommendation_in_front_of_everyone(
    db, org_and_user
):
    org, user = org_and_user
    decision = await _completed_executive_meeting(db, org, user)

    _, board, _, _ = await _run(
        db,
        org,
        user,
        MeetingMode.DEVILS_ADVOCATE,
        subject_id=decision.id,
        participants=("cfo", "coo", "customer_advocate"),
    )

    for call in board.of_kind("assessment"):
        assert "THE RECOMMENDATION UNDER TEST" in call.prompt
        assert decision.executive_summary[:40] in call.prompt
        assert "find how this recommendation fails" in call.prompt

    # The Chair is given it too, at both ends of the meeting.
    assert "THE RECOMMENDATION UNDER TEST" in board.of_kind("agenda")[0].prompt
    assert "THE RECOMMENDATION UNDER TEST" in board.of_kind("synthesis")[0].prompt


async def test_devils_advocate_carries_the_prior_dissent_forward(db, org_and_user):
    """So nobody re-raises a point the board already heard."""
    org, user = org_and_user
    decision = await _completed_executive_meeting(db, org, user)
    assert decision.dissenting_opinions  # the scripted board records CEO dissent

    _, board, _, _ = await _run(
        db,
        org,
        user,
        MeetingMode.DEVILS_ADVOCATE,
        subject_id=decision.id,
        participants=("cfo", "coo", "customer_advocate"),
    )
    prompt = board.of_kind("assessment")[0].prompt
    assert "Dissent already on record" in prompt
    assert "ceo" in prompt


async def test_devils_advocate_forbids_manufactured_objections(db, org_and_user):
    org, user = org_and_user
    decision = await _completed_executive_meeting(db, org, user)
    _, board, _, _ = await _run(
        db,
        org,
        user,
        MeetingMode.DEVILS_ADVOCATE,
        subject_id=decision.id,
        participants=("cfo", "coo", "customer_advocate"),
    )
    prompt = board.of_kind("assessment")[0].prompt
    assert "cannot find a material weakness" in prompt
    assert "Manufacturing an objection" in prompt


async def test_devils_advocate_fails_cleanly_if_the_subject_vanishes(db, org_and_user):
    org, user = org_and_user
    decision = await _completed_executive_meeting(db, org, user)
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        mode=MeetingMode.DEVILS_ADVOCATE,
        subject_decision_id=decision.id,
    )
    meeting.subject_decision_id = None  # deleted between creation and start
    await db.flush()

    _, model = scripted_board()
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(db, meeting, company, model=model, user_id=user.id)

    with pytest.raises(MeetingAborted) as excinfo:
        await orch.run()
    assert excinfo.value.code == "subject_required"


# --------------------------------------------------------------------------
# Strategy Workshop
# --------------------------------------------------------------------------


async def test_strategy_workshop_asks_for_alternatives(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(
        db, org, user, MeetingMode.STRATEGY_WORKSHOP, participants=("ceo", "coo", "cfo")
    )
    # The roadmap call reuses the assessment schema, so exclude it: it is a
    # planning task, not an alternatives task.
    alternatives_calls = [
        c for c in board.of_kind("assessment") if "30/60/90" not in c.prompt
    ]
    assert alternatives_calls
    for call in alternatives_calls:
        assert "Propose alternatives" in call.prompt
        assert "nobody has mentioned" in call.prompt


async def test_strategy_workshop_runs_the_coo_roadmap_stage(db, org_and_user):
    org, user = org_and_user
    meeting, board, _orch, _ = await _run(
        db, org, user, MeetingMode.STRATEGY_WORKSHOP, participants=("ceo", "coo", "cfo")
    )

    # One extra assessment-shaped call after synthesis, from the COO.
    kinds = board.kinds()
    assert kinds[-1] == "assessment"
    assert kinds[-2] == "synthesis"

    roadmap = (
        (
            await db.execute(
                select(AgentAssessment).where(
                    AgentAssessment.meeting_id == meeting.id,
                    AgentAssessment.round_number == 99,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(roadmap) == 1
    assert roadmap[0].agent_id == "coo"


async def test_the_roadmap_prompt_forbids_invented_dates(db, org_and_user):
    org, user = org_and_user
    _, board, _, _ = await _run(
        db, org, user, MeetingMode.STRATEGY_WORKSHOP, participants=("ceo", "coo", "cfo")
    )
    roadmap_prompt = board.calls[-1].prompt
    assert "30/60/90" in roadmap_prompt
    assert "do not invent one" in roadmap_prompt


async def test_workshop_without_a_coo_keeps_the_chairs_plan(db, org_and_user):
    """A missing COO diminishes the workshop; it does not break it.

    The COO has to be absent from the *pool*, not merely unnominated: an
    under-seated room is topped up from the pool, so leaving the COO out of
    the Chair's picks alone would just put it back.
    """
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        mode=MeetingMode.STRATEGY_WORKSHOP,
    )
    board, model = scripted_board(participants=("ceo", "cfo", "cgo"))
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db,
        meeting,
        company,
        model=model,
        user_id=user.id,
        candidates=(AgentId.CEO, AgentId.CFO, AgentId.CGO),
        limits=MeetingLimits(
            max_debate_rounds=1, model_timeout_seconds=10, max_model_requests=200
        ),
    )
    brief = await orch.run()

    assert meeting.status is MeetingStatus.COMPLETED
    assert AgentId.COO not in orch.assessments
    assert board.kinds()[-1] == "synthesis"  # no roadmap stage ran
    assert brief.action_plan is not None


# --------------------------------------------------------------------------
# Quick Consultation
# --------------------------------------------------------------------------


async def test_quick_consultation_seats_one_executive(db, org_and_user):
    org, user = org_and_user
    _, _, orch, _ = await _run(
        db, org, user, MeetingMode.QUICK_CONSULTATION, participants=("cfo",)
    )
    assert len(orch.assessments) == 1
    assert AgentId.CFO in orch.assessments


async def test_quick_consultation_stays_cheap(db, org_and_user):
    org, user = org_and_user
    _, board, orch, _ = await _run(
        db, org, user, MeetingMode.QUICK_CONSULTATION, participants=("cfo",)
    )
    # agenda + 1 assessment + debate plan + synthesis, and no debate to run.
    assert orch.budget.model_requests <= 5
    assert board.of_kind("objection") == []
