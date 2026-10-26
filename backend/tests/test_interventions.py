"""Directing a live meeting: interventions, pause/resume, action items, export."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents.factory import reset_agent_cache
from app.agents.registry import AgentId
from app.models.enums import ActionItemStatus, MeetingStatus
from app.models.intervention import (
    InterventionKind,
    InterventionStatus,
    MeetingIntervention,
)
from app.orchestration.events import EventType
from app.orchestration.interventions import build_prompt
from app.orchestration.meeting import MeetingLimits, MeetingOrchestrator
from app.services import export
from app.services import meeting as svc
from app.services.consultation import load_company_context
from tests.board_model import scripted_board

QUESTION = "Should we prioritise retention or launch a new product?"


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


async def _running_meeting(db, org, user):
    """A meeting in RUNNING state with participants, not yet executed."""
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        participant_agent_ids=["ceo", "coo", "cfo"],
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()
    return meeting


async def _completed(db, org, user, **board_kwargs):
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    board, model = scripted_board(**board_kwargs)
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    brief = await orch.run()
    decision = await svc.persist_decision(db, meeting, brief, orch)
    return meeting, board, orch, decision


# --------------------------------------------------------------------------
# Queuing
# --------------------------------------------------------------------------


async def test_an_intervention_is_a_persisted_row_not_a_ui_state(db, org_and_user):
    """The spec forbids buttons that only change frontend text."""
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)

    intervention = await svc.queue_intervention(
        db,
        meeting=meeting,
        user_id=user.id,
        agent_id="coo",
        kind=InterventionKind.ASK,
        prompt="Can we actually execute this in six months?",
    )

    stored = (
        await db.execute(
            select(MeetingIntervention).where(MeetingIntervention.id == intervention.id)
        )
    ).scalar_one()
    assert stored.status is InterventionStatus.QUEUED
    assert stored.agent_id == "coo"
    assert stored.requested_by_user_id == user.id


async def test_cannot_address_an_executive_who_is_not_in_the_room(db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)
    with pytest.raises(svc.MeetingError) as exc:
        await svc.queue_intervention(
            db,
            meeting=meeting,
            user_id=user.id,
            agent_id="general_counsel",
            kind=InterventionKind.ASK,
            prompt="What is the exposure?",
        )
    assert exc.value.code == "agent_not_present"


async def test_cannot_address_an_invented_executive(db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)
    with pytest.raises(svc.MeetingError) as exc:
        await svc.queue_intervention(
            db,
            meeting=meeting,
            user_id=user.id,
            agent_id="head_of_vibes",
            kind=InterventionKind.ASK,
            prompt="hi",
        )
    assert exc.value.code == "unknown_agent"


async def test_cannot_intervene_in_a_meeting_that_is_not_live(db, org_and_user):
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )  # still DRAFT
    with pytest.raises(svc.MeetingError) as exc:
        await svc.queue_intervention(
            db,
            meeting=meeting,
            user_id=user.id,
            agent_id="ceo",
            kind=InterventionKind.ASK,
            prompt="hi",
        )
    assert exc.value.code == "meeting_not_live"


# --------------------------------------------------------------------------
# Execution at a safe point
# --------------------------------------------------------------------------


async def test_a_queued_intervention_is_answered_during_the_meeting(db, org_and_user):
    """Phase 8 acceptance: the founder directs the meeting, and it shows."""
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        participant_agent_ids=["ceo", "coo", "cfo"],
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()

    await svc.queue_intervention(
        db,
        meeting=meeting,
        user_id=user.id,
        agent_id="coo",
        kind=InterventionKind.ASK,
        prompt="Can we execute this with the team we have?",
    )
    meeting.status = MeetingStatus.DRAFT  # run() sets it back to RUNNING
    await db.flush()

    board, model = scripted_board(participants=("ceo", "coo", "cfo"))
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    await orch.run()

    stored = (await svc.list_interventions(db, meeting.id))[0]
    assert stored.status is InterventionStatus.ANSWERED
    assert stored.response
    assert stored.answered_at is not None
    assert stored.answered_at_stage

    # The COO's consultation agent answered, with the founder's words in it.
    intervention_calls = [c for c in board.calls if c.kind == "consultation"]
    assert intervention_calls
    assert "Can we execute this with the team we have?" in intervention_calls[0].prompt
    assert intervention_calls[0].agent_id == "coo"


async def test_the_exchange_is_preserved_in_the_meeting_history(db, org_and_user):
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        participant_agent_ids=["ceo", "cfo"],
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()
    await svc.queue_intervention(
        db,
        meeting=meeting,
        user_id=user.id,
        agent_id="cfo",
        kind=InterventionKind.CHALLENGE,
        prompt="Your runway maths assumes flat burn. Defend that.",
    )
    meeting.status = MeetingStatus.DRAFT
    await db.flush()

    _, model = scripted_board(participants=("ceo", "cfo"))
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    await orch.run()

    events = await svc.list_events(db, meeting.id)
    types = [e.event_type for e in events]
    assert EventType.USER_INTERVENTION_REQUESTED.value in types
    assert EventType.INTERVENTION_ANSWERED.value in types

    requested = next(
        e for e in events if e.event_type == EventType.USER_INTERVENTION_REQUESTED.value
    )
    assert requested.agent_id == "cfo"
    assert "flat burn" in requested.payload["prompt"]


async def test_interventions_run_between_stages_never_inside_one(db, org_and_user):
    """A founder interrupting must not corrupt a round in flight."""
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        participant_agent_ids=["ceo", "coo", "cfo"],
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()
    await svc.queue_intervention(
        db,
        meeting=meeting,
        user_id=user.id,
        agent_id="ceo",
        kind=InterventionKind.ASK,
        prompt="Why this and not the alternative?",
    )
    meeting.status = MeetingStatus.DRAFT
    await db.flush()

    board, model = scripted_board(participants=("ceo", "coo", "cfo"))
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    await orch.run()

    kinds = board.kinds()
    first_assessment = kinds.index("assessment")
    last_assessment = max(i for i, k in enumerate(kinds) if k == "assessment")
    consultation_at = kinds.index("consultation")
    # The intervention did not land in the middle of the assessment wave.
    assert not (first_assessment < consultation_at < last_assessment)


async def test_several_interventions_are_answered_in_order(db, org_and_user):
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        participant_agent_ids=["ceo", "coo", "cfo"],
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()
    for agent, text in (("ceo", "First question"), ("cfo", "Second question")):
        await svc.queue_intervention(
            db,
            meeting=meeting,
            user_id=user.id,
            agent_id=agent,
            kind=InterventionKind.ASK,
            prompt=text,
        )
    meeting.status = MeetingStatus.DRAFT
    await db.flush()

    board, model = scripted_board(participants=("ceo", "coo", "cfo"))
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    await orch.run()

    answered = await svc.list_interventions(db, meeting.id)
    assert [i.status for i in answered] == [InterventionStatus.ANSWERED] * 2
    prompts = [c.prompt for c in board.calls if c.kind == "consultation"]
    assert "First question" in prompts[0]
    assert "Second question" in prompts[1]


async def test_unanswered_interventions_are_abandoned_not_left_pending(
    db, org_and_user
):
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db,
        organization_id=org.id,
        user_id=user.id,
        question=QUESTION,
        participant_agent_ids=["ceo", "cfo"],
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()
    await svc.queue_intervention(
        db,
        meeting=meeting,
        user_id=user.id,
        agent_id="ceo",
        kind=InterventionKind.ASK,
        prompt="Too late",
    )
    meeting.status = MeetingStatus.DRAFT
    await db.flush()

    # The Chair fails at the agenda, so the meeting never reaches a drain.
    _, model = scripted_board(fail={"chairperson": "agenda"})
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(db, meeting, company, model=model, user_id=user.id)
    from app.orchestration.meeting import MeetingAborted

    with pytest.raises(MeetingAborted):
        await orch.run()

    stored = (await svc.list_interventions(db, meeting.id))[0]
    assert stored.status is InterventionStatus.ABANDONED
    assert "ended before" in stored.error_message


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------


def test_each_intervention_kind_frames_the_task_differently():
    prompts = {
        kind: build_prompt(
            kind=kind,
            agent_id=AgentId.CFO,
            founder_text="Explain yourself.",
            about_agent_id=None,
            meeting_question=QUESTION,
            own_position="Improve retention.",
            target_position=None,
            stage="debate",
        )
        for kind in InterventionKind
    }
    assert len({p for p in prompts.values()}) == len(InterventionKind)
    assert "challenging your position" in prompts[InterventionKind.CHALLENGE]
    assert "what your position actually rests on" in prompts[
        InterventionKind.REQUEST_EVIDENCE
    ]


def test_a_critique_prompt_carries_the_colleagues_actual_conclusion():
    prompt = build_prompt(
        kind=InterventionKind.CRITIQUE_COLLEAGUE,
        agent_id=AgentId.CFO,
        founder_text="Is the CEO right?",
        about_agent_id=AgentId.CEO,
        meeting_question=QUESTION,
        own_position="Improve retention.",
        target_position="Launch the new product.",
        stage="debate",
    )
    assert "Marcus Lindqvist" in prompt
    assert "Launch the new product." in prompt
    assert "Agreeing is a real answer" in prompt


def test_the_prompt_quotes_the_founder_verbatim():
    prompt = build_prompt(
        kind=InterventionKind.ASK,
        agent_id=AgentId.COO,
        founder_text="  Can we do this in six months?  ",
        about_agent_id=None,
        meeting_question=QUESTION,
        own_position=None,
        target_position=None,
        stage="assessments",
    )
    assert '"Can we do this in six months?"' in prompt


# --------------------------------------------------------------------------
# Pause and resume
# --------------------------------------------------------------------------


async def test_pause_and_resume_move_the_status(db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)

    await svc.pause_meeting(db, meeting)
    assert meeting.status is MeetingStatus.PAUSED

    await svc.resume_meeting(db, meeting)
    assert meeting.status is MeetingStatus.RUNNING


async def test_only_a_running_meeting_can_be_paused(db, org_and_user):
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    with pytest.raises(svc.MeetingError) as exc:
        await svc.pause_meeting(db, meeting)
    assert exc.value.code == "not_pausable"


async def test_only_a_paused_meeting_can_be_resumed(db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)
    with pytest.raises(svc.MeetingError) as exc:
        await svc.resume_meeting(db, meeting)
    assert exc.value.code == "not_resumable"


async def test_a_paused_meeting_holds_at_the_checkpoint_then_continues(
    db, org_and_user
):
    """Pause stops the next step; it does not abort one in flight."""
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    board, model = scripted_board(participants=("ceo", "cfo"))
    company = await load_company_context(db, org.id)
    orch = MeetingOrchestrator(
        db, meeting, company, model=model, user_id=user.id,
        limits=MeetingLimits(
            max_debate_rounds=1, model_timeout_seconds=10, pause_poll_seconds=0.01
        ),
    )

    # Pause as soon as the agenda is done, and resume on the first poll.
    original = orch._stage_agenda
    resumed = {"done": False}

    async def agenda_then_pause():
        result = await original()
        meeting.status = MeetingStatus.PAUSED
        await db.flush()
        return result

    original_refresh = orch.db.refresh
    seen_paused = {"count": 0}

    async def refresh_and_resume(obj, attrs=None):
        await original_refresh(obj, attrs)
        if obj is not meeting or meeting.status is not MeetingStatus.PAUSED:
            return
        # Let the first refresh see PAUSED so _await_resume emits the event
        # and enters its wait loop; resume on the loop's own poll.
        seen_paused["count"] += 1
        if seen_paused["count"] >= 2 and not resumed["done"]:
            resumed["done"] = True
            meeting.status = MeetingStatus.RUNNING
            await db.flush()

    orch._stage_agenda = agenda_then_pause  # type: ignore[method-assign]
    orch.db.refresh = refresh_and_resume  # type: ignore[method-assign]

    await orch.run()
    orch.db.refresh = original_refresh  # type: ignore[method-assign]

    assert meeting.status is MeetingStatus.COMPLETED
    events = [e.event_type for e in await svc.list_events(db, meeting.id)]
    assert EventType.MEETING_PAUSED.value in events
    assert EventType.MEETING_RESUMED.value in events
    assert board.of_kind("assessment")  # it carried on afterwards


# --------------------------------------------------------------------------
# Action items
# --------------------------------------------------------------------------


async def test_action_items_can_be_assigned_and_closed(db, org_and_user):
    org, user = org_and_user
    _, _, _, _decision = await _completed(db, org, user)

    items = await svc.list_action_items(db, org.id)
    assert items
    item = items[0]
    assert item.status is ActionItemStatus.OPEN

    updated = await svc.update_action_item(
        db,
        item,
        status=ActionItemStatus.IN_PROGRESS,
        suggested_owner="Priya",
        outcome_notes="Started on the churn cohort analysis.",
    )
    assert updated.status is ActionItemStatus.IN_PROGRESS
    assert updated.suggested_owner == "Priya"
    assert updated.outcome_notes.startswith("Started")

    open_only = await svc.list_action_items(db, org.id, open_only=True)
    assert item.id in {i.id for i in open_only}

    await svc.update_action_item(db, item, status=ActionItemStatus.DONE)
    open_only = await svc.list_action_items(db, org.id, open_only=True)
    assert item.id not in {i.id for i in open_only}


async def test_action_items_are_scoped_to_the_organization(db, org_and_user):
    org, user = org_and_user
    _, _, _, _decision = await _completed(db, org, user)
    item = (await svc.list_action_items(db, org.id))[0]

    assert await svc.get_action_item(db, item.id, org.id) is not None
    assert await svc.get_action_item(db, item.id, uuid.uuid4()) is None


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


async def test_markdown_export_contains_the_whole_brief(db, org_and_user):
    org, user = org_and_user
    _, _, _, decision = await _completed(db, org, user)

    md = export.to_markdown(decision, question=QUESTION)
    assert md.startswith("# ")
    for heading in (
        "## Executive summary",
        "## Problem",
        "## Options considered",
        "## Dissent",
        "## Still unresolved",
        "## Action plan",
        "## Where each executive stood",
    ):
        assert heading in md

    # Dissent is attributed to a named executive, not an id.
    assert "Marcus Lindqvist" in md
    assert "recommended" in md
    assert "not legal advice" in md


async def test_markdown_export_omits_empty_sections(db, org_and_user):
    org, user = org_and_user
    _, _, _, decision = await _completed(db, org, user)
    decision.legal_considerations = None
    decision.dissenting_opinions = []
    await db.flush()

    md = export.to_markdown(decision)
    assert "## Legal considerations" not in md
    assert "## Dissent" not in md


async def test_pdf_export_produces_a_real_pdf(db, org_and_user):
    org, user = org_and_user
    _, _, _, decision = await _completed(db, org, user)

    data = export.to_pdf(decision, question=QUESTION)
    assert data.startswith(b"%PDF-")
    assert len(data) > 1000


async def test_pdf_export_keeps_the_punctuation_the_board_writes(db, org_and_user):
    """Em dashes and curly quotes used to come out as question marks.

    The core fonts are declared WinAnsiEncoding, so cp1252 is their real
    repertoire; encoding to latin-1 first was throwing away characters the
    PDF could render.
    """
    import io

    from pypdf import PdfReader

    org, user = org_and_user
    _, _, _, decision = await _completed(db, org, user)
    decision.executive_summary = (
        "Runway falls 12 → 9 months — a 25% cut. "
        "The CFO’s “segmented” plan costs €400k… café maths."
    )
    await db.flush()

    data = export.to_pdf(decision)
    assert data.startswith(b"%PDF-")

    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)
    for survivor in ("—", "’", "“", "…", "€", "é"):
        assert survivor in text, f"{survivor!r} was dropped from the PDF"
    # An arrow is outside cp1252, so it is transliterated rather than lost.
    assert "12 -> 9 months" in text


def test_pdf_text_falls_back_only_where_cp1252_genuinely_cannot_reach():
    """Accent-folding is per character, so encodable accents are untouched."""
    assert export._pdf_safe("café naïve") == "café naïve"
    assert export._pdf_safe("āş") == "as"
    assert export._pdf_safe("ARR ≥ 2M") == "ARR >= 2M"
    # Nothing Latin to fall back to; "?" is the honest answer.
    assert export._pdf_safe("日本語") == "???"


def test_export_filename_is_slugged():
    class Fake:
        title = "Should we prioritise retention?!"

    assert export.filename_for(Fake(), "md") == "should-we-prioritise-retention.md"


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


async def test_intervention_endpoint_queues_and_returns_202(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)

    res = await client.post(
        f"/api/meetings/{meeting.id}/interventions",
        json={"agent_id": "coo", "kind": "ask", "prompt": "Can we execute this?"},
    )
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "queued"

    listing = await client.get(f"/api/meetings/{meeting.id}/interventions")
    assert len(listing.json()) == 1


async def test_intervention_endpoint_rejects_a_finished_meeting(
    client, db, org_and_user
):
    org, user = org_and_user
    meeting, _, _, _ = await _completed(db, org, user)
    res = await client.post(
        f"/api/meetings/{meeting.id}/interventions",
        json={"agent_id": "ceo", "kind": "ask", "prompt": "hello"},
    )
    assert res.status_code == 409


async def test_pause_and_resume_endpoints(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)

    paused = await client.post(f"/api/meetings/{meeting.id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = await client.post(f"/api/meetings/{meeting.id}/resume")
    assert resumed.json()["status"] == "running"

    # Resuming twice is a conflict, not a silent no-op.
    assert (await client.post(f"/api/meetings/{meeting.id}/resume")).status_code == 409


async def test_export_endpoints_return_downloadable_files(client, db, org_and_user):
    org, user = org_and_user
    _, _, _, decision = await _completed(db, org, user)

    md = await client.get(f"/api/decisions/{decision.id}/export?format=markdown")
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert "attachment" in md.headers["content-disposition"]
    assert md.text.startswith("# ")

    pdf = await client.get(f"/api/decisions/{decision.id}/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")


async def test_export_rejects_an_unknown_format(client, db, org_and_user):
    org, user = org_and_user
    _, _, _, decision = await _completed(db, org, user)
    res = await client.get(f"/api/decisions/{decision.id}/export?format=docx")
    assert res.status_code == 422


async def test_action_item_endpoints(client, db, org_and_user):
    org, user = org_and_user
    await _completed(db, org, user)

    listing = await client.get("/api/action-items")
    assert listing.status_code == 200
    items = listing.json()
    assert items

    updated = await client.patch(
        f"/api/action-items/{items[0]['id']}",
        json={"status": "done", "outcome_notes": "Shipped."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"


async def test_meeting_detail_includes_interventions(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)
    await svc.queue_intervention(
        db,
        meeting=meeting,
        user_id=user.id,
        agent_id="cfo",
        kind=InterventionKind.REQUEST_EVIDENCE,
        prompt="What is that based on?",
    )

    body = (await client.get(f"/api/meetings/{meeting.id}")).json()
    assert len(body["interventions"]) == 1
    assert body["interventions"][0]["kind"] == "request_evidence"


async def test_intervention_endpoints_require_authentication(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _running_meeting(db, org, user)
    res = await client.post(
        f"/api/meetings/{meeting.id}/interventions",
        json={"agent_id": "ceo", "kind": "ask", "prompt": "hi"},
        headers={"Authorization": ""},
    )
    assert res.status_code == 401
