"""Test fixtures.

Runs against a real PostgreSQL database (ghostboard_test), because the schema
leans on JSONB, enums, and GIN indexes that SQLite cannot model. No test in
the default suite makes a paid model call — the agent model is overridden with
a deterministic one.
"""

from __future__ import annotations

import asyncio
import os

# Set before app.core.security builds its CryptContext: bcrypt at the
# production work factor costs ~0.4s per hash, and the suite creates a
# user per test.
os.environ.setdefault("BCRYPT_ROUNDS", "4")
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
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
                # Drop the schema rather than Base.metadata.drop_all. drop_all
                # emits DROP CONSTRAINT by the *current* model's name, which
                # fails against a database built by an earlier version of the
                # models — exactly what happens when a constraint gets renamed
                # or switched to use_alter. Dropping the schema is immune to
                # that and also clears orphaned enum types.
                await conn.execute(text("DROP SCHEMA public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await eng.dispose()

    asyncio.run(_setup())


@pytest_asyncio.fixture
async def engine(schema) -> AsyncIterator[AsyncEngine]:
    """An engine per test, bound to that test's event loop.

    Still per-test: pytest-asyncio gives each test its own loop by default
    and asyncpg connections cannot cross loops. NullPool avoids keeping a
    pooled connection alive past the loop that opened it, which would raise
    on the next test.
    """
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """The AsyncConnection the test transaction runs on.

    Exposed separately so code that opens its own sessions in production —
    the SSE stream does — can be pointed at the same uncommitted transaction.
    """
    conn = await engine.connect()
    trans = await conn.begin()
    try:
        yield conn
    finally:
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def db(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """A session on the test transaction, rolled back after the test."""
    conn = db_connection
    maker = async_sessionmaker(
        bind=conn,
        expire_on_commit=False,
        autoflush=False,
        # The orchestrator commits each event so the SSE stream can see it.
        # Savepoints keep those commits inside the test transaction, so the
        # per-test rollback still cleans up.
        join_transaction_mode="create_savepoint",
    )
    session = maker()
    try:
        yield session
    finally:
        # The connection fixture owns the transaction and the rollback.
        await session.close()


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
