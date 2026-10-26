"""Shared FastAPI dependencies: current user, and organization scoping.

Organization scope is resolved server-side from the authenticated user's
membership. Nothing a model or client *says* about an org id is trusted here —
spec section 8 requires the authenticated context to establish the real scope.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_ai.models import Model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.identity import Organization, OrganizationMember, User

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_agent_model() -> Model | None:
    """Model override for agent runs.

    Returns None in production, so each agent uses its configured provider.
    Tests override this dependency with a deterministic model, which is what
    keeps the suite from needing a paid API call.
    """
    return None


AgentModel = Annotated[Model | None, Depends(get_agent_model)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_organization(
    db: DbSession,
    user: CurrentUser,
    x_organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> Organization:
    """Resolve the active org, verifying membership every time.

    The header only *selects* among orgs the user already belongs to; it can
    never widen access. With no header, fall back to the user's first org.
    """
    stmt = (
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id, Organization.deleted_at.is_(None))
    )

    if x_organization_id:
        try:
            requested = uuid.UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed X-Organization-Id"
            )
        stmt = stmt.where(Organization.id == requested)

    org = (await db.execute(stmt.order_by(Organization.created_at).limit(1))).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No accessible organization for this user",
        )
    return org


CurrentOrg = Annotated[Organization, Depends(get_current_organization)]
