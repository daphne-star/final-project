"""Server-Sent Events for live meetings.

The stream tails the **persisted** event log rather than subscribing to an
in-process bus. That choice is deliberate and has three consequences worth
stating:

* Reconnection is correct by construction. The SSE ``id:`` field carries the
  event's sequence number, the browser replays it as ``Last-Event-ID``, and
  the next read simply starts after that cursor. No event is delivered twice
  and none is skipped.
* A reader does not have to share a process with the orchestrator. A second
  worker, or a client that connects after the meeting finished, sees exactly
  the same ordered history.
* The cost is latency: updates appear within one poll interval rather than
  instantly. For a workflow whose individual steps take 5-30 seconds that is
  not a meaningful delay, and it buys durability that an in-memory queue
  cannot offer without Redis — which the spec rules out for the MVP.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.db.session import AsyncSessionLocal
from app.models.enums import MeetingStatus
from app.models.meeting import Meeting
from app.services.meeting import list_events

logger = logging.getLogger(__name__)

#: How often to look for new events while a meeting is running.
POLL_INTERVAL_SECONDS = 0.4

#: Comment frames keep proxies from closing an idle connection.
HEARTBEAT_SECONDS = 15.0

#: Hard ceiling so a wedged meeting cannot hold a connection open forever.
MAX_STREAM_SECONDS = 60 * 30

TERMINAL_STATUSES = frozenset(
    {MeetingStatus.COMPLETED, MeetingStatus.FAILED, MeetingStatus.CANCELLED}
)


def format_sse(*, event: str, data: dict, event_id: int | None = None) -> str:
    """Render one SSE frame.

    ``id`` is the sequence number, which is what makes Last-Event-ID replay
    work without a server-side subscription registry.
    """
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    # json.dumps never emits a raw newline, so one data line is always enough.
    lines.append(f"data: {json.dumps(data, default=str)}")
    return "\n".join(lines) + "\n\n"


def heartbeat() -> str:
    return f": heartbeat {datetime.now(UTC).isoformat()}\n\n"


async def meeting_event_stream(
    meeting_id: uuid.UUID,
    organization_id: uuid.UUID,
    *,
    after_sequence: int = 0,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    max_seconds: float = MAX_STREAM_SECONDS,
) -> AsyncIterator[str]:
    """Yield SSE frames for one meeting, from ``after_sequence`` onward.

    Opens short-lived sessions per poll rather than holding one for the life
    of the connection, so a long meeting does not pin a pool connection.
    """
    cursor = after_sequence
    started = asyncio.get_running_loop().time()
    last_heartbeat = started

    while True:
        now = asyncio.get_running_loop().time()
        if now - started > max_seconds:
            yield format_sse(
                event="stream_timeout",
                data={
                    "reason": "Stream exceeded its maximum duration.",
                    "last_sequence": cursor,
                    "meeting_id": str(meeting_id),
                },
            )
            return

        async with AsyncSessionLocal() as db:
            meeting = await db.get(Meeting, meeting_id)
            if meeting is None or meeting.organization_id != organization_id:
                # Deleted mid-stream, or never ours. Say so and stop rather
                # than silently going quiet.
                yield format_sse(
                    event="stream_error",
                    data={"reason": "Meeting is no longer accessible."},
                )
                return

            events = await list_events(db, meeting_id, after_sequence=cursor, limit=200)
            status = meeting.status

        for event in events:
            cursor = event.sequence_number
            yield format_sse(
                event=event.event_type,
                event_id=event.sequence_number,
                data={
                    "event_id": str(event.id),
                    "meeting_id": str(meeting_id),
                    "sequence_number": event.sequence_number,
                    "event_type": event.event_type,
                    "agent_id": event.agent_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                },
            )
            last_heartbeat = asyncio.get_running_loop().time()

        if status in TERMINAL_STATUSES and not events:
            # Drained, and nothing more is coming. A final frame tells the
            # client this is a clean end rather than a dropped connection,
            # so it does not try to reconnect.
            yield format_sse(
                event="stream_closed",
                data={
                    "meeting_id": str(meeting_id),
                    "status": status.value,
                    "last_sequence": cursor,
                },
            )
            return

        if not events:
            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                yield heartbeat()
                last_heartbeat = now
            await asyncio.sleep(poll_interval)


async def reconcile_orphaned_meetings() -> int:
    """Fail meetings left RUNNING by a process that died.

    The orchestrator runs as an in-process asyncio task, so a restart orphans
    anything mid-flight. Without this a crashed meeting would sit at RUNNING
    forever and its SSE stream would poll until the hard timeout. Called once
    at application startup.

    This is the honest limitation of not having a durable job queue: work in
    flight at shutdown is lost, not resumed. It is marked failed so the user
    can see what happened and start again.
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        stale = (
            (
                await db.execute(
                    select(Meeting).where(Meeting.status == MeetingStatus.RUNNING)
                )
            )
            .scalars()
            .all()
        )
        for meeting in stale:
            meeting.status = MeetingStatus.FAILED
            meeting.failure_reason = (
                "The server restarted while this meeting was running. In-flight "
                "meetings are not resumable; start a new one."
            )
            logger.warning("Marking orphaned meeting %s as failed", meeting.id)
        if stale:
            await db.commit()
        return len(stale)
