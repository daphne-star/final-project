"""Auth, user, organization, and company profile payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import OrgRole
from app.schemas.common import ORMModel


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(
        default=None, max_length=200, description="Creates a first org when provided"
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class UserRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime


class OrganizationRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class OrganizationMembershipRead(BaseModel):
    organization: OrganizationRead
    role: OrgRole


class MeResponse(BaseModel):
    user: UserRead
    organizations: list[OrganizationMembershipRead]
    active_organization_id: uuid.UUID | None


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class CompanyProfileRead(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_name: str
    industry: str | None
    business_model: str | None
    stage: str | None
    headcount: int | None
    description: str | None
    products: list[dict]
    customer_segments: list[dict]
    goals: list[dict]
    challenges: list[dict]
    constraints: list[dict]
    arr_usd: float | None
    monthly_burn_usd: float | None
    cash_on_hand_usd: float | None
    runway_months: float | None
    annual_churn_rate: float | None
    revenue_model: str | None
    updated_at: datetime


class CompanyProfileUpsert(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    industry: str | None = None
    business_model: str | None = None
    stage: str | None = None
    headcount: int | None = Field(default=None, ge=0)
    description: str | None = None
    products: list[dict] = Field(default_factory=list)
    customer_segments: list[dict] = Field(default_factory=list)
    goals: list[dict] = Field(default_factory=list)
    challenges: list[dict] = Field(default_factory=list)
    constraints: list[dict] = Field(default_factory=list)
    arr_usd: float | None = Field(default=None, ge=0)
    monthly_burn_usd: float | None = Field(default=None, ge=0)
    cash_on_hand_usd: float | None = Field(default=None, ge=0)
    runway_months: float | None = Field(default=None, ge=0)
    annual_churn_rate: float | None = Field(default=None, ge=0, le=1)
    revenue_model: str | None = None
