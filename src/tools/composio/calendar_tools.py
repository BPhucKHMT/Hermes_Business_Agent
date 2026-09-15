"""Composio Google Calendar tools with strict caller/account isolation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .auth import check_connection_status, get_user_emails, resolve_account_target
from .client import (
    execute_composio_tool,
    format_user_id,
    get_composio_client,
    get_response_data,
)

_NOT_CONNECTED = {
    "status": "error",
    "error_code": "NOT_CONNECTED",
    "message": "Bạn chưa kết nối Google Calendar. Vui lòng dùng lệnh /connect-google để liên kết tài khoản.",
}


def _normalize_event_data(result: Any) -> dict[str, Any]:
    """Extract the provider event payload from an SDK response."""
    raw = get_response_data(result)
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("response_data")
    if isinstance(nested, dict):
        merged = dict(nested)
        if "display_url" in raw and "htmlLink" not in merged:
            merged["htmlLink"] = raw["display_url"]
        return merged
    return raw


def _is_calendar_connected(principal_id: int | str) -> bool:
    return any(
        check_connection_status(principal_id, app=app)
        for app in ("googlesuper", "googlecalendar", "gmail")
    )


def _context(
    principal_id: int | str, account_email: str | None
) -> tuple[Any, str | None, str | None, list[str]]:
    """Resolve account before creating a provider session."""
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
    slug: str,
    fallback_slug: str,
    arguments: dict[str, Any],
    account_id: str | None,
) -> Any:
    kwargs: dict[str, Any] = {"arguments": arguments}
    if account_id:
        kwargs["account"] = account_id
    return execute_composio_tool(
        session,
        slug,
        fallback_slug=fallback_slug,
        **kwargs,
    )


def _error(message: str, *, code: str = "PROVIDER_ERROR") -> dict[str, Any]:
    return {"status": "error", "error_code": code, "message": message}


def composio_calendar_list_events(
    telegram_user_id: int | str,
    calendar_id: str = "primary",
    account_email: str | None = None,
    time_min: str | None = None,
    time_max: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List or search events in a caller's selected Google Calendar."""
    if not _is_calendar_connected(telegram_user_id):
        return dict(_NOT_CONNECTED)
    try:
        session, account_id, resolved_email, all_emails = _context(
            telegram_user_id, account_email
        )
        args: dict[str, Any] = {
            "calendar_id": calendar_id,
            "calendarId": calendar_id,
            "maxResults": limit,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        effective_time_min = time_min
        if not effective_time_min and not query:
            effective_time_min = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        if effective_time_min:
            args["timeMin"] = effective_time_min
            args["time_min"] = effective_time_min
        if time_max:
            args["timeMax"] = time_max
            args["time_max"] = time_max
        if query:
            args["q"] = query
        result = _execute(
            session,
            "GOOGLESUPER_EVENTS_LIST",
            "GOOGLECALENDAR_FIND_EVENT",
            args,
            account_id,
        )
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "all_connected_accounts": all_emails,
            "data": _normalize_event_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi đọc lịch trình: {exc}")


def composio_calendar_create_event(
    telegram_user_id: int | str,
    summary: str,
    start_datetime: str,
    duration_minutes: int = 30,
    end_datetime: str | None = None,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
    account_email: str | None = None,
) -> dict[str, Any]:
    """Create a Google Calendar event and return its genuine provider ID."""
    if not _is_calendar_connected(telegram_user_id):
        return dict(_NOT_CONNECTED)
    try:
        session, account_id, resolved_email, _ = _context(
            telegram_user_id, account_email
        )
        args: dict[str, Any] = {
            "calendar_id": calendar_id,
            "summary": summary,
            "start_datetime": start_datetime,
            "duration": duration_minutes,
            "event_duration_minutes": duration_minutes,
        }
        if end_datetime:
            args["end_datetime"] = end_datetime
        if description:
            args["description"] = description
        if location:
            args["location"] = location
        if attendees:
            args["attendees"] = attendees
        result = _execute(
            session,
            "GOOGLESUPER_CREATE_EVENT",
            "GOOGLECALENDAR_CREATE_EVENT",
            args,
            account_id,
        )
        data = _normalize_event_data(result)
        event_id = data.get("id") or data.get("event_id")
        if not event_id:
            return _error("provider_event_id_missing", code="PROVIDER_EVENT_ID_MISSING")
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": data,
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi tạo lịch hẹn: {exc}")


def composio_calendar_find_free_slots(
    telegram_user_id: int | str,
    date_str: str,
    duration_minutes: int = 30,
    calendar_id: str = "primary",
    account_email: str | None = None,
    timezone_str: str | None = None,
    working_hours_start: str | None = None,
    working_hours_end: str | None = None,
) -> dict[str, Any]:
    """Find free slots using the provider's duration and calendar constraints."""
    if not _is_calendar_connected(telegram_user_id):
        return dict(_NOT_CONNECTED)
    try:
        session, account_id, resolved_email, _ = _context(
            telegram_user_id, account_email
        )
        args: dict[str, Any] = {
            "date": date_str,
            "start_date": date_str,
            "calendar_id": calendar_id,
            "duration_minutes": duration_minutes,
            "duration": duration_minutes,
        }
        if timezone_str:
            args["timezone"] = timezone_str
        if working_hours_start:
            args["working_hours_start"] = working_hours_start
        if working_hours_end:
            args["working_hours_end"] = working_hours_end
        result = _execute(
            session,
            "GOOGLESUPER_FIND_FREE_SLOTS",
            "GOOGLECALENDAR_FIND_FREE_SLOTS",
            args,
            account_id,
        )
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi tìm khoảng thời gian trống: {exc}")


def composio_calendar_get_event(
    telegram_user_id: int | str,
    event_id: str,
    calendar_id: str = "primary",
    account_email: str | None = None,
) -> dict[str, Any]:
    """Retrieve one event from the caller's selected Google Calendar."""
    if not _is_calendar_connected(telegram_user_id):
        return dict(_NOT_CONNECTED)
    try:
        session, account_id, resolved_email, _ = _context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GOOGLESUPER_EVENTS_GET",
            "GOOGLECALENDAR_EVENTS_GET",
            {"event_id": event_id, "calendar_id": calendar_id},
            account_id,
        )
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": _normalize_event_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi lấy thông tin sự kiện: {exc}")


def composio_calendar_patch_event(
    telegram_user_id: int | str,
    event_id: str,
    calendar_id: str = "primary",
    account_email: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
    timezone_str: str | None = None,
) -> dict[str, Any]:
    """Patch fields on an existing Google Calendar event."""
    if not _is_calendar_connected(telegram_user_id):
        return dict(_NOT_CONNECTED)
    try:
        session, account_id, resolved_email, _ = _context(
            telegram_user_id, account_email
        )
        args: dict[str, Any] = {"event_id": event_id, "calendar_id": calendar_id}
        optional_values = {
            "start_time": start_time,
            "end_time": end_time,
            "summary": summary,
            "description": description,
            "location": location,
            "attendees": attendees,
            "timezone": timezone_str,
        }
        args.update(
            {key: value for key, value in optional_values.items() if value is not None}
        )
        result = _execute(
            session,
            "GOOGLESUPER_PATCH_EVENT",
            "GOOGLECALENDAR_PATCH_EVENT",
            args,
            account_id,
        )
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": _normalize_event_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi dời/sửa lịch: {exc}")


def composio_calendar_delete_event(
    telegram_user_id: int | str,
    event_id: str,
    calendar_id: str = "primary",
    account_email: str | None = None,
) -> dict[str, Any]:
    """Delete an event from the caller's selected Google Calendar."""
    if not _is_calendar_connected(telegram_user_id):
        return dict(_NOT_CONNECTED)
    try:
        session, account_id, resolved_email, _ = _context(
            telegram_user_id, account_email
        )
        result = _execute(
            session,
            "GOOGLESUPER_DELETE_EVENT",
            "GOOGLECALENDAR_DELETE_EVENT",
            {"event_id": event_id, "calendar_id": calendar_id},
            account_id,
        )
        return {
            "status": "success",
            "active_account": resolved_email or "default",
            "data": get_response_data(result),
        }
    except ValueError as exc:
        return _error(str(exc), code="INVALID_ACCOUNT_TARGET")
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure to error payload
        return _error(f"Lỗi khi hủy/xóa lịch: {exc}")
