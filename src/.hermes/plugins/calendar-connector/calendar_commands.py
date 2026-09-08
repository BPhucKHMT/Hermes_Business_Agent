from __future__ import annotations

import json
from typing import Any

from calendar_caller import DM_REDIRECT_TEXT, DmOnlyError


def _caller(registry: Any) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_command()


def _principal_id(caller: Any) -> str:
    principal_id = str(getattr(caller, "principal_id", "")).strip()
    if not principal_id:
        raise LookupError("caller_principal_unavailable")
    return principal_id


def _unavailable(code: str = "connector_unavailable") -> str:
    return f"Dịch vụ Calendar không khả dụng ({code})."


def handle_connect_calendar(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    del raw_args
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    from tools.composio.bridge import call_google

    return call_google("handle_connect_calendar", principal_id)


def handle_calendar_status_cmd(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    del raw_args
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    from tools.composio.bridge import call_google

    return call_google("handle_google_status", principal_id)


def handle_disconnect_calendar(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    from tools.composio.bridge import call_google

    return call_google(
        "handle_disconnect_google", principal_id, {"target": raw_args.strip()}
    )
