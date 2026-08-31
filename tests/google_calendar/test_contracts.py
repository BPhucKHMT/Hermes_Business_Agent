from datetime import datetime, timezone
import pytest

from tools.calendar.contracts import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEvent,
    EventDraft,
    EventDraftStatus,
    FreeSlot,
    compute_draft_idempotency_key,
)


def test_compute_draft_idempotency_key_is_deterministic() -> None:
    key1 = compute_draft_idempotency_key(
        principal_id="telegram:default:12345",
        calendar_id="primary",
        summary="Weekly Sync",
        start_time="2026-09-01T10:00:00Z",
        end_time="2026-09-01T11:00:00Z",
    )
    key2 = compute_draft_idempotency_key(
        principal_id="telegram:default:12345",
        calendar_id="primary",
        summary="weekly sync",
        start_time="2026-09-01T10:00:00Z",
        end_time="2026-09-01T11:00:00Z",
    )
    assert key1 == key2
    assert len(key1) == 64


def test_event_draft_structure() -> None:
    draft = EventDraft(
        draft_id="drf-1234",
        idempotency_key="key-1234",
        principal_id="telegram:default:12345",
        calendar_id="primary",
        summary="Team Meeting",
        description="Discuss roadmap",
        location="Room 3B",
        start_time="2026-09-01T14:00:00Z",
        end_time="2026-09-01T15:00:00Z",
        attendees=("alex@example.com", "klaus@example.com"),
        created_at="2026-08-31T12:00:00Z",
        status=EventDraftStatus.DRAFT,
    )
    assert draft.status == EventDraftStatus.DRAFT
    assert len(draft.attendees) == 2
    assert draft.committed_event_id is None


def test_calendar_event_structure() -> None:
    ev = CalendarEvent(
        event_id="evt-999",
        calendar_id="primary",
        summary="Product Launch",
        description="Doors open",
        location="Thao Dien",
        start_time="2026-12-08T09:00:00Z",
        end_time="2026-12-08T18:00:00Z",
        html_link="https://www.google.com/calendar/event?eid=999",
        status="confirmed",
        is_all_day=False,
    )
    assert ev.event_id == "evt-999"
    assert ev.status == "confirmed"
