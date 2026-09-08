from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from caller import CallerContextRegistry, DmOnlyError

logger = logging.getLogger(__name__)


def _error(code: str, message: str = "") -> str:
    err: Dict[str, Any] = {"code": code}
    if message:
        err["message"] = message
        lower = message.lower()
        if any(
            term in lower
            for term in ("missing_access_token", "invalid_grant", "401", "unauthorized")
        ):
            err["hint"] = (
                "Tài khoản Google/Gmail chưa được kết nối hoặc token đã hết hạn. "
                "Hãy dùng lệnh /connect_google để kết nối lại."
            )
    return json.dumps({"ok": False, "error": err}, ensure_ascii=False)


def _resolve_caller(
    registry: CallerContextRegistry | Any,
    task_id: str,
    session_id: str,
) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_dm_tool(task_id=task_id, session_id=session_id)


def _resolve_principal(caller: Any) -> str:
    principal_id = str(getattr(caller, "principal_id", "")).strip()
    if not principal_id:
        raise LookupError("caller_principal_unavailable")
    return principal_id
def _target_user_id(caller: Any) -> str:
    user_id = getattr(caller, "user_id", None)
    if user_id is not None and str(user_id).strip():
        return str(user_id).strip()
    return _resolve_principal(caller)


def _caller_error(exc: Exception) -> str:
    if isinstance(exc, DmOnlyError):
        return _error("dm_required", str(exc))
    return _error("missing_caller_context", str(exc))

def _call_google(
    operation: str,
    principal_id: str,
    params: Dict[str, Any] | None = None,
) -> Any:
    try:
        from tools.composio.bridge import call_google
        return call_google(operation, principal_id, params)
    except (ImportError, ModuleNotFoundError):
        pass
    import importlib.util, os, sys
    from pathlib import Path
    for candidate in (
        Path(os.environ.get("HERMES_PROJECT_SRC", "")),
        Path("C:/Hermes-Business-Agent/src"),
        Path.cwd() / "src",
        Path.cwd(),
    ):
        target = candidate / "tools" / "composio" / "bridge.py"
        if target.is_file():
            src_dir = str(candidate.resolve())
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            try:
                import tools
                tools_dir = str((candidate / "tools").resolve())
                if hasattr(tools, "__path__") and tools_dir not in tools.__path__:
                    tools.__path__.insert(0, tools_dir)
            except Exception:
                pass
            spec = importlib.util.spec_from_file_location("tools.composio.bridge", str(target))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["tools.composio.bridge"] = mod
                spec.loader.exec_module(mod)
                return mod.call_google(operation, principal_id, params)
    raise RuntimeError("call_google bridge unavailable; run python src/setup_local.py --local")


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
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        principal_id = _resolve_principal(caller)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    if hasattr(client, "search") and (hasattr(client, "calls") or client.__class__.__name__ == "UnavailableConnectorClient"):
        return json.dumps(client.search(caller, params.get("query", ""), params.get("limit", 10)))

    query = str(params.get("query", "label:inbox"))
    account_email = params.get("account_email")
    if not account_email and query:
        match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", query)
        if match:
            account_email = match.group(0)
    try:
        if not _call_google(
            "check_connection_status",
            principal_id,
            {"app": "gmail"},
        ):
            return _error(
                "not_connected",
                "Tài khoản Gmail chưa được kết nối. Hãy dùng lệnh /connect_google để kết nối.",
            )
        result = _call_google(
            "composio_mail_search",
            principal_id,
            {
                "query": query,
                "max_results": params.get("limit", 10),
                "account_email": account_email,
            },
        )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "mail_search_failed").lower(),
                result.get("message", "Lỗi tìm kiếm email"),
            )
        return json.dumps(
            {
                "ok": True,
                "active_mailbox": result.get("active_mailbox"),
                "all_connected_mailboxes": result.get("all_connected_mailboxes"),
                "result": result.get("data", {}),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.warning("Composio email search failed for %s: %s", principal_id, exc)
        return _error("mail_search_failed", str(exc))


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
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        principal_id = _resolve_principal(caller)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    if hasattr(client, "get_thread") and (hasattr(client, "calls") or client.__class__.__name__ == "UnavailableConnectorClient"):
        return json.dumps(client.get_thread(caller, params.get("thread_id", "")))
    thread_id = str(params.get("thread_id", "")).strip()
    account_email = params.get("account_email")
    if not thread_id:
        return _error("thread_id_required")
    try:
        if not _call_google(
            "check_connection_status",
            principal_id,
            {"app": "gmail"},
        ):
            return _error(
                "not_connected",
                "Tài khoản Gmail chưa được kết nối. Hãy dùng lệnh /connect_google để kết nối.",
            )
        result = _call_google(
            "composio_mail_get_thread",
            principal_id,
            {"thread_id": thread_id, "account_email": account_email},
        )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "mail_get_thread_failed").lower(),
                result.get("message", "Lỗi khi đọc email"),
            )
        return json.dumps(
            {
                "ok": True,
                "active_mailbox": result.get("active_mailbox"),
                "all_connected_mailboxes": result.get("all_connected_mailboxes"),
                "result": result.get("data", {}),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.warning(
            "Composio get_thread failed for %s (thread %s): %s",
            principal_id,
            thread_id,
            exc,
        )
        return _error("mail_get_thread_failed", str(exc))


def handle_email_connection_status(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del params, kwargs
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        principal_id = _resolve_principal(caller)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    if hasattr(client, "connections") and (hasattr(client, "calls") or client.__class__.__name__ == "UnavailableConnectorClient"):
        return json.dumps(client.connections(caller))
    try:
        connections = _call_google("list_user_connections", principal_id)
        return json.dumps(
            {
                "ok": True,
                "result": {
                    "status": "connected" if connections else "disconnected",
                    "connections": [
                        {
                            "connection_id": item.get("id"),
                            "email": item.get("email", ""),
                            "status": item.get("status"),
                        }
                        for item in connections
                    ],
                },
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.warning("Failed querying email connections for %s: %s", principal_id, exc)
        return _error("connection_status_failed", str(exc))


def handle_email_send(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is not None and getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        principal_id = _resolve_principal(caller)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    recipient = str(params.get("recipient", "")).strip()
    subject = str(params.get("subject", "")).strip()
    body = str(params.get("body", "")).strip()
    account_email = params.get("account_email")

    if not recipient or not subject or not body:
        return _error("missing_required_fields", "recipient, subject, và body là bắt buộc.")

    try:
        res = _call_google(
            "composio_mail_send",
            principal_id,
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "account_email": account_email,
            },
        )
        if res.get("status") == "success":
            return json.dumps({
                "ok": True,
                "active_mailbox": res.get("active_mailbox"),
                "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                "result": res.get("data", {}),
            }, ensure_ascii=False)
        return _error("mail_send_failed", res.get("message", "Lỗi gửi email qua Composio"))
    except Exception as exc:
        return _error("mail_send_failed", str(exc))


def handle_email_create_draft(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is not None and getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        principal_id = _resolve_principal(caller)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    recipient = str(params.get("recipient", "")).strip()
    subject = str(params.get("subject", "")).strip()
    body = str(params.get("body", "")).strip()
    account_email = params.get("account_email")

    if not recipient or not subject or not body:
        return _error("missing_required_fields", "recipient, subject, và body là bắt buộc.")

    try:
        res = _call_google(
            "composio_mail_create_draft",
            principal_id,
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "account_email": account_email,
            },
        )
        if res.get("status") == "success":
            return json.dumps({
                "ok": True,
                "active_mailbox": res.get("active_mailbox"),
                "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                "result": res.get("data", {}),
            }, ensure_ascii=False)
        return _error("mail_draft_failed", res.get("message", "Lỗi tạo bản nháp qua Composio"))
    except Exception as exc:
        return _error("mail_draft_failed", str(exc))


def handle_email_reply(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is not None and getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        principal_id = _resolve_principal(caller)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    thread_id = str(params.get("thread_id", "")).strip()
    body = str(params.get("body", "")).strip()
    account_email = params.get("account_email")

    if not thread_id or not body:
        return _error("missing_required_fields", "thread_id và body là bắt buộc.")

    try:
        res = _call_google(
            "composio_mail_reply",
            principal_id,
            {
                "thread_id": thread_id,
                "body": body,
                "account_email": account_email,
            },
        )
        if res.get("status") == "success":
            return json.dumps({
                "ok": True,
                "active_mailbox": res.get("active_mailbox"),
                "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                "result": res.get("data", {}),
            }, ensure_ascii=False)
        return _error("mail_reply_failed", res.get("message", "Lỗi trả lời email qua Composio"))
    except Exception as exc:
        return _error("mail_reply_failed", str(exc))
