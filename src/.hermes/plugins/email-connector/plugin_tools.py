from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any

from caller import CallerContextRegistry, DmOnlyError

logger = logging.getLogger(__name__)


def _error(code: str, message: str = "") -> str:
    err: dict[str, Any] = {"code": code}
    if message:
        err["message"] = message
        lower = message.lower()
        if any(
            term in lower
            for term in ("missing_access_token", "invalid_grant", "401", "unauthorized")
        ):
            err["hint"] = (
                "Google/Gmail account is not connected or the token has expired. "
                "Use /connect_google to reconnect."
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


def _candidate_src_dirs() -> list[Path]:
    candidates: list[Path] = []
    for key in ("HERMES_PROJECT_SRC", "HERMES_SRC_DIR"):
        val = os.environ.get(key)
        if val and (Path(val) / "tools").is_dir():
            candidates.append(Path(val))
    if len(Path(__file__).resolve().parents) >= 3:
        parent_candidate = Path(__file__).resolve().parents[2]
        if (parent_candidate / "tools").is_dir():
            candidates.append(parent_candidate)
    for env_file in (
        Path.home() / ".hermes" / ".env",
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
        if os.name == "nt"
        else None,
    ):
        if env_file and env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("HERMES_PROJECT_SRC="):
                        val = (
                            line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        )
                        if val and (Path(val) / "tools").is_dir():
                            candidates.append(Path(val))
            except OSError:
                pass
    for cwd_cand in (Path.cwd() / "src", Path.cwd()):
        if (cwd_cand / "tools").is_dir():
            candidates.append(cwd_cand)
    return candidates


_composio_bridge = None


def _load_composio_bridge():
    """Locate and load the repo composio bridge from candidate src dirs."""
    global _composio_bridge
    try:
        from tools.composio import bridge as _bridge  # noqa: PLC0415

        _composio_bridge = _bridge
        return _bridge
    except (ImportError, ModuleNotFoundError):
        pass
    for _cand in _candidate_src_dirs():
        _target = _cand / "tools" / "composio" / "bridge.py"
        if _target.is_file():
            _src_dir = str(_cand.resolve())
            if _src_dir not in sys.path:
                sys.path.insert(0, _src_dir)
            _spec = importlib.util.spec_from_file_location(
                "tools.composio.bridge", str(_target)
            )
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                sys.modules["tools.composio.bridge"] = _mod
                _spec.loader.exec_module(_mod)
                _composio_bridge = _mod
                return _mod
    raise RuntimeError(
        "call_google bridge unavailable; run python src/setup_local.py --local"
    )


_composio_bridge = _load_composio_bridge()


def _call_google(
    operation: str,
    principal_id: str,
    params: dict[str, Any] | None = None,
) -> Any:
    bridge = sys.modules.get("tools.composio.bridge") or _composio_bridge
    if bridge is None or not hasattr(bridge, "call_google"):
        raise RuntimeError(
            "call_google bridge unavailable; run python src/setup_local.py --local"
        )
    return bridge.call_google(operation, principal_id, params)


def handle_email_search(
    params: dict[str, Any],
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
    if hasattr(client, "search") and (
        hasattr(client, "calls")
        or client.__class__.__name__ == "UnavailableConnectorClient"
    ):
        return json.dumps(
            client.search(caller, params.get("query", ""), params.get("limit", 10))
        )

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
                "Gmail account not connected. Use /connect_google to connect.",
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
                result.get("message", "Email search failed"),
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
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        logger.warning("Composio email search failed for %s: %s", principal_id, exc)
        return _error("mail_search_failed", str(exc))


def handle_email_get_thread(
    params: dict[str, Any],
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
    if hasattr(client, "get_thread") and (
        hasattr(client, "calls")
        or client.__class__.__name__ == "UnavailableConnectorClient"
    ):
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
                "Gmail account not connected. Use /connect_google to connect.",
            )
        result = _call_google(
            "composio_mail_get_thread",
            principal_id,
            {"thread_id": thread_id, "account_email": account_email},
        )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "mail_get_thread_failed").lower(),
                result.get("message", "Failed to read email"),
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
    except Exception as exc:  # noqa: BLE001 -- gateway boundary maps provider failure to error payload
        logger.warning(
            "Composio get_thread failed for %s (thread %s): %s",
            principal_id,
            thread_id,
            exc,
        )
        return _error("mail_get_thread_failed", str(exc))


def handle_email_connection_status(
    params: dict[str, Any],
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
    if hasattr(client, "connections") and (
        hasattr(client, "calls")
        or client.__class__.__name__ == "UnavailableConnectorClient"
    ):
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
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        logger.warning(
            "Failed querying email connections for %s: %s", principal_id, exc
        )
        return _error("connection_status_failed", str(exc))


def handle_email_send(
    params: dict[str, Any],
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
        return _error(
            "missing_required_fields", "recipient, subject, and body are required."
        )

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
            return json.dumps(
                {
                    "ok": True,
                    "active_mailbox": res.get("active_mailbox"),
                    "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                    "result": res.get("data", {}),
                },
                ensure_ascii=False,
            )
        return _error(
            "mail_send_failed", res.get("message", "Failed to send email via Composio")
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("mail_send_failed", str(exc))


def handle_email_create_draft(
    params: dict[str, Any],
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
        return _error(
            "missing_required_fields", "recipient, subject, and body are required."
        )

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
            return json.dumps(
                {
                    "ok": True,
                    "active_mailbox": res.get("active_mailbox"),
                    "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                    "result": res.get("data", {}),
                },
                ensure_ascii=False,
            )
        return _error(
            "mail_draft_failed",
            res.get("message", "Failed to create draft via Composio"),
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("mail_draft_failed", str(exc))


def handle_email_reply(
    params: dict[str, Any],
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
        return _error("missing_required_fields", "thread_id and body are required.")

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
            return json.dumps(
                {
                    "ok": True,
                    "active_mailbox": res.get("active_mailbox"),
                    "all_connected_mailboxes": res.get("all_connected_mailboxes"),
                    "result": res.get("data", {}),
                },
                ensure_ascii=False,
            )
        return _error(
            "mail_reply_failed", res.get("message", "Failed to reply via Composio")
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("mail_reply_failed", str(exc))
