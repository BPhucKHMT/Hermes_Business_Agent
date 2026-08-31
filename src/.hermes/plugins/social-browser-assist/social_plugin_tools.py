from __future__ import annotations

import json
from typing import Any

from hermes_social_browser_assist.social_caller import CallerContextRegistry, DmOnlyError


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(code: str) -> str:
    return _json({"ok": False, "error": {"code": code}})


def _resolve(
    registry: CallerContextRegistry | Any, task_id: str, session_id: str
) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_dm_tool(task_id=task_id, session_id=session_id)


def _caller_error(exc: Exception) -> str:
    if isinstance(exc, DmOnlyError):
        return _error("dm_required")
    return _error("missing_caller_context")


def handle_prepare(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("social_browser_unavailable")
    try:
        caller = _resolve(registry, task_id, session_id)
        return _json(client.prepare(caller, params))
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except PermissionError as exc:
        return _error(str(exc))


def handle_status(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("social_browser_unavailable")
    try:
        caller = _resolve(registry, task_id, session_id)
        return _json(client.status(caller, str(params.get("run_id", ""))))
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except PermissionError as exc:
        return _error(str(exc))


def handle_verify(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("social_browser_unavailable")
    try:
        caller = _resolve(registry, task_id, session_id)
        return _json(client.verify(caller, str(params.get("run_id", ""))))
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except PermissionError as exc:
        return _error(str(exc))
