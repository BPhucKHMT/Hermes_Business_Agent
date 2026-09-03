from tools.calendar.contracts import CalendarEvent, EventDraft, EventDraftStatus
from tools.calendar.google_calendar import GoogleCalendarClient


def test_google_calendar_client_mock_events() -> None:
    client = GoogleCalendarClient()
    mock_token_data = {
        "mock_events": [
            {
                "id": "evt-001",
                "summary": "Morning Standup",
                "start": {"dateTime": "2026-09-01T09:00:00Z"},
                "end": {"dateTime": "2026-09-01T09:30:00Z"},
                "htmlLink": "https://google.com/calendar/event?eid=001",
            },
            {
                "id": "evt-002",
                "summary": "Lunch with Partner",
                "start": {"dateTime": "2026-09-01T12:00:00Z"},
                "end": {"dateTime": "2026-09-01T13:00:00Z"},
                "htmlLink": "https://google.com/calendar/event?eid=002",
            },
        ]
    }

    events = client.list_events(mock_token_data, calendar_id="primary")
    assert len(events) == 2
    assert events[0].event_id == "evt-001"
    assert events[0].summary == "Morning Standup"

    single = client.get_event(mock_token_data, "primary", "evt-002")
    assert single.event_id == "evt-002"
    assert single.summary == "Lunch with Partner"


def test_google_calendar_client_create_event_mock() -> None:
    client = GoogleCalendarClient()
    draft = EventDraft(
        draft_id="drf-111",
        idempotency_key="key-111",
        principal_id="telegram:default:123",
        calendar_id="primary",
        summary="Vendor Review",
        description="Review supplier contracts",
        location="HQ",
        start_time="2026-09-01T15:00:00Z",
        end_time="2026-09-01T16:00:00Z",
        attendees=("vendor@example.com",),
        created_at="2026-08-31T12:00:00Z",
    )

    created = client.create_event({"mock_mode": True}, "primary", draft)
    assert created.summary == "Vendor Review"
    assert created.status == "confirmed"
    assert "evt-" in created.event_id
    assert created.html_link.startswith("https://www.google.com/calendar/event")


def test_google_calendar_client_create_event_http() -> None:
    class FakeHttp:
        def __init__(self):
            self.posted = None

        def post(self, url, headers, body):
            self.posted = (url, headers, body)
            return {
                "id": "real-evt-999",
                "summary": "Project web",
                "start": {"dateTime": "2026-09-04T13:00:00+07:00"},
                "end": {"dateTime": "2026-09-04T15:00:00+07:00"},
                "htmlLink": "https://calendar.google.com/event?id=999",
            }

    fake_http = FakeHttp()
    client = GoogleCalendarClient(http_client=fake_http)
    draft = EventDraft(
        draft_id="drf-222",
        idempotency_key="key-222",
        principal_id="telegram:default:123",
        calendar_id="primary",
        summary="Project web",
        description="",
        location="THREE O’CLOCK – Phạm Ngọc Thạch",
        start_time="2026-09-04T13:00:00+07:00",
        end_time="2026-09-04T15:00:00+07:00",
        attendees=(),
        created_at="2026-09-03T12:00:00Z",
    )

    created = client.create_event({"access_token": "valid-token"}, "primary", draft)
    assert created.summary == "Project web"
    assert created.event_id == "real-evt-999"
    assert fake_http.posted is not None
    url, headers, body = fake_http.posted
    assert b"Project web" in body
