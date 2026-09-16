"""Composio Google Drive tools with caller-scoped capability enforcement."""

from __future__ import annotations

from typing import Any

from .auth import (
    check_connection_status,
    has_service_capability,
    select_service_account,
)
from .client import (
    execute_composio_tool,
    format_user_id,
    get_composio_client,
    get_response_data,
    get_response_error,
)

_NOT_CONNECTED = {
    "status": "error",
    "error_code": "NOT_CONNECTED",
    "message": "Google account not connected. Use /connect_google to connect.",
}


def _error(message: str, *, code: str = "PROVIDER_ERROR") -> dict[str, Any]:
    return {"status": "error", "error_code": code, "message": message}


def _run(
    principal_id: int | str,
    service: str,
    tool_slug: str,
    arguments: dict[str, Any],
    account_email: str | None,
) -> dict[str, Any]:
    """Shared execution path: capability gate -> account selection -> call."""
    try:
        selection = select_service_account(principal_id, service, account_email)
        session = get_composio_client().create(
            user_id=format_user_id(principal_id),
            multi_account={"enable": True},
        )
        result = execute_composio_tool(
            session,
            tool_slug,
            arguments=arguments,
            account=selection["account_id"],
        )
        error = get_response_error(result)
        if error:
            return _error(error)
        return {
            "status": "success",
            "account_email": selection["email"],
            "data": get_response_data(result),
        }
    except ValueError as exc:
        message = str(exc)
        if message.startswith("account_selection_required:"):
            return _error(message, code="ACCOUNT_SELECTION_REQUIRED")
        if message.startswith("service_not_ready:"):
            return _error(
                message,
                code="SERVICE_NOT_READY",
            )
        return _error(message, code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure
        return _error(f"Google Drive operation failed: {exc}")


def require_drive(principal_id: int | str) -> dict[str, Any] | None:
    """Return a NOT_CONNECTED error payload when Drive capability is absent."""
    if not check_connection_status(principal_id, app="googlesuper"):
        return dict(_NOT_CONNECTED)
    if not has_service_capability(principal_id, "drive"):
        return _error(
            "Account lacks Google Drive permission. "
            "Use /connect_google to grant additional access.",
            code="SCOPE_MISSING",
        )
    return None


def composio_drive_find(
    principal_id: int | str,
    query: str = "",
    page_size: int = 20,
    page_token: str | None = None,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Search Drive files the caller's account can access."""
    if not check_connection_status(principal_id, app="googlesuper"):
        return dict(_NOT_CONNECTED)
    if not has_service_capability(principal_id, "drive"):
        return _error(
            "Account lacks Google Drive permission. "
            "Use /connect_google to grant additional access.",
            code="SCOPE_MISSING",
        )
    arguments: dict[str, Any] = {"pageSize": max(1, min(int(page_size), 100))}
    if query:
        arguments["q"] = query
    if page_token:
        arguments["pageToken"] = page_token
    return _run(
        principal_id, "drive", "GOOGLEDRIVE_FIND_FILE", arguments, account_email
    )


def composio_drive_read_file(
    principal_id: int | str,
    file_id: str,
    mime_type: str | None = None,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Download file content through authenticated access."""
    gate = require_drive(principal_id)
    if gate:
        return gate
    arguments: dict[str, Any] = {"file_id": file_id}
    if mime_type:
        arguments["mime_type"] = mime_type
    return _run(
        principal_id, "drive", "GOOGLEDRIVE_DOWNLOAD_FILE", arguments, account_email
    )


def composio_drive_get_metadata(
    principal_id: int | str,
    file_id: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Read file metadata including permissions-related fields."""
    gate = require_drive(principal_id)
    if gate:
        return gate
    return _run(
        principal_id,
        "drive",
        "GOOGLEDRIVE_GET_FILE_METADATA",
        {"fileId": file_id},
        account_email,
    )
