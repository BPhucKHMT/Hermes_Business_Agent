"""Composio Gmail tools with strict host-bound user isolation (v3 SDK)."""

from typing import Union, Dict, Any
from .client import format_user_id, get_composio_client
from .auth import check_connection_status


def composio_mail_search(
    telegram_user_id: Union[int, str],
    query: str = "label:inbox",
    max_results: int = 5,
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
    session = client.create(user_id=user_id)

    try:
        result = session.execute(
            tool_slug="GMAIL_FETCH_EMAILS",
            arguments={"query": query, "max_results": max_results},
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tìm kiếm email: {str(exc)}"}


def composio_mail_send(
    telegram_user_id: Union[int, str],
    recipient: str,
    subject: str,
    body: str,
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
    session = client.create(user_id=user_id)

    try:
        result = session.execute(
            tool_slug="GMAIL_SEND_EMAIL",
            arguments={
                "recipient_email": recipient,
                "subject": subject,
                "body": body,
            },
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi gửi email: {str(exc)}"}


def composio_mail_create_draft(
    telegram_user_id: Union[int, str],
    recipient: str,
    subject: str,
    body: str,
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
    session = client.create(user_id=user_id)

    try:
        result = session.execute(
            tool_slug="GMAIL_CREATE_EMAIL_DRAFT",
            arguments={
                "recipient_email": recipient,
                "subject": subject,
                "body": body,
            },
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tạo bản nháp email: {str(exc)}"}


def composio_mail_reply(
    telegram_user_id: Union[int, str],
    thread_id: str,
    body: str,
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
    session = client.create(user_id=user_id)

    try:
        result = session.execute(
            tool_slug="GMAIL_REPLY_TO_THREAD",
            arguments={
                "thread_id": thread_id,
                "body": body,
            },
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi trả lời email: {str(exc)}"}
