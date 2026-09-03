from __future__ import annotations

import json
from typing import Any, Dict

from caller import CallerContextRegistry, DmOnlyError


def _error(code: str, message: str = "") -> str:
    err: Dict[str, Any] = {"code": code}
    if message:
        err["message"] = message
        lower = message.lower()
        if any(term in lower for term in ("missing_access_token", "invalid_grant", "401", "unauthorized")):
            err["hint"] = "Tài khoản Google/Gmail chưa được kết nối hoặc token đã hết hạn. Hãy dùng lệnh /connect_google để kết nối lại."
    return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

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

    try:
        user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
        if user_id:
            from tools.composio.auth import check_connection_status
            from tools.composio.mail_tools import composio_mail_search
            if check_connection_status(user_id, app="gmail"):
                res = composio_mail_search(user_id, query=params.get("query", "label:inbox"), max_results=params.get("limit", 10))
                if res.get("status") == "success":
                    return json.dumps({"ok": True, "result": res.get("data", {})}, ensure_ascii=False)
    except Exception:
        pass

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
