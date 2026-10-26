"""Users, organizations, membership, and the company profile."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import OrgRole

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.meeting import Meeting


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships: Mapped[list[OrganizationMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)

    members: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    company_profile: Mapped[CompanyProfile | None] = relationship(
        back_populates="organization", cascade="all, delete-orphan", uselist=False
    )
    meetings: Mapped[list[Meeting]] = relationship(back_populates="organization")
    documents: Mapped[list[Document]] = relationship(back_populates="organization")


class OrganizationMember(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        Index("ix_org_member_user", "user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgRole] = mapped_column(
        Enum(OrgRole, name="org_role"), default=OrgRole.MEMBER, nullable=False
    )

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class CompanyProfile(Base, UUIDMixin, TimestampMixin):
    """Structured company context the board reasons over (spec section 9)."""

    __tablename__ = "company_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(200))
    business_model: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(String(100))
    headcount: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)

    products: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    customer_segments: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    goals: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    challenges: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    constraints: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)

    # Headline financials kept as explicit columns so tools can compute on them
    # without fishing through JSON.
    arr_usd: Mapped[float | None] = mapped_column()
    monthly_burn_usd: Mapped[float | None] = mapped_column()
    cash_on_hand_usd: Mapped[float | None] = mapped_column()
    runway_months: Mapped[float | None] = mapped_column()
    annual_churn_rate: Mapped[float | None] = mapped_column()
    revenue_model: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[Organization] = relationship(back_populates="company_profile")
