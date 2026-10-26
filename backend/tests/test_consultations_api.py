"""The consultation endpoint end to end: real agent run, real persistence."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents.registry import AgentId
from app.core.security import create_access_token, hash_password
from app.models.consultation import ConsultationMessage
from app.models.enums import OrgRole
from app.models.identity import Organization, OrganizationMember, User
from app.models.usage import LLMUsageRecord
from tests.capture import recorder_model


async def test_create_consultation_with_opening_question(client, override_agent_model):
    recorder, model = recorder_model(answer="Runway is 12 months at current burn.")
    override_agent_model(model)

    res = await client.post(
        "/api/consultations",
        json={"agent_id": "cfo", "opening_message": "How much runway do we have?"},
    )
    assert res.status_code == 201, res.text

    body = res.json()
    assert body["agent_id"] == "cfo"
    assert body["title"] == "Consultation with CFO"
    assert len(body["messages"]) == 2

    user_msg, agent_msg = body["messages"]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "How much runway do we have?"
    assert agent_msg["role"] == "agent"
    assert agent_msg["agent_id"] == "cfo"
    assert agent_msg["content"] == "Runway is 12 months at current burn."

    # The CFO's own instructions reached the model, not a generic prompt.
    assert "Yusuf Benali" in recorder.last.instructions
    assert "you are the one person who will not round" in recorder.last.instructions.lower()


async def test_structured_output_is_persisted_alongside_the_text(client, override_agent_model):
    _, model = recorder_model()
    override_agent_model(model)

    created = await client.post("/api/consultations", json={"agent_id": "coo"})
    cid = created.json()["id"]

    res = await client.post(
        f"/api/consultations/{cid}/messages",
        json={"content": "Can we ship this in six months?"},
    )
    assert res.status_code == 200, res.text

    payload = res.json()
    structured = payload["structured"]
    assert structured["confidence_level"] == "medium"
    assert structured["key_points"]
    assert structured["assumptions"][0]["how_to_validate"]
    assert structured["risks"][0]["severity"] == "moderate"
    assert structured["recommended_actions"][0]["priority"] == "high"

    # And the same structure is on the stored message, not just the response.
    assert payload["agent_message"]["structured_output"]["confidence_level"] == "medium"


async def test_conversation_survives_a_refresh(client, override_agent_model, db):
    """The definition-of-done check: ask, reload, see the saved conversation."""
    _, model = recorder_model(answer="Persisted answer.")
    override_agent_model(model)

    cid = (await client.post("/api/consultations", json={"agent_id": "cgo"})).json()["id"]
    await client.post(f"/api/consultations/{cid}/messages", json={"content": "First question"})
    await client.post(f"/api/consultations/{cid}/messages", json={"content": "Second question"})

    # Re-fetch the way the page does after a reload.
    reloaded = await client.get(f"/api/consultations/{cid}")
    assert reloaded.status_code == 200
    messages = reloaded.json()["messages"]
    assert [m["content"] for m in messages] == [
        "First question",
        "Persisted answer.",
        "Second question",
        "Persisted answer.",
    ]

    # Present in the database itself, not only in the response.
    rows = (
        (
            await db.execute(
                select(ConsultationMessage)
                .where(ConsultationMessage.consultation_id == uuid.UUID(cid))
                .order_by(ConsultationMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 4
    assert rows[1].model_messages, "agent turn should persist replayable history"


async def test_prior_turns_are_replayed_to_the_model(client, override_agent_model):
    recorder, model = recorder_model()
    override_agent_model(model)

    cid = (await client.post("/api/consultations", json={"agent_id": "ceo"})).json()["id"]
    await client.post(f"/api/consultations/{cid}/messages", json={"content": "Turn one"})
    await client.post(f"/api/consultations/{cid}/messages", json={"content": "Turn two"})

    # The second call must have seen the first exchange.
    assert len(recorder.calls) == 2
    assert recorder.calls[0].user_prompts == ["Turn one"]
    assert "Turn one" in recorder.calls[1].user_prompts
    assert "Turn two" in recorder.calls[1].user_prompts


async def test_usage_is_recorded_for_each_turn(client, override_agent_model, db, org_and_user):
    _, model = recorder_model()
    override_agent_model(model)
    org, _ = org_and_user

    cid = (await client.post("/api/consultations", json={"agent_id": "cfo"})).json()["id"]
    await client.post(f"/api/consultations/{cid}/messages", json={"content": "Question"})

    records = (
        (
            await db.execute(
                select(LLMUsageRecord).where(LLMUsageRecord.organization_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(records) == 1
    record = records[0]
    assert record.agent_id == "cfo"
    assert record.stage == "consultation"
    assert record.request_count >= 1
    assert record.duration_ms is not None


async def test_company_context_reaches_the_agent(client, override_agent_model):
    recorder, model = recorder_model()
    override_agent_model(model)

    await client.post(
        "/api/consultations",
        json={"agent_id": "cfo", "opening_message": "What is our runway?"},
    )

    sent = recorder.last.instructions
    assert "Northstar Labs" in sent
    assert "2,000,000" in sent  # ARR from the seeded profile
    assert "15.0%" in sent  # churn rendered as a percentage


async def test_unknown_agent_is_rejected(client):
    res = await client.post("/api/consultations", json={"agent_id": "head_of_vibes"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "http_404"


async def test_chairperson_cannot_be_consulted_one_on_one(client):
    res = await client.post("/api/consultations", json={"agent_id": "chairperson"})
    assert res.status_code == 400
    assert "one-on-one" in res.json()["error"]["message"]


async def test_consultations_are_listed_for_the_organization(client, override_agent_model):
    _, model = recorder_model()
    override_agent_model(model)

    await client.post("/api/consultations", json={"agent_id": "cfo"})
    await client.post("/api/consultations", json={"agent_id": "coo"})

    res = await client.get("/api/consultations")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert {c["agent_id"] for c in body} == {"cfo", "coo"}

    filtered = await client.get("/api/consultations?agent_id=cfo")
    assert len(filtered.json()) == 1


async def test_another_organization_cannot_read_the_consultation(
    client, override_agent_model, db
):
    """Cross-tenant isolation, enforced in the query rather than checked after."""
    _, model = recorder_model()
    override_agent_model(model)
    cid = (await client.post("/api/consultations", json={"agent_id": "cfo"})).json()["id"]

    outsider = User(email="outsider@other.test", hashed_password=hash_password("x" * 12))
    other_org = Organization(name="Other Co", slug="other-co")
    db.add_all([outsider, other_org])
    await db.flush()
    db.add(
        OrganizationMember(
            organization_id=other_org.id, user_id=outsider.id, role=OrgRole.OWNER
        )
    )
    await db.flush()

    res = await client.get(
        f"/api/consultations/{cid}",
        headers={"Authorization": f"Bearer {create_access_token(str(outsider.id))}"},
    )
    assert res.status_code == 404


async def test_consultation_requires_authentication(client):
    res = await client.post(
        "/api/consultations", json={"agent_id": "cfo"}, headers={"Authorization": ""}
    )
    assert res.status_code == 401


async def test_missing_consultation_returns_404(client):
    res = await client.get(f"/api/consultations/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.parametrize(
    "agent_id", [a.value for a in AgentId if a is not AgentId.CHAIRPERSON]
)
async def test_every_consultable_executive_answers_as_itself(
    client, override_agent_model, agent_id
):
    """Eight separate consultations, eight different sets of instructions."""
    recorder, model = recorder_model()
    override_agent_model(model)

    res = await client.post(
        "/api/consultations",
        json={"agent_id": agent_id, "opening_message": "What matters most right now?"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["messages"][1]["agent_id"] == agent_id

    from app.agents.registry import REGISTRY

    assert REGISTRY[AgentId(agent_id)].display_name in recorder.last.instructions
