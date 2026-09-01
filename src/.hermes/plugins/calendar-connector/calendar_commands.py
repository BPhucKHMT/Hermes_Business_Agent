from __future__ import annotations

import json
from typing import Any

from calendar_caller import DM_REDIRECT_TEXT, DmOnlyError


def _caller(registry: Any) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_command()


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
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError:
        return _unavailable("missing_caller_context")

    response = client.start_oauth(caller)
    url = (
        response.get("result", {}).get("authorization_url")
        if response.get("ok")
        else None
    )
    if not url:
        return _unavailable(response.get("error", {}).get("code", "oauth_start_failed"))
    return f"Mở liên kết này để kết nối Google Calendar: {url}"


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
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError:
        return _unavailable("missing_caller_context")

    response = client.status(caller)
    return json.dumps(response, ensure_ascii=False)


def handle_disconnect_calendar(
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
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError:
        return _unavailable("missing_caller_context")

    result = client.disconnect(caller)
    return json.dumps(result, ensure_ascii=False)
