from __future__ import annotations

import json
from typing import Any, Dict

from caller import CallerContextRegistry, DmOnlyError


def _error(code: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code}})


def _resolve_caller(
    registry: CallerContextRegistry | Any,
    task_id: str,
    session_id: str,
) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_dm_tool(task_id=task_id, session_id=session_id)


def handle_email_search(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except DmOnlyError:
        return _error("dm_required")
    except LookupError:
        return _error("missing_caller_context")
    result = client.search(caller, params.get("query", ""), params.get("limit", 10))
    return json.dumps(result)


def handle_email_get_thread(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except DmOnlyError:
        return _error("dm_required")
    except LookupError:
        return _error("missing_caller_context")
    result = client.get_thread(caller, params.get("thread_id", ""))
    return json.dumps(result)


def handle_email_connection_status(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del params
    del kwargs
    if client is None:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except DmOnlyError:
        return _error("dm_required")
    except LookupError:
        return _error("missing_caller_context")
    return json.dumps(client.connections(caller))
