from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from composio_client.types.tool_router.session_execute_response import (
    SessionExecuteResponse,
)

from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import load_calendar_policy
from tools.calendar.service import CalendarService
from tools.calendar.store import CalendarStore
from tools.composio import calendar_tools

ROOT = Path(__file__).resolve().parents[1]


def test_provider_rejection_is_not_calendar_success():
    rejected = SessionExecuteResponse(
        data={}, error="synthetic provider rejection", log_id="audit-log"
    )
    session = SimpleNamespace(execute=lambda **kwargs: rejected)
    client = SimpleNamespace(create=lambda **kwargs: session)
    with (
        patch.object(calendar_tools, "check_connection_status", return_value=True),
        patch.object(calendar_tools, "get_composio_client", return_value=client),
        patch.object(
            calendar_tools,
            "resolve_account_target",
            return_value=("account-a", "alpha@example.invalid"),
        ),
    ):
        result = calendar_tools.composio_calendar_create_event(
            "local:owner:audit", "Audit", "2030-01-01T09:00:00Z"
        )
    assert result["status"] == "error"


def test_different_accounts_do_not_share_calendar_draft(tmp_path):
    service = CalendarService(
        load_calendar_policy(ROOT / "src/config/calendar_policy.json"),
        CalendarStore(tmp_path / "calendar.sqlite3"),
        GoogleCalendarClient(),
        token_resolver=lambda principal: {"access_token": "synthetic"},
    )
    caller = SimpleNamespace(principal_id="local:owner:audit")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(minutes=30)
    first = service.create_draft_event(
        caller, "Audit", start.isoformat(), end.isoformat(),
        account_email="alpha@example.invalid",
    )
    second = service.create_draft_event(
        caller, "Audit", start.isoformat(), end.isoformat(),
        account_email="bravo@example.invalid",
    )
    assert first.draft_id != second.draft_id
    assert second.account_email == "bravo@example.invalid"
