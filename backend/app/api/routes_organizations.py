"""Organization CRUD and the company profile it owns."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentOrg, CurrentUser, DbSession
from app.api.routes_auth import _unique_slug, slugify
from app.models.enums import OrgRole
from app.models.identity import CompanyProfile, Organization, OrganizationMember
from app.schemas.identity import (
    CompanyProfileRead,
    CompanyProfileUpsert,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)

router = APIRouter(tags=["organizations"])


async def _require_membership(
    db: DbSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> OrganizationMember:
    member = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        # 404 rather than 403 so a non-member cannot probe which org ids exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return member


@router.post(
    "/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED
)
async def create_organization(
    payload: OrganizationCreate, user: CurrentUser, db: DbSession
) -> OrganizationRead:
    org = Organization(name=payload.name, slug=await _unique_slug(db, slugify(payload.name)))
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))
    await db.flush()
    return OrganizationRead.model_validate(org)


@router.get("/organizations/{organization_id}", response_model=OrganizationRead)
async def get_organization(
    organization_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> OrganizationRead:
    await _require_membership(db, user.id, organization_id)
    org = await db.get(Organization, organization_id)
    if org is None or org.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationRead.model_validate(org)


@router.patch("/organizations/{organization_id}", response_model=OrganizationRead)
async def update_organization(
    organization_id: uuid.UUID, payload: OrganizationUpdate, user: CurrentUser, db: DbSession
) -> OrganizationRead:
    member = await _require_membership(db, user.id, organization_id)
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires owner or admin role"
        )

    org = await db.get(Organization, organization_id)
    if org is None or org.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if payload.name is not None:
        org.name = payload.name
    await db.flush()
    return OrganizationRead.model_validate(org)


@router.get("/company-profile", response_model=CompanyProfileRead | None)
async def get_company_profile(org: CurrentOrg, db: DbSession) -> CompanyProfileRead | None:
    profile = (
        await db.execute(
            select(CompanyProfile).where(CompanyProfile.organization_id == org.id)
        )
    ).scalar_one_or_none()
    return CompanyProfileRead.model_validate(profile) if profile else None


@router.put("/company-profile", response_model=CompanyProfileRead)
async def upsert_company_profile(
    payload: CompanyProfileUpsert, org: CurrentOrg, db: DbSession
) -> CompanyProfileRead:
    profile = (
        await db.execute(
            select(CompanyProfile).where(CompanyProfile.organization_id == org.id)
        )
    ).scalar_one_or_none()

    if profile is None:
        profile = CompanyProfile(organization_id=org.id, **payload.model_dump())
        db.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return CompanyProfileRead.model_validate(profile)
