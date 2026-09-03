from __future__ import annotations

import json
import re
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

    # In legacy unit tests using FakeConnectorClient
    if hasattr(client, "calls"):
        return json.dumps(client.search(caller, params.get("query", ""), params.get("limit", 10)))

    query = params.get("query", "label:inbox")
    account_email = params.get("account_email")

    if not account_email and query:
        match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', query)
        if match:
            account_email = match.group(0)
    try:
        user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
        if user_id:
            from tools.composio.auth import check_connection_status
            from tools.composio.mail_tools import composio_mail_search
            if check_connection_status(user_id, app="gmail"):
                res = composio_mail_search(
                    user_id,
                    query=query,
                    max_results=params.get("limit", 10),
                    account_email=account_email,
                )
                if res.get("status") == "success":
                    return json.dumps({
                        "ok": True,
                        "active_mailbox": res.get("active_mailbox"),
                        "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                        "result": res.get("data", {}),
                    }, ensure_ascii=False)
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
    # In legacy unit tests using FakeConnectorClient
    if hasattr(client, "calls"):
        return json.dumps(client.get_thread(caller, params.get("thread_id", "")))

    thread_id = str(params.get("thread_id", "")).strip()
    account_email = params.get("account_email")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    if user_id:
        try:
            from tools.composio.auth import check_connection_status
            from tools.composio.mail_tools import composio_mail_get_thread
            if check_connection_status(user_id, app="gmail"):
                res = composio_mail_get_thread(user_id, thread_id=thread_id, account_email=account_email)
                if res.get("status") == "success":
                    return json.dumps({
                        "ok": True,
                        "active_mailbox": res.get("active_mailbox"),
                        "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                        "result": res.get("data", {}),
                    }, ensure_ascii=False)
        except Exception:
            pass

    result = client.get_thread(caller, thread_id)
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
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except DmOnlyError:
        return _error("dm_required")
    except LookupError:
        return _error("missing_caller_context")

    recipient = str(params.get("recipient", "")).strip()
    subject = str(params.get("subject", "")).strip()
    body = str(params.get("body", "")).strip()
    account_email = params.get("account_email")

    if not recipient or not subject or not body:
        return _error("missing_required_fields", "recipient, subject, và body là bắt buộc.")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    try:
        from tools.composio.mail_tools import composio_mail_send
        res = composio_mail_send(
            user_id,
            recipient=recipient,
            subject=subject,
            body=body,
            account_email=account_email,
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
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except DmOnlyError:
        return _error("dm_required")
    except LookupError:
        return _error("missing_caller_context")

    recipient = str(params.get("recipient", "")).strip()
    subject = str(params.get("subject", "")).strip()
    body = str(params.get("body", "")).strip()
    account_email = params.get("account_email")

    if not recipient or not subject or not body:
        return _error("missing_required_fields", "recipient, subject, và body là bắt buộc.")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    try:
        from tools.composio.mail_tools import composio_mail_create_draft
        res = composio_mail_create_draft(
            user_id,
            recipient=recipient,
            subject=subject,
            body=body,
            account_email=account_email,
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
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except DmOnlyError:
        return _error("dm_required")
    except LookupError:
        return _error("missing_caller_context")

    thread_id = str(params.get("thread_id", "")).strip()
    body = str(params.get("body", "")).strip()
    account_email = params.get("account_email")

    if not thread_id or not body:
        return _error("missing_required_fields", "thread_id và body là bắt buộc.")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    try:
        from tools.composio.mail_tools import composio_mail_reply
        res = composio_mail_reply(
            user_id,
            thread_id=thread_id,
            body=body,
            account_email=account_email,
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
