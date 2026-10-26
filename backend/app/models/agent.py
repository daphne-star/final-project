"""Per-organization overrides for the fixed nine-agent roster."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentConfiguration(Base, UUIDMixin, TimestampMixin):
    """Optional per-org model settings for one roster agent.

    The roster itself is fixed in code (app/agents/registry.py); this table only
    holds overrides, so an organization can run the CFO on a different model
    without touching the agent architecture.
    """

    __tablename__ = "agent_configurations"
    __table_args__ = (UniqueConstraint("organization_id", "agent_id", name="uq_org_agent"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    model_name: Mapped[str | None] = mapped_column(String(128))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
