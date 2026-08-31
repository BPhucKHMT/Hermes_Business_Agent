from pathlib import Path
from types import SimpleNamespace
import pytest

from tools.calendar.contracts import EventDraftStatus
from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import load_calendar_policy
from tools.calendar.service import CalendarService
from tools.calendar.store import CalendarStore

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def service(tmp_path: Path) -> CalendarService:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)
    store = CalendarStore(tmp_path / "test_calendar.sqlite3")
    client = GoogleCalendarClient()

    # Pre-configure mock token with some test events
    mock_events = [
        {
            "id": "evt-existing-1",
            "summary": "Team Sync",
            "start": {"dateTime": "2026-09-01T09:30:00Z"},
            "end": {"dateTime": "2026-09-01T10:30:00Z"},
            "htmlLink": "https://google.com/calendar/event?eid=1",
        },
        {
            "id": "evt-existing-2",
            "summary": "Lunch Break",
            "start": {"dateTime": "2026-09-01T12:00:00Z"},
            "end": {"dateTime": "2026-09-01T13:00:00Z"},
            "htmlLink": "https://google.com/calendar/event?eid=2",
        },
    ]

    def mock_token_resolver(principal_id: str):
        return {"mock_mode": True, "mock_events": mock_events}

    return CalendarService(policy=policy, store=store, google_client=client, token_resolver=mock_token_resolver)


def test_list_events(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    events = service.list_events(caller, limit=10)
    assert len(events) == 2
    assert events[0].summary == "Team Sync"


def test_find_free_slots(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    slots = service.find_free_slots(caller, "2026-09-01", duration_minutes=30)
    assert len(slots) >= 3
    # 09:00 - 09:30 (30 mins before first event)
    assert slots[0].start_time == "2026-09-01T09:00:00Z"
    assert slots[0].end_time == "2026-09-01T09:30:00Z"
    assert slots[0].duration_minutes == 30


def test_create_and_confirm_draft(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    draft = service.create_draft_event(
        caller=caller,
        summary="Supplier Negotiation",
        start_time="2026-09-01T14:00:00Z",
        end_time="2026-09-01T15:00:00Z",
        location="Thao Dien",
    )
    assert draft.status == EventDraftStatus.DRAFT

    confirmed = service.confirm_event(caller=caller, draft_id=draft.draft_id)
    assert confirmed.summary == "Supplier Negotiation"
    assert "evt-" in confirmed.event_id

    # Verify state in store
    persisted_draft = service.store.get_draft(draft.draft_id)
    assert persisted_draft is not None
    assert persisted_draft.status == EventDraftStatus.COMMITTED
    assert persisted_draft.committed_event_id == confirmed.event_id
