"""Composio Google Calendar tools with strict host-bound user isolation (v3 SDK)."""

from typing import Union, Dict, Any, Optional, List
from .client import format_user_id, get_composio_client
from .auth import check_connection_status


def composio_calendar_list_events(
    telegram_user_id: Union[int, str],
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """List or search events in the user's Google Calendar."""
    if not (check_connection_status(telegram_user_id, app="googlecalendar") or check_connection_status(telegram_user_id, app="gmail")):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id)

    try:
        result = session.execute(
            tool_slug="GOOGLECALENDAR_FIND_EVENT",
            arguments={"calendar_id": calendar_id},
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi đọc lịch trình: {str(exc)}"}


def composio_calendar_create_event(
    telegram_user_id: Union[int, str],
    summary: str,
    start_datetime: str,
    duration_minutes: int = 30,
    description: str = "",
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """Create a new event in the user's Google Calendar."""
    if not (check_connection_status(telegram_user_id, app="googlecalendar") or check_connection_status(telegram_user_id, app="gmail")):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id)

    params: Dict[str, Any] = {
        "calendar_id": calendar_id,
        "summary": summary,
        "start_datetime": start_datetime,
        "duration": duration_minutes,
    }
    if description:
        params["description"] = description
    if attendees:
        params["attendees"] = attendees

    try:
        result = session.execute(
            tool_slug="GOOGLECALENDAR_CREATE_EVENT",
            arguments=params,
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tạo lịch hẹn: {str(exc)}"}


def composio_calendar_find_free_slots(
    telegram_user_id: Union[int, str],
    date_str: str,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """Find free slots in the user's Google Calendar for a given date."""
    if not (check_connection_status(telegram_user_id, app="googlecalendar") or check_connection_status(telegram_user_id, app="gmail")):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id)

    try:
        result = session.execute(
            tool_slug="GOOGLECALENDAR_FIND_FREE_SLOTS",
            arguments={"date": date_str, "calendar_id": calendar_id},
        )
        return {"status": "success", "data": getattr(result, "data", result)}
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tìm khoảng thời gian trống: {str(exc)}"}
