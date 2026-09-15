"""Composio Gmail tools with strict caller/account isolation."""

from __future__ import annotations

from typing import Any

from .auth import (
    _toolkit_slug,
    check_connection_status,
    get_user_emails,
    resolve_account_target,
)
from .client import (
    execute_composio_tool,
    format_user_id,
    get_composio_client,
    get_response_data,
)

_NOT_CONNECTED = {
    "status": "error",
    "error_code": "NOT_CONNECTED",
    "message": "Bạn chưa kết nối tài khoản Gmail. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
}


def _context(
    principal_id: int | str, account_email: str | None
) -> tuple[Any, str | None, str | None, list[str]]:
    """Resolve an explicit target before opening a provider session."""
    account_id, resolved_email = resolve_account_target(principal_id, account_email)
    client = get_composio_client()
    session = client.create(
        user_id=format_user_id(principal_id),
        multi_account={"enable": True},
    )
    all_emails = list(dict.fromkeys(get_user_emails(principal_id).values()))
    return session, account_id, resolved_email, all_emails


def _execute(
    session: Any,
    tool_slug: str,
    arguments: dict[str, Any],
    account_id: str | None,
) -> Any:
    kwargs: dict[str, Any] = {"arguments": arguments}
    if account_id:
        kwargs["account"] = account_id
        if tool_slug.startswith("GMAIL_"):
            selected = get_composio_client().connected_accounts.get(account_id)
            toolkit = _toolkit_slug(selected).lower()
            if toolkit not in ("gmail", "googlesuper"):
                raise ValueError("Selected account does not support Gmail operations")
            tool_slug = f"{toolkit.upper()}_{tool_slug.removeprefix('GMAIL_')}"
    return execute_composio_tool(session, tool_slug, **kwargs)


def _error(message: str, *, code: str = "PROVIDER_ERROR") -> dict[str, Any]:
    return {"status": "error", "error_code": code, "message": message}


def _mailbox_context(
    principal_id: int | str, account_email: str | None
) -> tuple[Any, str | None, str | None, list[str]]:
    return _context(principal_id, account_email)


def composio_mail_search(
    telegram_user_id: int | str,
    query: str = "label:inbox",
    max_results: int = 5,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Search Gmail messages for the caller's selected mailbox."""
    try:
        if not check_connection_status(telegram_user_id, app="gmail"):
            return dict(_NOT_CONNECTED)
        session, account_id, resolved_email, all_emails = _mailbox_context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GMAIL_FETCH_EMAILS",
            {"query": query, "max_results": max_results},
            account_id,
        )
        return {
            "status": "success",
            "active_mailbox": resolved_email or "default",
            "all_connected_mailboxes": all_emails,
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi tìm kiếm email: {exc}")


def composio_mail_get_thread(
    telegram_user_id: int | str,
    thread_id: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Retrieve a Gmail thread from the caller's selected mailbox."""
    try:
        if not check_connection_status(telegram_user_id, app="gmail"):
            return dict(_NOT_CONNECTED)
        session, account_id, resolved_email, all_emails = _mailbox_context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
            {"thread_id": thread_id},
            account_id,
        )
        return {
            "status": "success",
            "active_mailbox": resolved_email or "default",
            "all_connected_mailboxes": all_emails,
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi đọc chuỗi email: {exc}")


def composio_mail_send(
    telegram_user_id: int | str,
    recipient: str,
    subject: str,
    body: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Send a Gmail message from the caller's selected mailbox."""
    try:
        if not check_connection_status(telegram_user_id, app="gmail"):
            return dict(_NOT_CONNECTED)
        session, account_id, resolved_email, all_emails = _mailbox_context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GMAIL_SEND_EMAIL",
            {"recipient_email": recipient, "subject": subject, "body": body},
            account_id,
        )
        return {
            "status": "success",
            "active_mailbox": resolved_email or "default",
            "all_connected_mailboxes": all_emails,
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi gửi email: {exc}")


def composio_mail_create_draft(
    telegram_user_id: int | str,
    recipient: str,
    subject: str,
    body: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Create a Gmail draft in the caller's selected mailbox."""
    try:
        if not check_connection_status(telegram_user_id, app="gmail"):
            return dict(_NOT_CONNECTED)
        session, account_id, resolved_email, all_emails = _mailbox_context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GMAIL_CREATE_EMAIL_DRAFT",
            {"recipient_email": recipient, "subject": subject, "body": body},
            account_id,
        )
        return {
            "status": "success",
            "active_mailbox": resolved_email or "default",
            "all_connected_mailboxes": all_emails,
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi tạo bản nháp email: {exc}")


def composio_mail_reply(
    telegram_user_id: int | str,
    thread_id: str,
    body: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Reply to a Gmail thread from the caller's selected mailbox."""
    try:
        if not check_connection_status(telegram_user_id, app="gmail"):
            return dict(_NOT_CONNECTED)
        session, account_id, resolved_email, all_emails = _mailbox_context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GMAIL_REPLY_TO_THREAD",
            {"thread_id": thread_id, "body": body},
            account_id,
        )
        return {
            "status": "success",
            "active_mailbox": resolved_email or "default",
            "all_connected_mailboxes": all_emails,
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi trả lời email: {exc}")
