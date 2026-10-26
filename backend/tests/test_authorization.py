"""Who can reach what.

Two questions, asked of the whole API rather than of the endpoints someone
remembered to check:

1. Does every route demand a token, except the handful that are public on
   purpose? The route list is read from the app, so a route added later
   without an auth dependency fails here rather than shipping.
2. Can one organization reach another's rows? Every by-id endpoint is given
   a real id belonging to someone else and must answer 404 -- not 403, which
   would confirm the id exists.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.consultation import Consultation
from app.models.decision import ActionItem, StrategicDecision
from app.models.document import Document
from app.models.enums import DocumentStatus, FactSource, MeetingMode, OrgRole
from app.models.identity import Organization, OrganizationMember, User
from app.models.meeting import Meeting
from app.models.memory import CompanyMemory

# Deliberately public. /health is a liveness probe, /agents returns the nine
# fixed role descriptions that are identical for everyone, and registration
# and login cannot require the token they exist to issue.
PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/agents"),
    ("GET", "/api/agents/{agent_id}"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
}


def _routes() -> list[tuple[str, str]]:
    paths = app.openapi()["paths"]
    return [
        (method.upper(), path)
        for path, operations in sorted(paths.items())
        for method in operations
        if method in ("get", "post", "put", "patch", "delete")
    ]


def _fill(path: str) -> str:
    """Substitute a syntactically valid id for every path parameter."""
    out = path
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        name = out[start + 1 : end]
        out = out[:start] + ("cfo" if name == "agent_id" else str(uuid.uuid4())) + out[end + 1 :]
    return out


def test_the_api_has_routes_to_check():
    """Guards the sweep below: an empty route list would pass vacuously."""
    assert len(_routes()) >= 40


@pytest.mark.asyncio
async def test_every_route_requires_a_token_unless_it_is_public(db):
    """No token at all must mean 401, for every route but the public few."""

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as anon:
            reachable = []
            for method, path in _routes():
                if (method, path) in PUBLIC:
                    continue
                response = await anon.request(method, _fill(path), json={})
                if response.status_code != 401:
                    reachable.append(f"{method} {path} -> {response.status_code}")
            assert not reachable, "reachable without a token: " + "; ".join(reachable)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_a_forged_token_is_rejected(client):
    """A token this server did not sign buys nothing."""
    from jose import jwt

    forged = jwt.encode({"sub": str(uuid.uuid4())}, "not-the-real-key", algorithm="HS256")
    response = await client.get("/api/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_a_token_for_a_deactivated_user_is_rejected(db, org_and_user, client):
    """Deactivation takes effect on the next request, not at token expiry."""
    _, user = org_and_user
    user.is_active = False
    await db.flush()
    response = await client.get("/api/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Cross-tenant access
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def other_org_client(db, org_and_user):
    """A second organization with its own owner, sharing nothing with the first."""
    outsider = User(
        email="outsider@rival.test",
        hashed_password=hash_password("another-correct-horse"),
        full_name="Rival Founder",
    )
    rival = Organization(name="Rival Co", slug="rival-co")
    db.add_all([outsider, rival])
    await db.flush()
    db.add(OrganizationMember(organization_id=rival.id, user_id=outsider.id, role=OrgRole.OWNER))
    await db.flush()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {create_access_token(str(outsider.id))}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def org_a_rows(db, org_and_user):
    """One row of every org-scoped kind, all belonging to the first org."""
    org, _user = org_and_user

    meeting = Meeting(
        organization_id=org.id,
        title="Upmarket or self-serve",
        question="Should we move upmarket?",
        mode=MeetingMode.EXECUTIVE_MEETING,
    )
    decision = StrategicDecision(
        organization_id=org.id,
        title="Segment the move",
        problem_statement="Enterprise-only would abandon the self-serve base.",
        executive_summary="Move upmarket for new logos; keep self-serve on maintenance.",
    )
    action = ActionItem(organization_id=org.id, description="Model the segmented P&L")
    consultation = Consultation(
        organization_id=org.id, agent_id="cfo", title="Runway sanity check"
    )
    document = Document(
        organization_id=org.id,
        filename="board-pack.md",
        content_type="text/markdown",
        size_bytes=42,
        storage_path="/nowhere/board-pack.md",
        status=DocumentStatus.INDEXED,
    )
    memory = CompanyMemory(
        organization_id=org.id,
        key="churn_breakdown",
        value="Enterprise renews at 96%; churn is self-serve.",
        source_kind=FactSource.USER_CONFIRMED,
    )
    db.add_all([meeting, decision, action, consultation, document, memory])
    await db.flush()
    return {
        "organization": org,
        "meeting": meeting,
        "decision": decision,
        "action_item": action,
        "consultation": consultation,
        "document": document,
        "memory": memory,
    }


@pytest.mark.asyncio
async def test_another_org_cannot_reach_any_of_these_rows(other_org_client, org_a_rows):
    """Real ids, a valid token, the wrong organization: 404 every time."""
    meeting_id = org_a_rows["meeting"].id
    decision_id = org_a_rows["decision"].id
    memory_id = org_a_rows["memory"].id

    attempts = [
        ("GET", f"/api/meetings/{meeting_id}"),
        ("GET", f"/api/meetings/{meeting_id}/events"),
        ("GET", f"/api/meetings/{meeting_id}/stream"),
        ("POST", f"/api/meetings/{meeting_id}/start"),
        ("POST", f"/api/meetings/{meeting_id}/cancel"),
        ("POST", f"/api/meetings/{meeting_id}/pause"),
        ("POST", f"/api/meetings/{meeting_id}/resume"),
        ("GET", f"/api/meetings/{meeting_id}/interventions"),
        ("GET", f"/api/decisions/{decision_id}"),
        ("GET", f"/api/decisions/{decision_id}/export"),
        ("GET", f"/api/consultations/{org_a_rows['consultation'].id}"),
        ("DELETE", f"/api/documents/{org_a_rows['document'].id}"),
        ("POST", f"/api/memory/{memory_id}/confirm"),
        ("DELETE", f"/api/memory/{memory_id}"),
        ("GET", f"/api/organizations/{org_a_rows['organization'].id}"),
    ]

    leaks = []
    for method, path in attempts:
        response = await other_org_client.request(method, path, json={})
        if response.status_code != 404:
            leaks.append(f"{method} {path} -> {response.status_code}")
    assert not leaks, "reachable across organizations: " + "; ".join(leaks)


@pytest.mark.asyncio
async def test_writes_scoped_to_the_other_org_are_refused(other_org_client, org_a_rows):
    """The write paths that need a real body, checked with one."""
    patched = await other_org_client.patch(
        f"/api/decisions/{org_a_rows['decision'].id}",
        json={"status": "accepted", "decision_notes": "mine now"},
    )
    assert patched.status_code == 404

    corrected = await other_org_client.patch(
        f"/api/memory/{org_a_rows['memory'].id}", json={"value": "rewritten"}
    )
    assert corrected.status_code == 404

    item = await other_org_client.patch(
        f"/api/action-items/{org_a_rows['action_item'].id}", json={"suggested_owner": "Rival Founder"}
    )
    assert item.status_code == 404

    intervention = await other_org_client.post(
        f"/api/meetings/{org_a_rows['meeting'].id}/interventions",
        json={"agent_id": "cfo", "prompt": "Who signed this off?"},
    )
    assert intervention.status_code == 404

    message = await other_org_client.post(
        f"/api/consultations/{org_a_rows['consultation'].id}/messages",
        json={"content": "What is their runway?"},
    )
    assert message.status_code == 404


@pytest.mark.asyncio
async def test_list_endpoints_show_only_the_callers_own_rows(other_org_client, org_a_rows):
    """Nothing belonging to the first org appears in the second org's lists."""
    for path in (
        "/api/meetings",
        "/api/decisions",
        "/api/consultations",
        "/api/documents",
        "/api/memory",
        "/api/action-items",
    ):
        response = await other_org_client.get(path)
        assert response.status_code == 200, path
        assert response.json() == [], f"{path} leaked rows from another organization"

    profile = await other_org_client.get("/api/company-profile")
    assert profile.status_code == 200
    assert profile.json() is None


@pytest.mark.asyncio
async def test_the_org_header_selects_but_cannot_grant(other_org_client, org_a_rows):
    """X-Organization-Id picks among the caller's own orgs; it never adds one."""
    response = await other_org_client.get(
        "/api/meetings",
        headers={"X-Organization-Id": str(org_a_rows["organization"].id)},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_non_member_cannot_rename_an_organization(other_org_client, org_a_rows):
    """Role checks sit behind membership, so a stranger never reaches them."""
    response = await other_org_client.patch(
        f"/api/organizations/{org_a_rows['organization'].id}", json={"name": "Acquired"}
    )
    assert response.status_code == 404
