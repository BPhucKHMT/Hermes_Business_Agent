"""Composio Gmail tools with strict host-bound user isolation and multi-account support (v3 SDK)."""

from typing import Union, Dict, Any, Optional
from .client import format_user_id, get_composio_client
from .auth import check_connection_status, get_user_emails


def resolve_account_id(
    telegram_user_id: Union[int, str],
    account_email: Optional[str] = None,
) -> Optional[str]:
    """Find the specific Composio account ID matching the requested email, or None."""
    if not account_email:
        return None
    try:
        emails = get_user_emails(telegram_user_id)
        target = account_email.lower().strip()
        for acc_id, em in emails.items():
            if target in em.lower():
                return acc_id
    except Exception:
        pass
    return None


def composio_mail_search(
    telegram_user_id: Union[int, str],
    query: str = "label:inbox",
    max_results: int = 5,
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Search and fetch emails for the authenticated Telegram user."""
    if not check_connection_status(telegram_user_id, app="gmail"):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối tài khoản Gmail. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id = resolve_account_id(telegram_user_id, account_email)

    kwargs: Dict[str, Any] = {
        "tool_slug": "GMAIL_FETCH_EMAILS",
        "arguments": {"query": query, "max_results": max_results},
    }
    if acc_id:
        kwargs["account"] = acc_id

    try:
        result = session.execute(**kwargs)
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tìm kiếm email: {str(exc)}"}


def composio_mail_send(
    telegram_user_id: Union[int, str],
    recipient: str,
    subject: str,
    body: str,
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Send an email from the authenticated user's Gmail account."""
    if not check_connection_status(telegram_user_id, app="gmail"):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối tài khoản Gmail. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id = resolve_account_id(telegram_user_id, account_email)

    kwargs: Dict[str, Any] = {
        "tool_slug": "GMAIL_SEND_EMAIL",
        "arguments": {
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
        },
    }
    if acc_id:
        kwargs["account"] = acc_id

    try:
        result = session.execute(**kwargs)
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi gửi email: {str(exc)}"}


def composio_mail_create_draft(
    telegram_user_id: Union[int, str],
    recipient: str,
    subject: str,
    body: str,
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a draft email in the user's Gmail account without sending it immediately."""
    if not check_connection_status(telegram_user_id, app="gmail"):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối tài khoản Gmail. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id = resolve_account_id(telegram_user_id, account_email)

    kwargs: Dict[str, Any] = {
        "tool_slug": "GMAIL_CREATE_EMAIL_DRAFT",
        "arguments": {
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
        },
    }
    if acc_id:
        kwargs["account"] = acc_id

    try:
        result = session.execute(**kwargs)
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tạo bản nháp email: {str(exc)}"}


def composio_mail_reply(
    telegram_user_id: Union[int, str],
    thread_id: str,
    body: str,
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Reply to an existing Gmail thread from the user's Gmail account."""
    if not check_connection_status(telegram_user_id, app="gmail"):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối tài khoản Gmail. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id = resolve_account_id(telegram_user_id, account_email)

    kwargs: Dict[str, Any] = {
        "tool_slug": "GMAIL_REPLY_TO_THREAD",
        "arguments": {
            "thread_id": thread_id,
            "body": body,
        },
    }
    if acc_id:
        kwargs["account"] = acc_id

    try:
        result = session.execute(**kwargs)
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi trả lời email: {str(exc)}"}
def composio_mail_get_thread(
    telegram_user_id: Union[int, str],
    thread_id: str,
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve full message contents of a specific Gmail thread ID."""
    if not check_connection_status(telegram_user_id, app="gmail"):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối tài khoản Gmail. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id = resolve_account_id(telegram_user_id, account_email)

    kwargs: Dict[str, Any] = {
        "tool_slug": "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
        "arguments": {"thread_id": thread_id},
    }
    if acc_id:
        kwargs["account"] = acc_id

    try:
        result = session.execute(**kwargs)
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi đọc chuỗi email: {str(exc)}"}
