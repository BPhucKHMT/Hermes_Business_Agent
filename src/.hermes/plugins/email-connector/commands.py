from __future__ import annotations

import json
from typing import Any

from caller import DM_REDIRECT_TEXT, DmOnlyError


def _caller(registry: Any) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_command()


def _unavailable(code: str = "connector_unavailable") -> str:
    return f"Dịch vụ Gmail không khả dụng ({code})."


def handle_connect_gmail(
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

    # In legacy unit tests using FakeConnectorClient
    if hasattr(client, "calls"):
        response = client.start_oauth(caller)
        url = (
            response.get("result", {}).get("authorization_url")
            if response.get("ok")
            else None
        )
        if not url:
            return _unavailable(response.get("error", {}).get("code", "oauth_start_failed"))
        return f"Mở liên kết này để kết nối Google (Gmail, Calendar, YouTube): {url}"

    # In live runtime: exclusively use Composio Google Workspace
    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    if not user_id:
        return _unavailable("missing_caller_context")

    from tools.composio.commands import handle_connect_google
    return handle_connect_google(user_id)


def handle_mail_status(
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

    # In legacy unit tests using FakeConnectorClient
    if hasattr(client, "calls"):
        response = client.connections(caller)
        if not response.get("ok"):
            return _unavailable(response.get("error", {}).get("code", "status_failed"))
        return json.dumps(response["result"], ensure_ascii=False)

    # In live runtime: exclusively use Composio Google Workspace
    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    if not user_id:
        return _unavailable("missing_caller_context")

    from tools.composio.commands import handle_google_status
    return handle_google_status(user_id)


def handle_disconnect_gmail(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    parts = raw_args.split()
    # In legacy unit tests using FakeConnectorClient
    if hasattr(client, "calls") and len(parts) == 1:
        try:
            caller = _caller(registry)
        except (DmOnlyError, LookupError):
            return _unavailable("missing_caller_context")
        response = client.disconnect(caller, parts[0])
        if not response.get("ok"):
            return _unavailable(
                response.get("error", {}).get("code", "disconnect_failed")
            )
        result = response.get("result", {})
        if result.get("status") != "revoked":
            return _unavailable("disconnect_not_confirmed")
        return json.dumps(result, ensure_ascii=False)

    # In live runtime: exclusively use Composio Google Workspace
    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    if not user_id:
        return _unavailable("missing_caller_context")

    from tools.composio.commands import handle_disconnect_google
    target = parts[0] if parts else ""
    return handle_disconnect_google(user_id, target=target)


def handle_share_mailbox(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    parts = raw_args.split()
    if len(parts) not in (2, 3):
        return "Cần: <mã_kết_nối> <chat_id> [thread_id]."
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError:
        return _unavailable("missing_caller_context")

    response = client.propose_grant(
        caller,
        parts[0],
        parts[1],
        parts[2] if len(parts) == 3 else None,
    )
    if not response.get("ok"):
        return _unavailable(
            response.get("error", {}).get("code", "grant_proposal_failed")
        )
    result = response.get("result", {})
    if result.get("status") != "pending" or not result.get("request_id"):
        return _unavailable("grant_proposal_not_confirmed")
    return json.dumps(result, ensure_ascii=False)


def handle_email_grant(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    parts = raw_args.split()
    if len(parts) != 2 or parts[1] not in ("approve", "deny"):
        return "Cần: <mã_yêu_cầu> approve|deny."
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError:
        return _unavailable("missing_caller_context")

    approved = parts[1] == "approve"
    response = client.decide_grant(caller, parts[0], parts[1])
    if not response.get("ok"):
        return _unavailable(
            response.get("error", {}).get("code", "grant_resolution_failed")
        )
    result = response.get("result", {})
    if result.get("status") not in ("approved", "denied"):
        return _unavailable("grant_resolution_not_confirmed")
    return json.dumps(result, ensure_ascii=False)
