"""Composio Google Calendar tools with strict host-bound user isolation (v3 SDK)."""

from typing import Union, Dict, Any, Optional, List
from .client import format_user_id, get_composio_client
from .auth import check_connection_status, resolve_account_target, get_user_emails

def _normalize_event_data(result: Any) -> Dict[str, Any]:
    """Extract standard event dictionary from Composio SessionExecuteResponse."""
    raw = getattr(result, "data", result)
    if not isinstance(raw, dict):
        return {}
    if "response_data" in raw and isinstance(raw["response_data"], dict):
        merged = dict(raw["response_data"])
        if "display_url" in raw and "htmlLink" not in merged:
            merged["htmlLink"] = raw["display_url"]
        return merged
    return raw

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
            "data": _normalize_event_data(result),
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
def composio_calendar_get_event(
    telegram_user_id: Union[int, str],
    event_id: str,
    calendar_id: str = "primary",
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve details of a single Google Calendar event by ID."""
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

    args = {"event_id": event_id, "calendar_id": calendar_id}
    kwargs: Dict[str, Any] = {"arguments": args}
    if acc_id:
        kwargs["account"] = acc_id

    try:
        try:
            result = session.execute(tool_slug="GOOGLESUPER_EVENTS_GET", **kwargs)
        except Exception:
            result = session.execute(tool_slug="GOOGLECALENDAR_EVENTS_GET", **kwargs)
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": _normalize_event_data(result),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi lấy thông tin sự kiện: {str(exc)}"}


def composio_calendar_patch_event(
    telegram_user_id: Union[int, str],
    event_id: str,
    calendar_id: str = "primary",
    account_email: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    timezone_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Reschedule or update specified fields of an existing Google Calendar event using patch semantics."""
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
        "event_id": event_id,
        "calendar_id": calendar_id,
    }
    if start_time:
        args["start_time"] = start_time
    if end_time:
        args["end_time"] = end_time
    if summary:
        args["summary"] = summary
    if description:
        args["description"] = description
    if location:
        args["location"] = location
    if attendees is not None:
        args["attendees"] = attendees
    if timezone_str:
        args["timezone"] = timezone_str

    kwargs: Dict[str, Any] = {"arguments": args}
    if acc_id:
        kwargs["account"] = acc_id

    try:
        try:
            result = session.execute(tool_slug="GOOGLESUPER_PATCH_EVENT", **kwargs)
        except Exception:
            result = session.execute(tool_slug="GOOGLECALENDAR_PATCH_EVENT", **kwargs)
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": _normalize_event_data(result),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi dời/sửa lịch: {str(exc)}"}

def composio_calendar_delete_event(
    telegram_user_id: Union[int, str],
    event_id: str,
    calendar_id: str = "primary",
    account_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel and delete an event from Google Calendar."""
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

    args = {"event_id": event_id, "calendar_id": calendar_id}
    kwargs: Dict[str, Any] = {"arguments": args}
    if acc_id:
        kwargs["account"] = acc_id

    try:
        try:
            result = session.execute(tool_slug="GOOGLESUPER_DELETE_EVENT", **kwargs)
        except Exception:
            result = session.execute(tool_slug="GOOGLECALENDAR_DELETE_EVENT", **kwargs)
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": getattr(result, "data", result),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Lỗi khi hủy/xóa lịch: {str(exc)}"}
