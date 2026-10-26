"""Registration, login, and the current-identity endpoint."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import OrgRole
from app.models.identity import Organization, OrganizationMember, User
from app.schemas.identity import (
    MeResponse,
    OrganizationMembershipRead,
    OrganizationRead,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
)

router = APIRouter(tags=["auth"])


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "org"


async def _unique_slug(db: DbSession, base: str) -> str:
    slug = base
    suffix = 1
    while (
        await db.execute(select(Organization.id).where(Organization.slug == slug))
    ).scalar_one_or_none() is not None:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: DbSession) -> TokenResponse:
    existing = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account with that email exists"
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.flush()

    org_name = payload.organization_name or (
        f"{payload.full_name}'s Company" if payload.full_name else "My Company"
    )
    org = Organization(name=org_name, slug=await _unique_slug(db, slugify(org_name)))
    db.add(org)
    await db.flush()
    db.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER)
    )
    await db.flush()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: DbSession) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    # Same response whether the email is unknown or the password is wrong.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser, db: DbSession) -> MeResponse:
    memberships = (
        (
            await db.execute(
                select(OrganizationMember)
                .where(OrganizationMember.user_id == user.id)
                .options(selectinload(OrganizationMember.organization))
                .order_by(OrganizationMember.created_at)
            )
        )
        .scalars()
        .all()
    )

    orgs = [
        OrganizationMembershipRead(
            organization=OrganizationRead.model_validate(m.organization), role=m.role
        )
        for m in memberships
        if m.organization.deleted_at is None
    ]
    active: uuid.UUID | None = orgs[0].organization.id if orgs else None

    return MeResponse(
        user=UserRead.model_validate(user), organizations=orgs, active_organization_id=active
    )
