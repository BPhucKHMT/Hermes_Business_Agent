from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pytest

from tools.calendar.contracts import EventDraftStatus
from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import load_calendar_policy
from tools.calendar.service import CalendarService
from tools.calendar.store import CalendarStore

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def service(tmp_path: Path) -> CalendarService:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)
    store = CalendarStore(tmp_path / "test_calendar_boundary.sqlite3")
    client = GoogleCalendarClient()

    mock_events = [
        {
            "id": "evt-all-day",
            "summary": "Holiday",
            "start": {"date": "2026-09-01"},
            "end": {"date": "2026-09-02"},
            "htmlLink": "https://google.com/calendar/event?eid=holiday",
        }
    ]

    def mock_token_resolver(principal_id: str):
        return {"mock_mode": True, "mock_events": mock_events}

    return CalendarService(policy=policy, store=store, google_client=client, token_resolver=mock_token_resolver)


def test_empty_summary_raises(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    with pytest.raises(ValueError, match="summary_required"):
        service.create_draft_event(
            caller=caller,
            summary="   ",
            start_time="2026-09-01T14:00:00Z",
            end_time="2026-09-01T15:00:00Z",
        )


def test_end_before_start_raises(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    with pytest.raises(ValueError):
        service.create_draft_event(
            caller=caller,
            summary="Invalid Time Event",
            start_time="2026-09-01T15:00:00Z",
            end_time="2026-09-01T14:00:00Z",
        )


def test_all_day_event_ignored_in_busy_calculation(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    # All-day event shouldn't block the entire day working hours (09:00 - 18:00 ICT)
    slots = service.find_free_slots(caller, "2026-09-01", duration_minutes=60)
    assert len(slots) >= 1
    # Full day slot available (9 hours = 540 mins)
    assert slots[0].duration_minutes == 540


def test_limit_clamping(service: CalendarService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    # Requesting limit 9999 should not error and should clamp
    events = service.list_events(caller, limit=9999)
    assert isinstance(events, list)
