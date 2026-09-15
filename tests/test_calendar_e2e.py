"""End-to-end integration test for Google Calendar draft creation and confirmation.

Tests the full pipeline without high-level mocks, intercepting only at the
HTTP urllib transport boundary to guarantee that all internal payload
serialization (including body_bytes) executes with 100% fidelity.
"""

import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/.hermes/plugins/calendar-connector"))
# Plugin imports
from calendar_client import (  # noqa: E402 -- imports follow plugin path bootstrap
    CalendarConnectorClient,
)
from calendar_plugin_tools import (  # noqa: E402 -- imports follow plugin path bootstrap
    handle_calendar_confirm_event,
    handle_calendar_create_draft_event,
)

from tools.calendar.contracts import (  # noqa: E402 -- imports follow source path bootstrap
    EventDraftStatus,
)
from tools.calendar.google_calendar import (  # noqa: E402 -- source path bootstrap above
    GoogleCalendarClient,
)
from tools.calendar.policy import (  # noqa: E402 -- source path bootstrap above
    load_calendar_policy,
)
from tools.calendar.service import (  # noqa: E402 -- source path bootstrap above
    CalendarService,
)
from tools.calendar.store import (  # noqa: E402 -- source path bootstrap above
    CalendarStore,
)


class MockHTTPResponse(io.BytesIO):
    def __init__(self, data: bytes, status: int = 200):
        super().__init__(data)
        self.status = status
        self.length = len(data)

    def read(self, *args, **kwargs):
        return super().read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeCaller:
    def __init__(self, principal_id: str = "telegram:default:7275339077"):
        self.principal_id = principal_id
        self.user_id = "7275339077"
        self.chat_id = "7275339077"
        self.thread_id = None
        self.chat_type = "dm"


class FakeRegistry:
    def __init__(self, caller: FakeCaller):
        self.caller = caller

    def resolve_dm_tool(self, task_id: str, session_id: str):
        return self.caller


def test_calendar_e2e_draft_and_confirm_flow():
    """Execute end-to-end flow matching the user's exact draft event."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "calendar.sqlite3"
        policy_path = (
            Path(__file__).resolve().parents[1] / "src/config/calendar_policy.json"
        )
        policy = load_calendar_policy(policy_path)
        store = CalendarStore(db_path)

        # Real GoogleCalendarClient with NO fake http_client
        google_client = GoogleCalendarClient()

        # Token resolver returning a live-like OAuth token (mock_mode is False!)
        def fake_token_resolver(principal_id: str) -> dict[str, Any]:
            return {
                "access_token": "ya29.a0ARrdaM_test_live_token",
                "refresh_token": "1//04_test_refresh_token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            }

        service = CalendarService(
            policy=policy,
            store=store,
            google_client=google_client,
            token_resolver=fake_token_resolver,
        )

        client = CalendarConnectorClient(service_factory=lambda: service)
        caller = FakeCaller()
        registry = FakeRegistry(caller)

        # 1. Step 1: Create Draft Event (Exact user prompt details)
        draft_params = {
            "summary": "Project web",
            "start_time": "2026-09-04T13:00:00+07:00",
            "end_time": "2026-09-04T15:00:00+07:00",
            "location": "THREE O’CLOCK – Phạm Ngọc Thạch",
            "description": "46–48 Phạm Ngọc Thạch, Phường Xuân Hòa, TP. Hồ Chí Minh",
            "attendees": [],
            "calendar_id": "primary",
        }

        draft_res_raw = handle_calendar_create_draft_event(
            params=draft_params,
            client=client,
            registry=registry,
            task_id="task-001",
            session_id="session-001",
        )
        draft_res = json.loads(draft_res_raw)
        assert draft_res["ok"] is True
        draft_id = draft_res["result"]["draft"]["draft_id"]

        # 2. Step 2: Confirm Event
        # Intercept ONLY at the raw urllib.request.urlopen transport layer
        captured_requests = []

        def mock_urlopen(req, timeout=15):
            captured_requests.append(req)
            # Response matching Google Calendar v3 API events.insert
            response_payload = {
                "id": "google_event_id_xyz789",
                "status": "confirmed",
                "htmlLink": "https://www.google.com/calendar/event?eid=google_event_id_xyz789",
                "summary": "Project web",
                "location": "THREE O’CLOCK – Phạm Ngọc Thạch",
                "description": "46–48 Phạm Ngọc Thạch, Phường Xuân Hòa, TP. Hồ Chí Minh",
                "start": {"dateTime": "2026-09-04T13:00:00+07:00"},
                "end": {"dateTime": "2026-09-04T15:00:00+07:00"},
            }
            return MockHTTPResponse(json.dumps(response_payload).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            confirm_res_raw = handle_calendar_confirm_event(
                params={"draft_id": draft_id},
                client=client,
                registry=registry,
                task_id="task-001",
                session_id="session-001",
            )

            confirm_res = json.loads(confirm_res_raw)
            assert confirm_res["ok"] is True
        event_data = confirm_res["result"]["event"]
        assert event_data["event_id"] == "google_event_id_xyz789"
        assert event_data["summary"] == "Project web"

        # 3. Step 3: Verify the raw HTTP request details that were sent
        assert len(captured_requests) == 2
        assert captured_requests[1].get_method() == "GET"
        assert (
            "calendars/primary/events/google_event_id_xyz789"
            in captured_requests[1].get_full_url()
        )
        req = captured_requests[0]
        assert req.get_method() == "POST"
        assert "calendars/primary/events" in req.get_full_url()
        assert req.get_header("Authorization") == "Bearer ya29.a0ARrdaM_test_live_token"
        assert req.get_header("Content-type") == "application/json"

        # Verify body_bytes payload was serialized without error
        sent_body = json.loads(req.data.decode("utf-8"))
        assert sent_body["summary"] == "Project web"
        assert sent_body["location"] == "THREE O’CLOCK – Phạm Ngọc Thạch"
        assert (
            sent_body["description"]
            == "46–48 Phạm Ngọc Thạch, Phường Xuân Hòa, TP. Hồ Chí Minh"
        )
        assert sent_body["start"]["dateTime"] == "2026-09-04T13:00:00+07:00"
        assert sent_body["end"]["dateTime"] == "2026-09-04T15:00:00+07:00"

        # 4. Step 4: Verify store state transitioned to COMMITTED
        persisted_draft = store.get_draft(draft_id)
        assert persisted_draft.status == EventDraftStatus.COMMITTED
        assert persisted_draft.committed_event_id == "google_event_id_xyz789"
