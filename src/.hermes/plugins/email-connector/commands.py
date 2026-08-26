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

    response = client.start_oauth(caller)
    url = response.get("result", {}).get("authorization_url") if response.get("ok") else None
    if not url:
        return _unavailable(response.get("error", {}).get("code", "oauth_start_failed"))
    return f"Mở liên kết này để kết nối Gmail chỉ-đọc: {url}"


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

    response = client.connections(caller)
    if not response.get("ok"):
        return _unavailable(response.get("error", {}).get("code", "status_failed"))
    return json.dumps(response["result"], ensure_ascii=False)


def handle_disconnect_gmail(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    connection_id = raw_args.strip()
    if not connection_id or any(char.isspace() for char in connection_id):
        return "Cần đúng một mã kết nối Gmail."
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError:
        return _unavailable("missing_caller_context")

    response = client.disconnect(caller, connection_id)
    if not response.get("ok"):
        return _unavailable(response.get("error", {}).get("code", "disconnect_failed"))
    result = response.get("result", {})
    if result.get("status") != "revoked":
        return _unavailable("disconnect_not_confirmed")
    return json.dumps(result, ensure_ascii=False)


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
        return _unavailable(response.get("error", {}).get("code", "grant_proposal_failed"))
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

    response = client.decide_grant(caller, parts[0], parts[1])
    if not response.get("ok"):
        return _unavailable(response.get("error", {}).get("code", "grant_decision_failed"))
    result = response.get("result", {})
    expected = "approved" if parts[1] == "approve" else "denied"
    if result.get("status") != expected:
        return _unavailable("grant_decision_not_confirmed")
    return json.dumps(result, ensure_ascii=False)
