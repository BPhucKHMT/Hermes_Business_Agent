"""Private JSON worker for the native Google connector bridge."""

from contextlib import redirect_stdout
from dataclasses import asdict, is_dataclass
from enum import Enum
from importlib import import_module
import json
import sys
from types import SimpleNamespace
from typing import Any

PROVIDER_OPERATIONS = {
    "handle_connect_google": "commands",
    "handle_connect_calendar": "commands",
    "handle_google_status": "commands",
    "handle_disconnect_google": "commands",
    "initiate_google_connection": "auth",
    "check_connection_status": "auth",
    "get_user_emails": "auth",
    "list_user_connections": "auth",
    "disconnect_user": "auth",
    "composio_mail_search": "mail_tools",
    "composio_mail_get_thread": "mail_tools",
    "composio_mail_send": "mail_tools",
    "composio_mail_create_draft": "mail_tools",
    "composio_mail_reply": "mail_tools",
    "composio_calendar_list_events": "calendar_tools",
    "composio_calendar_find_free_slots": "calendar_tools",
    "composio_calendar_get_event": "calendar_tools",
    "composio_calendar_create_event": "calendar_tools",
    "composio_calendar_patch_event": "calendar_tools",
    "composio_calendar_delete_event": "calendar_tools",
}
CALENDAR_OPERATIONS = frozenset({
    "create_draft_event", "confirm_event", "get_draft", "status",
    "list_events", "find_free_slots", "get_event",
})

def normalize_result(value: Any) -> Any:
    """Normalize domain return values to JSON-safe structures."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [normalize_result(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_result(item) for item in value]
    if isinstance(value, dict):
        return {k: normalize_result(v) for k, v in value.items()}
    return value


def calendar_operation(name, principal_id, params):
    from tools.calendar.cli import build_service

    service = build_service()
    if name == "get_draft":
        draft = service.store.get_draft(params["draft_id"])
        if draft is None:
            raise LookupError("draft_not_found")
        if draft.principal_id != principal_id:
            raise PermissionError("principal_not_authorized_for_draft")
        return draft
    caller = SimpleNamespace(principal_id=principal_id)
    return getattr(service, name)(caller=caller, **params)


def dispatch(request):
    if not isinstance(request, dict):
        raise ValueError("Google worker request must be an object")
    operation = request.get("operation")
    principal_id = request.get("principal_id")
    params = request.get("params", {})
    if not isinstance(principal_id, str) or not principal_id.strip():
        raise ValueError("Google operation requires a bound caller")
    if not isinstance(params, dict):
        raise ValueError("Google operation parameters must be an object")
    if {"caller", "principal_id", "telegram_user_id", "user_id"} & params.keys():
        raise ValueError("Google operation parameters cannot override caller")
    if operation in PROVIDER_OPERATIONS:
        module = import_module(f"tools.composio.{PROVIDER_OPERATIONS[operation]}")
        target_id = (
            principal_id.split(":")[-1]
            if principal_id.startswith("telegram:")
            else principal_id
        )
        raw = getattr(module, operation)(target_id, **params)
        return normalize_result(raw)
    if isinstance(operation, str) and operation.startswith("calendar."):
        name = operation.removeprefix("calendar.")
        if name in CALENDAR_OPERATIONS:
            raw = calendar_operation(name, principal_id, params)
            return normalize_result(raw)
    raise ValueError("Unsupported Google worker operation")


def json_value(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError("Unsupported Google worker result")


def main():
    try:
        request = json.load(sys.stdin)
        with redirect_stdout(sys.stderr):
            result = dispatch(request)
        response = {"ok": True, "result": result}
        status = 0
    except Exception as exc:
        response = {"ok": False, "error": {
            "type": type(exc).__name__, "message": str(exc),
        }}
        status = 1
    print(json.dumps(response, ensure_ascii=False, default=json_value))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
