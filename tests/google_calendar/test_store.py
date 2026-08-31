from pathlib import Path
import pytest

from tools.calendar.contracts import (
    CalendarConnection,
    CalendarConnectionStatus,
    EventDraft,
    EventDraftStatus,
)
from tools.calendar.store import CalendarStore


@pytest.fixture
def store(tmp_path: Path) -> CalendarStore:
    return CalendarStore(tmp_path / "calendar_test.sqlite3")


def test_upsert_and_get_connection(store: CalendarStore) -> None:
    conn = CalendarConnection(
        connection_id="conn-101",
        principal_id="telegram:default:7275339077",
        email="klaus@titanai.space",
        calendar_id="primary",
        calendar_name="Klaus Master Calendar",
        status=CalendarConnectionStatus.CONNECTED,
    )
    saved = store.upsert_connection(conn)
    assert saved is not None
    assert saved.email == "klaus@titanai.space"
    assert saved.calendar_name == "Klaus Master Calendar"

    fetched = store.get_connection_by_principal("telegram:default:7275339077")
    assert fetched is not None
    assert fetched.connection_id == "conn-101"


def test_create_and_get_draft(store: CalendarStore) -> None:
    draft = EventDraft(
        draft_id="drf-101",
        idempotency_key="idem-key-101",
        principal_id="telegram:default:7275339077",
        calendar_id="primary",
        summary="Supplier Tasting Session",
        description="Sample protein bars with supplier",
        location="Thao Dien Lab",
        start_time="2026-09-02T14:00:00Z",
        end_time="2026-09-02T15:30:00Z",
        attendees=("supplier@example.com",),
        created_at="2026-08-31T12:00:00Z",
    )
    persisted = store.create_or_get_draft(draft)
    assert persisted.draft_id == "drf-101"
    assert persisted.status == EventDraftStatus.DRAFT

    # Duplicate call returns original
    duplicate = store.create_or_get_draft(draft)
    assert duplicate.draft_id == "drf-101"


def test_transition_draft_status(store: CalendarStore) -> None:
    draft = EventDraft(
        draft_id="drf-102",
        idempotency_key="idem-key-102",
        principal_id="telegram:default:7275339077",
        calendar_id="primary",
        summary="Investor Pitch",
        description="Present Q3 slides",
        location="Zoom",
        start_time="2026-09-03T09:00:00Z",
        end_time="2026-09-03T10:00:00Z",
        attendees=(),
        created_at="2026-08-31T12:00:00Z",
    )
    store.create_or_get_draft(draft)

    committed = store.transition_draft_status(
        draft_id="drf-102",
        from_status=EventDraftStatus.DRAFT,
        to_status=EventDraftStatus.COMMITTED,
        committed_event_id="google-evt-777",
    )
    assert committed.status == EventDraftStatus.COMMITTED
    assert committed.committed_event_id == "google-evt-777"


def test_audit_log_recording(store: CalendarStore) -> None:
    store.record_audit(
        principal_id="telegram:default:7275339077",
        action="test_action",
        target_id="target-1",
        details={"note": "audit ok"},
    )
