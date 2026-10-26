"""Meeting and decision endpoints.

The full workflow is driven through the service with a scripted model rather
than through the background task the API spawns, so these assertions are about
retrieval, scoping, and the human-decision surface — not orchestration timing.
"""

from __future__ import annotations

import uuid

import pytest

from app.agents.factory import reset_agent_cache
from app.core.security import create_access_token, hash_password
from app.models.enums import DecisionStatus, MeetingStatus, OrgRole
from app.models.identity import Organization, OrganizationMember, User
from app.orchestration.meeting import MeetingLimits
from app.services import meeting as svc
from tests.board_model import scripted_board

QUESTION = (
    "Should we prioritise improving retention, international expansion, "
    "or launching a new product?"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


async def _completed_meeting(db, org, user):
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    _, model = scripted_board()
    await svc.run_meeting(
        db,
        meeting,
        user_id=user.id,
        model=model,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    return meeting


async def test_create_meeting_without_starting_it(client):
    res = await client.post(
        "/api/meetings", json={"question": QUESTION, "start_immediately": False}
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "draft"
    assert body["question"] == QUESTION
    assert body["title"]
    assert body["assessments"] == []


async def test_question_must_be_substantive(client):
    res = await client.post("/api/meetings", json={"question": "hi", "start_immediately": False})
    assert res.status_code == 422


async def test_completed_meeting_exposes_every_contribution(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    res = await client.get(f"/api/meetings/{meeting.id}")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["status"] == "completed"
    assert body["stage"] == "persisted"
    assert len(body["participants"]) == 5
    assert len(body["assessments"]) == 4
    assert len(body["objections"]) == 2
    assert len(body["revisions"]) == 1
    assert body["agenda"]["reframed_question"]
    assert body["model_requests_used"] == 10


async def test_assessments_are_distinguishable_from_synthesis(client, db, org_and_user):
    """Independently produced positions and the Chair's brief are separate
    fields, never merged into one narrative."""
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)
    body = (await client.get(f"/api/meetings/{meeting.id}")).json()

    agent_ids = {a["agent_id"] for a in body["assessments"]}
    assert agent_ids == {"ceo", "coo", "cfo", "strategy_consultant"}
    assert "chairperson" not in agent_ids

    decision = body["decision"]
    assert decision is not None
    assert decision["executive_summary"]
    # The brief is not one of the assessments.
    assert decision["executive_summary"] not in [a["summary"] for a in body["assessments"]]


async def test_decision_records_dissent_and_unresolved_questions(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)
    decision = (await client.get(f"/api/meetings/{meeting.id}")).json()["decision"]

    assert decision["dissenting_opinions"][0]["agent_id"] == "ceo"
    assert decision["unresolved_questions"]
    assert decision["recommended_option_id"] == "retention"
    assert len(decision["strategic_options"]) == 2
    assert len(decision["action_items"]) == 3
    assert [p["is_dissent"] for p in decision["positions"]].count(True) == 1


async def test_event_log_is_retrievable_and_replayable(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    res = await client.get(f"/api/meetings/{meeting.id}/events")
    assert res.status_code == 200
    events = res.json()
    assert events
    assert [e["sequence_number"] for e in events] == sorted(
        e["sequence_number"] for e in events
    )
    assert events[0]["event_type"] == "meeting_started"
    assert events[-1]["event_type"] == "meeting_completed"

    cursor = events[3]["sequence_number"]
    tail = (await client.get(f"/api/meetings/{meeting.id}/events?after={cursor}")).json()
    assert all(e["sequence_number"] > cursor for e in tail)
    assert len(tail) == len(events) - 4


async def test_meetings_are_listed_for_the_organization(client, db, org_and_user):
    org, user = org_and_user
    await _completed_meeting(db, org, user)
    await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION + " (second)"
    )

    res = await client.get("/api/meetings")
    assert res.status_code == 200
    assert len(res.json()) == 2


async def test_the_api_reports_token_usage_with_its_parts(client, db, org_and_user):
    """The list and the detail must agree, and the total must be the sum."""
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    detail = (await client.get(f"/api/meetings/{meeting.id}")).json()
    assert detail["total_tokens_used"] > 0
    assert (
        detail["total_tokens_used"]
        == detail["input_tokens_used"] + detail["output_tokens_used"]
    )

    listed = next(m for m in (await client.get("/api/meetings")).json() if m["id"] == detail["id"])
    assert listed["total_tokens_used"] == detail["total_tokens_used"]


async def test_another_organization_cannot_read_the_meeting(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    outsider = User(email="rival@other.example.com", hashed_password=hash_password("x" * 12))
    other_org = Organization(name="Rival Co", slug="rival-co")
    db.add_all([outsider, other_org])
    await db.flush()
    db.add(
        OrganizationMember(
            organization_id=other_org.id, user_id=outsider.id, role=OrgRole.OWNER
        )
    )
    await db.flush()

    headers = {"Authorization": f"Bearer {create_access_token(str(outsider.id))}"}
    assert (await client.get(f"/api/meetings/{meeting.id}", headers=headers)).status_code == 404
    assert (
        await client.get(f"/api/meetings/{meeting.id}/events", headers=headers)
    ).status_code == 404


async def test_missing_meeting_returns_404(client):
    assert (await client.get(f"/api/meetings/{uuid.uuid4()}")).status_code == 404


async def test_cancelling_a_draft_meeting(client):
    created = (
        await client.post(
            "/api/meetings", json={"question": QUESTION, "start_immediately": False}
        )
    ).json()

    res = await client.post(f"/api/meetings/{created['id']}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


async def test_a_completed_meeting_cannot_be_cancelled(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    res = await client.post(f"/api/meetings/{meeting.id}/cancel")
    assert res.status_code == 400
    assert "already completed" in res.json()["error"]["message"]


async def test_a_completed_meeting_cannot_be_restarted(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    res = await client.post(f"/api/meetings/{meeting.id}/start")
    assert res.status_code == 409


async def test_the_founder_accepts_the_recommendation(client, db, org_and_user):
    """Human authority: the board advises, the user decides."""
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)
    decision_id = (await client.get(f"/api/meetings/{meeting.id}")).json()["decision"]["id"]

    res = await client.patch(
        f"/api/decisions/{decision_id}",
        json={"status": "accepted", "decision_notes": "Agreed; starting with churn diagnosis."},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == DecisionStatus.ACCEPTED.value
    assert body["decision_notes"].startswith("Agreed")

    # And it persists.
    again = await client.get(f"/api/decisions/{decision_id}")
    assert again.json()["status"] == "accepted"


async def test_the_founder_can_defer_or_reject(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)
    decision_id = (await client.get(f"/api/meetings/{meeting.id}")).json()["decision"]["id"]

    for verdict in ("deferred", "rejected"):
        res = await client.patch(f"/api/decisions/{decision_id}", json={"status": verdict})
        assert res.status_code == 200
        assert res.json()["status"] == verdict


async def test_decisions_are_listed_and_scoped(client, db, org_and_user):
    org, user = org_and_user
    await _completed_meeting(db, org, user)

    res = await client.get("/api/decisions")
    assert res.status_code == 200
    assert len(res.json()) == 1

    outsider = User(email="nosy@other.example.com", hashed_password=hash_password("x" * 12))
    other_org = Organization(name="Nosy Co", slug="nosy-co")
    db.add_all([outsider, other_org])
    await db.flush()
    db.add(
        OrganizationMember(
            organization_id=other_org.id, user_id=outsider.id, role=OrgRole.OWNER
        )
    )
    await db.flush()

    headers = {"Authorization": f"Bearer {create_access_token(str(outsider.id))}"}
    assert (await client.get("/api/decisions", headers=headers)).json() == []


async def test_meeting_endpoints_require_authentication(client):
    res = await client.get("/api/meetings", headers={"Authorization": ""})
    assert res.status_code == 401


async def test_a_failed_meeting_reports_why(client, db, org_and_user):
    """Failures are visible, not silent."""
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    _, model = scripted_board(fail={"chairperson": "agenda"})
    from app.orchestration.meeting import MeetingAborted

    with pytest.raises(MeetingAborted):
        await svc.run_meeting(db, meeting, user_id=user.id, model=model)

    body = (await client.get(f"/api/meetings/{meeting.id}")).json()
    assert body["status"] == MeetingStatus.FAILED.value
    assert "could not produce an agenda" in body["failure_reason"]

    events = (await client.get(f"/api/meetings/{meeting.id}/events")).json()
    assert events[-1]["event_type"] == "meeting_failed"
    assert events[-1]["payload"]["code"] == "agenda_failed"
