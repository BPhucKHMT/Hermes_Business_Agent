"""Composio Google Calendar tools with strict host-bound user isolation (v3 SDK)."""

from typing import Union, Dict, Any, Optional, List
from .client import format_user_id, get_composio_client
from .auth import check_connection_status, resolve_account_target, get_user_emails


def composio_calendar_list_events(
    telegram_user_id: Union[int, str],
    calendar_id: str = "primary",
    account_email: Optional[str] = None,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """List or search events in the user's Google Calendar with multi-account support."""
    if not (check_connection_status(telegram_user_id, app="googlesuper") or check_connection_status(telegram_user_id, app="googlecalendar") or check_connection_status(telegram_user_id, app="gmail")):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id, resolved_email = resolve_account_target(telegram_user_id, account_email)
    all_emails = list(dict.fromkeys(get_user_emails(telegram_user_id).values()))

    args: Dict[str, Any] = {
        "calendar_id": calendar_id,
        "calendarId": calendar_id,
        "maxResults": limit,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_min:
        args["timeMin"] = time_min
        args["time_min"] = time_min
    if time_max:
        args["timeMax"] = time_max
        args["time_max"] = time_max
    if query:
        args["q"] = query

    kwargs: Dict[str, Any] = {"arguments": args}
    if acc_id:
        kwargs["account"] = acc_id

    try:
        try:
            result = session.execute(tool_slug="GOOGLESUPER_EVENTS_LIST", **kwargs)
        except Exception:
            result = session.execute(tool_slug="GOOGLECALENDAR_FIND_EVENT", **kwargs)
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "all_connected_accounts": all_emails,
            "data": getattr(result, "data", result),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi đọc lịch trình: {str(exc)}"}
def composio_calendar_create_event(
    telegram_user_id: Union[int, str],
    summary: str,
    start_datetime: str,
    duration_minutes: int = 30,
    end_datetime: Optional[str] = None,
    description: str = "",
    location: str = "",
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary",
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new event in the user's Google Calendar with multi-account support."""
    if not (check_connection_status(telegram_user_id, app="googlesuper") or check_connection_status(telegram_user_id, app="googlecalendar") or check_connection_status(telegram_user_id, app="gmail")):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id, resolved_email = resolve_account_target(telegram_user_id, account_email)

    params: Dict[str, Any] = {
        "calendar_id": calendar_id,
        "summary": summary,
        "start_datetime": start_datetime,
        "duration": duration_minutes,
        "event_duration_minutes": duration_minutes,
    }
    if end_datetime:
        params["end_datetime"] = end_datetime
    if description:
        params["description"] = description
    if location:
        params["location"] = location
    if attendees:
        params["attendees"] = attendees

    kwargs: Dict[str, Any] = {"arguments": params}
    if acc_id:
        kwargs["account"] = acc_id

    try:
        try:
            result = session.execute(tool_slug="GOOGLESUPER_CREATE_EVENT", **kwargs)
        except Exception:
            result = session.execute(tool_slug="GOOGLECALENDAR_CREATE_EVENT", **kwargs)
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": getattr(result, "data", result),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tạo lịch hẹn: {str(exc)}"}
def composio_calendar_find_free_slots(
    telegram_user_id: Union[int, str],
    date_str: str,
    duration_minutes: int = 30,
    calendar_id: str = "primary",
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Find free slots in the user's Google Calendar for a given date with multi-account support."""
    if not (check_connection_status(telegram_user_id, app="googlesuper") or check_connection_status(telegram_user_id, app="googlecalendar") or check_connection_status(telegram_user_id, app="gmail")):
        return {
            "status": "error",
            "error_code": "NOT_CONNECTED",
            "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
        }

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})
    acc_id, resolved_email = resolve_account_target(telegram_user_id, account_email)

    args: Dict[str, Any] = {
        "date": date_str,
        "start_date": date_str,
        "calendar_id": calendar_id,
    }
    kwargs: Dict[str, Any] = {"arguments": args}
    if acc_id:
        kwargs["account"] = acc_id

    try:
        try:
            result = session.execute(tool_slug="GOOGLESUPER_FIND_FREE_SLOTS", **kwargs)
        except Exception:
            result = session.execute(tool_slug="GOOGLECALENDAR_FIND_FREE_SLOTS", **kwargs)
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": getattr(result, "data", result),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi tìm khoảng thời gian trống: {str(exc)}"}
