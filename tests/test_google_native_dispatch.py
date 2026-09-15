from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/.hermes/plugins/email-connector"))
sys.path.insert(0, str(ROOT / "src/.hermes/plugins/calendar-connector"))
from calendar_caller import (  # noqa: E402 -- imports follow plugin path bootstrap
    CallerContextRegistry as CalendarRegistry,
)
from calendar_commands import (  # noqa: E402 -- imports follow plugin path bootstrap
    handle_connect_calendar,
)
from calendar_guard import (  # noqa: E402 -- imports follow plugin path bootstrap
    CalendarToolsGuard,
)
from caller import (  # noqa: E402 -- imports follow plugin path bootstrap
    CallerContextRegistry as MailRegistry,
)
from commands import (  # noqa: E402 -- imports follow plugin path bootstrap
    handle_connect_gmail,
)
from plugin_tools import (  # noqa: E402 -- imports follow plugin path bootstrap
    handle_email_search,
)

OWNER_ID = "12345678-1234-4234-8234-123456789abc"


@pytest.fixture
def owner_file(tmp_path: Path) -> Path:
    path = tmp_path / "local-owner.json"
    path.write_text(
        json.dumps({"schema_version": 1, "owner_id": OWNER_ID}),
        encoding="utf-8",
    )
    return path


def test_native_connect_command_uses_bound_principal(owner_file, monkeypatch):
    received: list[str] = []

    def connect(principal_id: str) -> str:
        received.append(principal_id)
        return "https://accounts.google.invalid/connect"

    monkeypatch.setattr("tools.composio.commands.handle_connect_google", connect)
    result = handle_connect_gmail(
        client=object(),
        registry=MailRegistry(local_owner_path=owner_file),
    )

    assert "accounts.google.invalid" in result
    assert received == [f"local:owner:{OWNER_ID}"]


def test_native_calendar_command_uses_bound_principal(owner_file, monkeypatch):
    received: list[str] = []

    def connect(principal_id: str) -> str:
        received.append(principal_id)
        return "https://accounts.google.invalid/calendar"

    monkeypatch.setattr("tools.composio.commands.handle_connect_calendar", connect)
    result = handle_connect_calendar(
        client=object(),
        registry=CalendarRegistry(local_owner_path=owner_file),
    )

    assert "accounts.google.invalid" in result
    assert received == [f"local:owner:{OWNER_ID}"]


def test_native_mail_tool_uses_bound_principal(owner_file, monkeypatch):
    received: list[tuple[str, str]] = []

    def call(operation: str, principal_id: str, params=None):
        received.append((operation, principal_id))
        if operation == "check_connection_status":
            return True
        return {"status": "success", "data": {"messages": []}}

    monkeypatch.setattr("tools.composio.bridge.call_google", call)
    raw = handle_email_search(
        {"query": "label:inbox"},
        client=object(),
        registry=MailRegistry(local_owner_path=owner_file),
    )

    assert json.loads(raw)["ok"] is True
    assert received == [
        ("check_connection_status", f"local:owner:{OWNER_ID}"),
        ("composio_mail_search", f"local:owner:{OWNER_ID}"),
    ]


def test_captured_group_cannot_inherit_local_owner(owner_file):
    registry = MailRegistry(local_owner_path=owner_file)
    source = SimpleNamespace(
        platform="telegram",
        user_id="111",
        chat_id="-100",
        chat_type="group",
        profile="hermes-business",
        thread_id=None,
    )
    with pytest.raises(ValueError):
        registry.capture(SimpleNamespace(source=source))

    result = handle_email_search(
        {"query": "label:inbox"},
        client=object(),
        registry=registry,
    )
    assert json.loads(result)["error"]["code"] == "dm_required"


def test_calendar_confirm_approval_is_owner_and_content_scoped(owner_file):
    draft = SimpleNamespace(
        draft_id="draft-1",
        principal_id=f"local:owner:{OWNER_ID}",
        account_email="calendar@example.invalid",
        calendar_id="primary",
        summary="Review",
        description="Agenda",
        location="Room",
        start_time="2026-09-08T10:00:00Z",
        end_time="2026-09-08T10:30:00Z",
        attendees=("guest@example.invalid",),
        status="draft",
    )
    store = SimpleNamespace(
        get_draft=lambda draft_id: draft if draft_id == "draft-1" else None
    )
    client = SimpleNamespace(service=SimpleNamespace(store=store))
    guard = CalendarToolsGuard(
        registry=CalendarRegistry(local_owner_path=owner_file),
        client=client,
    )

    decision = guard.pre_tool_call(
        "calendar_confirm_event",
        {"draft_id": "draft-1"},
    )

    assert decision is not None
    assert decision["action"] == "approve"
    assert decision["rule_key"].startswith("calendar_confirm:")

    draft.principal_id = "local:owner:00000000-0000-4000-8000-000000000000"
    denied = guard.pre_tool_call("calendar_confirm_event", {"draft_id": "draft-1"})
    assert denied == {
        "action": "block",
        "message": "calendar draft belongs to another caller",
    }
