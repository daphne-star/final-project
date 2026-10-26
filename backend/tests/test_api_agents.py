"""Roster endpoints. These need no database, so they run without Postgres."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_list_agents_returns_nine(client: TestClient):
    res = client.get("/api/agents")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 9


def test_list_agents_exposes_visual_identity(client: TestClient):
    """The frontend drives portraits and accents off these fields."""
    for agent in client.get("/api/agents").json():
        assert agent["avatar_ref"]
        assert agent["theme_color"].startswith("#")
        assert agent["symbol"]
        assert agent["expertise_descriptor"]


def test_get_single_agent(client: TestClient):
    res = client.get("/api/agents/cfo")
    assert res.status_code == 200
    assert res.json()["title"] == "Chief Financial Officer"


def test_unknown_agent_returns_structured_404(client: TestClient):
    res = client.get("/api/agents/head_of_vibes")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "http_404"


def test_protected_route_requires_auth(client: TestClient):
    assert client.get("/api/me").status_code == 401
