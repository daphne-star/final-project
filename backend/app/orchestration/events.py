"""Typed meeting events.

Every event is persisted to ``meeting_events`` before it is handed to any
listener, so a reconnecting client can replay from a sequence number and a
completed meeting can be reconstructed exactly (spec section 12).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    MEETING_STARTED = "meeting_started"
    AGENDA_CREATED = "agenda_created"
    STAGE_CHANGED = "stage_changed"
    AGENT_STARTED = "agent_started"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    AGENT_MESSAGE_COMPLETED = "agent_message_completed"
    OBJECTION_RAISED = "objection_raised"
    POSITION_REVISED = "position_revised"
    AGENT_FAILED = "agent_failed"
    DECISION_GENERATED = "decision_generated"
    MEETING_COMPLETED = "meeting_completed"
    MEETING_CANCELLED = "meeting_cancelled"
    MEETING_FAILED = "meeting_failed"


class MeetingEventModel(BaseModel):
    """One thing that happened, in order."""

    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    meeting_id: uuid.UUID
    sequence_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: EventType
    agent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


#: Called with each event after it is persisted. Phase 4 of the frontend will
#: attach an SSE writer here; the orchestrator does not care who listens.
EventSink = Callable[[MeetingEventModel], Awaitable[None]]


async def noop_sink(_: MeetingEventModel) -> None:
    """Default sink. A meeting with no listener still records everything."""
    return
