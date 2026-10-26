"""SSE: frame format, ordering, replay, reconnection, and clean close."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.factory import reset_agent_cache
from app.models.enums import MeetingStatus
from app.orchestration import stream as stream_mod
from app.orchestration.events import EventType
from app.orchestration.meeting import MeetingLimits
from app.orchestration.stream import format_sse, meeting_event_stream
from app.services import meeting as svc
from tests.board_model import scripted_board

QUESTION = (
    "Should we prioritise improving retention, international expansion, "
    "or launching a new product?"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


@pytest_asyncio.fixture
async def stream_sessions(db_connection, monkeypatch):
    """Point the stream's own session factory at the test connection.

    The stream deliberately opens short-lived sessions of its own, which in
    production is what lets it survive across workers. In a test that work
    has to land on the same uncommitted transaction, so the factory is bound
    to the test connection instead.
    """
    maker = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(stream_mod, "AsyncSessionLocal", maker)
    return maker


async def _completed_meeting(db, org, user):
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    _, model = scripted_board()
    await svc.run_meeting(
        db,
        meeting,
        user_id=user.id,
        model=model,
        limits=MeetingLimits(max_debate_rounds=1, model_timeout_seconds=10),
    )
    return meeting


def _parse(frames: list[str]) -> list[dict]:
    """Parse SSE text into {id, event, data} records, skipping comments."""
    out: list[dict] = []
    for frame in frames:
        if frame.startswith(":"):
            continue
        record: dict = {}
        for line in frame.strip().splitlines():
            field, _, value = line.partition(": ")
            if field == "id":
                record["id"] = int(value)
            elif field == "event":
                record["event"] = value
            elif field == "data":
                record["data"] = json.loads(value)
        if record:
            out.append(record)
    return out


# --------------------------------------------------------------------------
# Frame format
# --------------------------------------------------------------------------


def test_sse_frame_has_id_event_and_data():
    frame = format_sse(event="agenda_created", data={"a": 1}, event_id=7)
    assert frame == 'id: 7\nevent: agenda_created\ndata: {"a": 1}\n\n'
    assert frame.endswith("\n\n")


def test_sse_frame_data_is_always_a_single_line():
    """A newline inside data would split the frame and corrupt the stream."""
    frame = format_sse(
        event="agent_message_completed",
        data={"summary": "line one\nline two\n\nline three"},
        event_id=1,
    )
    data_lines = [ln for ln in frame.strip().splitlines() if ln.startswith("data: ")]
    assert len(data_lines) == 1
    assert json.loads(data_lines[0][6:])["summary"] == "line one\nline two\n\nline three"


def test_sse_frame_without_id_omits_the_field():
    frame = format_sse(event="stream_closed", data={})
    assert not frame.startswith("id:")


# --------------------------------------------------------------------------
# Streaming a finished meeting
# --------------------------------------------------------------------------


async def test_stream_replays_a_completed_meeting_then_closes(
    db, org_and_user, stream_sessions
):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    frames = [f async for f in meeting_event_stream(meeting.id, org.id, poll_interval=0.01)]
    records = _parse(frames)

    assert records[0]["event"] == EventType.MEETING_STARTED.value
    assert records[-1]["event"] == "stream_closed"
    assert records[-1]["data"]["status"] == "completed"

    # The generator terminates on its own; it does not poll forever.
    assert len(records) > 10


async def test_streamed_events_are_in_gapless_sequence_order(
    db, org_and_user, stream_sessions
):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    records = _parse(
        [f async for f in meeting_event_stream(meeting.id, org.id, poll_interval=0.01)]
    )
    ids = [r["id"] for r in records if "id" in r]
    assert ids == sorted(ids)
    assert ids == list(range(1, len(ids) + 1))


async def test_every_frame_carries_the_full_typed_payload(
    db, org_and_user, stream_sessions
):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    records = _parse(
        [f async for f in meeting_event_stream(meeting.id, org.id, poll_interval=0.01)]
    )
    for record in records:
        if record["event"] in ("stream_closed", "stream_error", "stream_timeout"):
            continue
        data = record["data"]
        assert set(data) >= {
            "event_id",
            "meeting_id",
            "sequence_number",
            "event_type",
            "agent_id",
            "payload",
            "timestamp",
        }
        assert data["meeting_id"] == str(meeting.id)


async def test_the_stream_carries_the_events_the_ui_needs(
    db, org_and_user, stream_sessions
):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    records = _parse(
        [f async for f in meeting_event_stream(meeting.id, org.id, poll_interval=0.01)]
    )
    types = {r["event"] for r in records}
    for required in (
        EventType.MEETING_STARTED,
        EventType.AGENDA_CREATED,
        EventType.AGENT_STARTED,
        EventType.AGENT_STATUS_CHANGED,
        EventType.AGENT_MESSAGE_COMPLETED,
        EventType.OBJECTION_RAISED,
        EventType.POSITION_REVISED,
        EventType.DECISION_GENERATED,
        EventType.MEETING_COMPLETED,
    ):
        assert required.value in types, f"{required.value} never reached the stream"


# --------------------------------------------------------------------------
# Reconnection
# --------------------------------------------------------------------------


async def test_resuming_after_a_cursor_delivers_no_duplicates(
    db, org_and_user, stream_sessions
):
    """The property reconnection depends on: resume returns the tail exactly."""
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    full = _parse(
        [f async for f in meeting_event_stream(meeting.id, org.id, poll_interval=0.01)]
    )
    full_ids = [r["id"] for r in full if "id" in r]
    cut = full_ids[len(full_ids) // 2]

    resumed = _parse(
        [
            f
            async for f in meeting_event_stream(
                meeting.id, org.id, after_sequence=cut, poll_interval=0.01
            )
        ]
    )
    resumed_ids = [r["id"] for r in resumed if "id" in r]

    assert all(i > cut for i in resumed_ids)
    # Exactly the tail: concatenating the two halves reproduces the whole.
    assert [i for i in full_ids if i <= cut] + resumed_ids == full_ids


async def test_resuming_past_the_end_returns_only_the_close_frame(
    db, org_and_user, stream_sessions
):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    records = _parse(
        [
            f
            async for f in meeting_event_stream(
                meeting.id, org.id, after_sequence=10_000, poll_interval=0.01
            )
        ]
    )
    assert len(records) == 1
    assert records[0]["event"] == "stream_closed"


# --------------------------------------------------------------------------
# Failure and scoping
# --------------------------------------------------------------------------


async def test_a_failed_meeting_streams_the_failure_then_closes(
    db, org_and_user, stream_sessions
):
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    _, model = scripted_board(fail={"chairperson": "agenda"})
    from app.orchestration.meeting import MeetingAborted

    with pytest.raises(MeetingAborted):
        await svc.run_meeting(db, meeting, user_id=user.id, model=model)

    records = _parse(
        [f async for f in meeting_event_stream(meeting.id, org.id, poll_interval=0.01)]
    )
    types = [r["event"] for r in records]
    assert EventType.AGENT_FAILED.value in types
    assert EventType.MEETING_FAILED.value in types
    assert records[-1]["event"] == "stream_closed"
    assert records[-1]["data"]["status"] == "failed"


async def test_another_organization_gets_an_error_frame_not_the_events(
    db, org_and_user, stream_sessions
):
    import uuid

    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)

    records = _parse(
        [
            f
            async for f in meeting_event_stream(
                meeting.id, uuid.uuid4(), poll_interval=0.01
            )
        ]
    )
    assert len(records) == 1
    assert records[0]["event"] == "stream_error"


async def test_stream_stops_at_its_maximum_duration(db, org_and_user, stream_sessions):
    """A wedged meeting must not hold the connection open indefinitely."""
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    meeting.status = MeetingStatus.RUNNING  # running, but nothing is producing
    await db.flush()

    records = _parse(
        [
            f
            async for f in meeting_event_stream(
                meeting.id, org.id, poll_interval=0.01, max_seconds=0.05
            )
        ]
    )
    assert records[-1]["event"] == "stream_timeout"


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------


async def test_stream_endpoint_requires_authentication(client, db, org_and_user):
    org, user = org_and_user
    meeting = await _completed_meeting(db, org, user)
    res = await client.get(
        f"/api/meetings/{meeting.id}/stream", headers={"Authorization": ""}
    )
    assert res.status_code == 401


async def test_stream_endpoint_404s_for_an_unknown_meeting(client):
    import uuid

    res = await client.get(f"/api/meetings/{uuid.uuid4()}/stream")
    assert res.status_code == 404


async def test_orphaned_running_meetings_are_failed_on_startup(
    db, org_and_user, stream_sessions, monkeypatch
):
    """A restart must not leave a meeting stuck at RUNNING forever."""
    monkeypatch.setattr(
        "app.orchestration.stream.AsyncSessionLocal", stream_sessions, raising=False
    )
    org, user = org_and_user
    meeting = await svc.create_meeting(
        db, organization_id=org.id, user_id=user.id, question=QUESTION
    )
    meeting.status = MeetingStatus.RUNNING
    await db.flush()

    count = await stream_mod.reconcile_orphaned_meetings()

    assert count >= 1
    await db.refresh(meeting)
    assert meeting.status is MeetingStatus.FAILED
    assert "server restarted" in meeting.failure_reason
