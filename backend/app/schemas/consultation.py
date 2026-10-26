"""Consultation request and response payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.agents.schemas import ConsultationResponse
from app.models.enums import MeetingStatus
from app.schemas.common import ORMModel


class ConsultationCreate(BaseModel):
    agent_id: str = Field(description="Must be one of the nine roster agent ids")
    title: str | None = Field(default=None, max_length=300)
    opening_message: str | None = Field(
        default=None,
        max_length=8000,
        description="Optional first question, answered as part of creation",
    )


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ConsultationMessageRead(ORMModel):
    id: uuid.UUID
    role: str
    agent_id: str | None
    content: str
    structured_output: dict | None
    created_at: datetime


class ConsultationRead(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: str
    title: str
    status: MeetingStatus
    created_at: datetime
    updated_at: datetime


class ConsultationDetail(ConsultationRead):
    messages: list[ConsultationMessageRead] = Field(default_factory=list)


class ConsultationSummary(ConsultationRead):
    message_count: int
    last_message_at: datetime | None


class TurnResponse(BaseModel):
    """Both sides of one exchange, plus the typed agent output."""

    user_message: ConsultationMessageRead
    agent_message: ConsultationMessageRead
    structured: ConsultationResponse
