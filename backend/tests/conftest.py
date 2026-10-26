"""Test fixtures.

Runs against a real PostgreSQL database (ghostboard_test), because the schema
leans on JSONB, enums, and GIN indexes that SQLite cannot model. No test in
the default suite makes a paid model call — the agent model is overridden with
a deterministic one.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.deps import get_agent_model
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import OrgRole
from app.models.identity import CompanyProfile, Organization, OrganizationMember, User

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    str(settings.database_url).replace("/ghostboard", "/ghostboard_test"),
)


@pytest.fixture(scope="session")
def schema() -> None:
    """Create the schema once, in its own throwaway event loop.

    An async session-scoped fixture would bind its asyncpg connections to a
    loop the function-scoped tests do not share, which asyncpg rejects. Doing
    the setup in a self-contained asyncio.run keeps the loops from crossing.
    """

    async def _setup() -> None:
        eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with eng.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await eng.dispose()

    asyncio.run(_setup())


@pytest_asyncio.fixture
async def engine(schema) -> AsyncIterator[AsyncEngine]:
    """A fresh engine per test, bound to that test's event loop."""
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session wrapped in a transaction that is rolled back after the test."""
    conn = await engine.connect()
    trans = await conn.begin()
    maker = async_sessionmaker(bind=conn, expire_on_commit=False, autoflush=False)
    session = maker()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def org_and_user(db: AsyncSession) -> tuple[Organization, User]:
    user = User(
        email="founder@northstar.test",
        hashed_password=hash_password("correct-horse-battery"),
        full_name="Test Founder",
    )
    org = Organization(name="Northstar Labs", slug="northstar-labs")
    db.add_all([user, org])
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))
    db.add(
        CompanyProfile(
            organization_id=org.id,
            company_name="Northstar Labs",
            industry="B2B SaaS",
            business_model="Annual subscription",
            stage="Series A",
            headcount=28,
            description="Workflow automation for mid-market logistics teams.",
            revenue_model="Per-seat annual contracts",
            arr_usd=2_000_000,
            monthly_burn_usd=250_000,
            cash_on_hand_usd=3_000_000,
            runway_months=12,
            annual_churn_rate=0.15,
            goals=[{"text": "Sustainable growth"}],
            challenges=[{"text": "Choosing the next strategic priority"}],
            constraints=[],
        )
    )
    await db.flush()
    return org, user


@pytest_asyncio.fixture
async def client(db: AsyncSession, org_and_user) -> AsyncIterator[AsyncClient]:
    """App client bound to the test session, authenticated as the test user."""
    from app.core.security import create_access_token

    _, user = org_and_user

    async def _override_db():
        # The outer transaction owns commit/rollback, so the request-scoped
        # dependency must not commit or the rollback would have nothing to undo.
        yield db

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def override_agent_model():
    """Install a deterministic model for agent runs, and clean up after."""

    def _install(model):
        app.dependency_overrides[get_agent_model] = lambda: model
        return model

    yield _install
    app.dependency_overrides.pop(get_agent_model, None)
