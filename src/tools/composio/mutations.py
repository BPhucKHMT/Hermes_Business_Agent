"""Write-capable Google tools with durable lifecycle and evidence binding.

Every mutation goes through ActionStore:
    begin(request_key) -> executing -> verified|failed|unknown
Duplicate request keys never re-execute. Send/reply evidence is the provider's
returned message/thread ID recorded with the operation; read-back verification
is layered in by callers with service access.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .action_store import ActionStore
from .actions import evaluate_direct_send
from .drive_tools import _error, _run
from .mail_tools import composio_mail_send

_STORE: ActionStore | None = None


def get_store() -> ActionStore:
    global _STORE
    if _STORE is None:
        _STORE = ActionStore()
    return _STORE


def _request_key(
    principal_id: str, service: str, action: str, params: dict[str, Any]
) -> str:
    blob = json.dumps(
        {
            "principal": principal_id,
            "service": service,
            "action": action,
            "params": params,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _begin_write(
    principal_id: str,
    service: str,
    action: str,
    params: dict[str, Any],
    workspace: str = "",
) -> dict[str, Any]:
    """Begin a tracked write. Raises DuplicateRequestError on replays."""
    store = get_store()
    key = _request_key(principal_id, service, action, params)
    record = store.begin(
        request_key=key,
        principal_id=principal_id,
        service=service,
        action=action,
        params=params,
        workspace=workspace,
    )
    return record  # type: ignore[return-value]


def _execute_write(
    principal_id: str,
    service: str,
    action: str,
    tool_slug: str,
    arguments: dict[str, Any],
    account_email: str | None,
    workspace: str = "",
) -> dict[str, Any]:
    """Run one tracked mutation with full lifecycle handling."""
    try:
        record = _begin_write(principal_id, service, action, arguments, workspace)
    except Exception as exc:  # noqa: BLE001 -- store failure fails closed
        return _error(
            f"Failed to record the operation: {exc}", code="ACTION_STORE_ERROR"
        )
    store = get_store()
    if record["state"] not in ("pending",):
        return _error(
            f"This request was already processed (state: {record['state']}).",
            code="DUPLICATE_REQUEST",
        )
    store.mark_executing(record["operation_id"])
    result = _run(principal_id, service, tool_slug, arguments, account_email)
    if result.get("status") == "success":
        store.mark_verified(record["operation_id"], {"provider": result.get("data")})
        return {
            "status": "success",
            "operation_id": record["operation_id"],
            "account_email": result.get("account_email"),
            "data": result.get("data"),
        }
    if result.get("error_code") in (
        "PROVIDER_ERROR",
        "SERVICE_NOT_READY",
        "SCOPE_MISSING",
        "NOT_CONNECTED",
        "INVALID_ACCOUNT_TARGET",
    ):
        store.mark_failed(
            record["operation_id"], result.get("error_code", "PROVIDER_ERROR")
        )
        return result
    # Ambiguous outcome: the request may or may not have committed.
    store.mark_unknown(
        record["operation_id"], str(result.get("message", "unknown"))[:200]
    )
    return {
        "status": "error",
        "error_code": "UNKNOWN_OUTCOME",
        "message": (
            "The final outcome is unknown. Verify in Google "
            "before retrying; do not blindly resend or re-edit."
        ),
        "operation_id": record["operation_id"],
    }


# ---------------------------------------------------------------------------
# Gmail direct send with request-scoped approval (D028/REQ-AUTONOMY-03)
# ---------------------------------------------------------------------------


def composio_email_send_direct(
    principal_id: int | str,
    *,
    request_text: str,
    recipient: str,
    subject: str,
    body: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Send an email when the request text explicitly authorizes send-now.

    Returns decision error payloads when intent is draft/unclear or material
    inputs are missing. Executes exactly once per identical request.
    """
    decision = evaluate_direct_send(
        request_text=request_text,
        recipient=recipient,
        subject=subject,
        body=body,
    )
    if decision.intent == "draft":
        return _error(
            "Request is a draft-only request; not sent. Use /email_create_draft.",
            code="DRAFT_ONLY",
        )
    if decision.intent != "send_now":
        return _error(
            "Unclear whether to send now or just draft. Ask the user.",
            code="INTENT_UNCLEAR",
        )
    if decision.missing:
        return _error(
            "Missing information: " + ", ".join(decision.missing),
            code="MISSING_FIELDS",
        )
    params = {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "account_email": account_email,
    }
    try:
        record = _begin_write(str(principal_id), "gmail", "send", params, workspace)
    except Exception as exc:  # noqa: BLE001 -- store failure fails closed
        return _error(
            f"Failed to record the operation: {exc}", code="ACTION_STORE_ERROR"
        )
    store = get_store()
    if record["state"] != "pending":
        return _error(
            f"This request was already processed (state: {record['state']}).",
            code="DUPLICATE_REQUEST",
        )
    store.mark_executing(record["operation_id"])
    result = composio_mail_send(
        str(principal_id),
        recipient=recipient,
        subject=subject,
        body=body,
        account_email=account_email,
    )
    data = result.get("data") or {}
    message_id = data.get("message_id") or data.get("id")
    if result.get("status") == "success" and message_id:
        store.mark_verified(
            record["operation_id"],
            {"message_id": message_id, "provider": data},
        )
        return {
            "status": "success",
            "operation_id": record["operation_id"],
            "active_mailbox": result.get("active_mailbox"),
            "message_id": message_id,
            "data": data,
        }
    if result.get("status") == "success":
        store.mark_unknown(record["operation_id"], "sent without message id")
        return {
            "status": "error",
            "error_code": "UNKNOWN_OUTCOME",
            "message": "Send may have succeeded but no message ID was returned. Check the Sent folder.",
            "operation_id": record["operation_id"],
        }
    if result.get("error_code") in ("PROVIDER_ERROR", "INVALID_ACCOUNT_TARGET"):
        store.mark_failed(
            record["operation_id"], result.get("error_code", "PROVIDER_ERROR")
        )
        return result
    store.mark_unknown(
        record["operation_id"], str(result.get("message", "unknown"))[:200]
    )
    return {
        "status": "error",
        "error_code": "UNKNOWN_OUTCOME",
        "message": "Send outcome unknown. Check the Sent folder before retrying.",
        "operation_id": record["operation_id"],
    }


# ---------------------------------------------------------------------------
# Drive mutations
# ---------------------------------------------------------------------------


def composio_drive_upload(
    principal_id: int | str,
    *,
    file_b64: str,
    name: str,
    folder_id: str | None = None,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Upload a file (base64 content) into Drive."""
    arguments: dict[str, Any] = {
        "file_to_upload": {"name": name, "content": file_b64},
    }
    if folder_id:
        arguments["folder_to_upload_to"] = folder_id
    return _execute_write(
        principal_id,
        "drive",
        "upload",
        "GOOGLEDRIVE_UPLOAD_FILE",
        arguments,
        account_email,
        workspace,
    )


def composio_drive_create_folder(
    principal_id: int | str,
    *,
    folder_name: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Create a Drive folder."""
    return _execute_write(
        principal_id,
        "drive",
        "create_folder",
        "GOOGLEDRIVE_CREATE_FOLDER",
        {"folder_name": folder_name},
        account_email,
        workspace,
    )


def composio_drive_move(
    principal_id: int | str,
    *,
    file_id: str,
    add_parents: str | None = None,
    remove_parents: str | None = None,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Move a file between folders."""
    arguments: dict[str, Any] = {"file_id": file_id}
    if add_parents:
        arguments["add_parents"] = add_parents
    if remove_parents:
        arguments["remove_parents"] = remove_parents
    return _execute_write(
        principal_id,
        "drive",
        "move",
        "GOOGLEDRIVE_MOVE_FILE",
        arguments,
        account_email,
        workspace,
    )


def composio_drive_copy(
    principal_id: int | str,
    *,
    file_id: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Copy a Drive file."""
    return _execute_write(
        principal_id,
        "drive",
        "copy",
        "GOOGLEDRIVE_COPY_FILE",
        {"file_id": file_id},
        account_email,
        workspace,
    )


def composio_drive_share(
    principal_id: int | str,
    *,
    file_id: str,
    role: str,
    grantee_type: str,
    email_address: str | None = None,
    domain: str | None = None,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Grant or adjust sharing permission on a Drive file."""
    arguments: dict[str, Any] = {"file_id": file_id, "role": role, "type": grantee_type}
    if email_address:
        arguments["email_address"] = email_address
    if domain:
        arguments["domain"] = domain
    return _execute_write(
        principal_id,
        "drive",
        "share",
        "GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE",
        arguments,
        account_email,
        workspace,
    )


def composio_drive_revoke_permission(
    principal_id: int | str,
    *,
    file_id: str,
    permission_id: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Revoke one permission on a Drive file."""
    return _execute_write(
        principal_id,
        "drive",
        "revoke_permission",
        "GOOGLEDRIVE_DELETE_PERMISSION",
        {"file_id": file_id, "permission_id": permission_id},
        account_email,
        workspace,
    )


def composio_drive_trash(
    principal_id: int | str,
    *,
    file_id: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Move a Drive file/folder to trash (reversible; never permanent delete)."""
    return _execute_write(
        principal_id,
        "drive",
        "trash",
        "GOOGLEDRIVE_GOOGLE_DRIVE_DELETE_FOLDER_OR_FILE_ACTION",
        {"fileId": file_id},
        account_email,
        workspace,
    )


def composio_drive_restore(
    principal_id: int | str,
    *,
    file_id: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Restore a Drive item from trash."""
    return _execute_write(
        principal_id,
        "drive",
        "restore",
        "GOOGLEDRIVE_UNTRASH_FILE",
        {"file_id": file_id},
        account_email,
        workspace,
    )


# ---------------------------------------------------------------------------
# Docs mutations
# ---------------------------------------------------------------------------


def composio_docs_create(
    principal_id: int | str,
    *,
    title: str,
    text: str = "",
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Create a Google Docs document."""
    return _execute_write(
        principal_id,
        "docs",
        "create",
        "GOOGLEDOCS_CREATE_DOCUMENT",
        {"title": title, "text": text},
        account_email,
        workspace,
    )


def composio_docs_insert_text(
    principal_id: int | str,
    *,
    document_id: str,
    text: str,
    insertion_index: int,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Insert text at a specific index in a Docs document."""
    return _execute_write(
        principal_id,
        "docs",
        "insert_text",
        "GOOGLEDOCS_INSERT_TEXT_ACTION",
        {
            "document_id": document_id,
            "text_to_insert": text,
            "insertion_index": insertion_index,
        },
        account_email,
        workspace,
    )


def composio_docs_replace_all(
    principal_id: int | str,
    *,
    document_id: str,
    find_text: str,
    replace_text: str,
    match_case: bool = True,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Replace all occurrences of text in a Docs document."""
    return _execute_write(
        principal_id,
        "docs",
        "replace_all",
        "GOOGLEDOCS_REPLACE_ALL_TEXT",
        {
            "document_id": document_id,
            "find_text": find_text,
            "replace_text": replace_text,
            "match_case": match_case,
        },
        account_email,
        workspace,
    )


# ---------------------------------------------------------------------------
# Sheets mutations
# ---------------------------------------------------------------------------


def composio_sheets_update_values(
    principal_id: int | str,
    *,
    spreadsheet_id: str,
    sheet_name: str,
    values: list[list[Any]],
    first_cell: str | None = None,
    value_input_option: str = "USER_ENTERED",
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Write values/formulas into a spreadsheet range."""
    arguments: dict[str, Any] = {
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": sheet_name,
        "values": values,
        "valueInputOption": value_input_option,
    }
    if first_cell:
        arguments["first_cell_location"] = first_cell
    return _execute_write(
        principal_id,
        "sheets",
        "update_values",
        "GOOGLESHEETS_BATCH_UPDATE",
        arguments,
        account_email,
        workspace,
    )


def composio_sheets_append(
    principal_id: int | str,
    *,
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Append rows to a spreadsheet table."""
    return _execute_write(
        principal_id,
        "sheets",
        "append",
        "GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND",
        {
            "spreadsheetId": spreadsheet_id,
            "range": range_name,
            "values": values,
            "valueInputOption": "USER_ENTERED",
        },
        account_email,
        workspace,
    )


def composio_sheets_clear(
    principal_id: int | str,
    *,
    spreadsheet_id: str,
    range_name: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Clear values in a range."""
    return _execute_write(
        principal_id,
        "sheets",
        "clear",
        "GOOGLESHEETS_CLEAR_VALUES",
        {"spreadsheet_id": spreadsheet_id, "range": range_name},
        account_email,
        workspace,
    )


def composio_sheets_add_sheet(
    principal_id: int | str,
    *,
    spreadsheet_id: str,
    title: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Add a new tab to a spreadsheet."""
    return _execute_write(
        principal_id,
        "sheets",
        "add_sheet",
        "GOOGLESHEETS_ADD_SHEET",
        {"spreadsheetId": spreadsheet_id, "title": title},
        account_email,
        workspace,
    )


# ---------------------------------------------------------------------------
# Slides mutations
# ---------------------------------------------------------------------------


def composio_slides_create(
    principal_id: int | str,
    *,
    title: str,
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Create a Google Slides presentation."""
    return _execute_write(
        principal_id,
        "slides",
        "create",
        "GOOGLESLIDES_PRESENTATIONS_CREATE",
        {"title": title},
        account_email,
        workspace,
    )


def composio_slides_batch_update(
    principal_id: int | str,
    *,
    presentation_id: str,
    requests: list[dict[str, Any]],
    account_email: str | None = None,
    workspace: str = "",
) -> dict[str, Any]:
    """Apply batch structural updates to a presentation."""
    return _execute_write(
        principal_id,
        "slides",
        "batch_update",
        "GOOGLESLIDES_PRESENTATIONS_BATCH_UPDATE",
        {"presentationId": presentation_id, "requests": requests},
        account_email,
        workspace,
    )
