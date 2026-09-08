from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import load_calendar_policy
from tools.calendar.service import CalendarService
from tools.calendar.store import CalendarStore
from tools.composio import calendar_tools
from tools.composio.auth import resolve_account_target
from tools.composio.client import execute_composio_tool

ROOT = Path(__file__).resolve().parents[1]


class _TimeoutSession:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        raise TimeoutError("provider request timed out")


def test_composio_package_import_does_not_load_provider_sdk() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import tools.composio; assert 'composio' not in sys.modules",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr


def test_timeout_is_not_retried_as_slug_fallback() -> None:
    session = _TimeoutSession()
    with pytest.raises(TimeoutError):
        execute_composio_tool(
            session,
            "GOOGLESUPER_CREATE_EVENT",
            fallback_slug="GOOGLECALENDAR_CREATE_EVENT",
            arguments={},
        )
    assert session.calls == 1


def test_ambiguous_account_target_is_rejected_before_provider_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "tools.composio.auth.get_user_emails",
        lambda principal: {
            "account-a": "alpha@example.invalid",
            "account-b": "alpha-two@example.invalid",
        },
    )
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_account_target("local:owner:test", "alpha")


def test_out_of_range_account_index_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        "tools.composio.auth.get_user_emails",
        lambda principal: {"account-a": "alpha@example.invalid"},
    )
    with pytest.raises(ValueError, match="index_out_of_range"):
        resolve_account_target("telegram:default:test", "2")


def _service(tmp_path: Path, token_data: dict) -> CalendarService:
    policy = load_calendar_policy(ROOT / "src/config/calendar_policy.json")
    return CalendarService(
        policy,
        CalendarStore(tmp_path / "calendar.sqlite3"),
        GoogleCalendarClient(),
        token_resolver=lambda principal: token_data,
    )


def _draft(service: CalendarService, account: str):
    caller = SimpleNamespace(principal_id="local:owner:test")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(minutes=30)
    return caller, service.create_draft_event(
        caller,
        "Boundary event",
        start.isoformat(),
        end.isoformat(),
        account_email=account,
    )


def test_failed_readback_retains_provider_id_without_committing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "tools.composio.auth.get_user_emails",
        lambda principal: {"account-a": "alpha@example.invalid"},
    )
    service = _service(
        tmp_path,
        {"provider": "composio", "account_email": "alpha@example.invalid"},
    )
    caller, draft = _draft(service, "alpha@example.invalid")
    create_calls = 0
    readback_calls = 0

    def create(principal, **kwargs):
        nonlocal create_calls
        create_calls += 1
        return {
            "status": "success",
            "active_account": "alpha@example.invalid",
            "data": {
                "id": "provider-event-1",
                "start": {"dateTime": draft.start_time},
                "end": {"dateTime": draft.end_time},
            },
        }

    def get_event(principal, **kwargs):
        nonlocal readback_calls
        readback_calls += 1
        return {"status": "error", "message": "provider readback unavailable"}

    monkeypatch.setattr(calendar_tools, "composio_calendar_create_event", create)
    monkeypatch.setattr(calendar_tools, "composio_calendar_get_event", get_event)

    with pytest.raises(RuntimeError, match="readback"):
        service.confirm_event(caller, draft.draft_id)
    pending = service.store.get_draft(draft.draft_id)
    assert pending is not None
    assert pending.status.value == "draft"
    assert pending.committed_event_id == "provider-event-1"
    assert create_calls == 1
    assert readback_calls == 1


def test_replay_of_committed_draft_reads_existing_event(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "tools.composio.auth.get_user_emails",
        lambda principal: {"account-a": "alpha@example.invalid"},
    )
    service = _service(
        tmp_path,
        {"provider": "composio", "account_email": "alpha@example.invalid"},
    )
    caller, draft = _draft(service, "alpha@example.invalid")
    calls = {"create": 0, "get": 0}

    def create(principal, **kwargs):
        calls["create"] += 1
        return {
            "status": "success",
            "active_account": "alpha@example.invalid",
            "data": {"id": "provider-event-2"},
        }

    def get_event(principal, **kwargs):
        calls["get"] += 1
        return {
            "status": "success",
            "active_account": "alpha@example.invalid",
            "data": {
                "id": "provider-event-2",
                "calendarId": "primary",
                "summary": draft.summary,
                "start": {"dateTime": draft.start_time},
                "end": {"dateTime": draft.end_time},
            },
        }

    monkeypatch.setattr(calendar_tools, "composio_calendar_create_event", create)
    monkeypatch.setattr(calendar_tools, "composio_calendar_get_event", get_event)

    first = service.confirm_event(caller, draft.draft_id)
    second = service.confirm_event(caller, draft.draft_id)
    assert first.event_id == second.event_id == "provider-event-2"
    assert calls == {"create": 1, "get": 2}
