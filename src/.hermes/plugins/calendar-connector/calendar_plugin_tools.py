from __future__ import annotations

import json
from typing import Any, Dict

from calendar_caller import CallerContextRegistry, DmOnlyError


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(code: str, message: str = "") -> str:
    err: Dict[str, Any] = {"code": code}
    if message:
        err["message"] = message
        lower = message.lower()
        if any(term in lower for term in ("missing_access_token", "invalid_grant", "401", "unauthorized")):
            err["hint"] = "Tài khoản Google chưa được kết nối hoặc token đã hết hạn. Hãy dùng lệnh /connect_google để kết nối lại."
    return _json({"ok": False, "error": err})

def _resolve_caller(
    registry: CallerContextRegistry | Any,
    task_id: str,
    session_id: str,
) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_dm_tool(task_id=task_id, session_id=session_id)


def _caller_error(exc: Exception) -> str:
    if isinstance(exc, DmOnlyError):
        return _error("dm_required", str(exc))
    return _error("missing_caller_context", str(exc))


def handle_calendar_list_events(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    account_email = params.get("account_email")

    if user_id:
        try:
            from tools.composio.calendar_tools import composio_calendar_list_events
            from tools.composio.auth import check_connection_status
            if check_connection_status(user_id, app="googlecalendar") or check_connection_status(user_id, app="googlesuper"):
                c_res = composio_calendar_list_events(
                    user_id,
                    calendar_id=params.get("calendar_id", "primary"),
                    account_email=account_email,
                    time_min=params.get("time_min"),
                    time_max=params.get("time_max"),
                    query=params.get("query"),
                    limit=params.get("limit", 20),
                )
                if c_res.get("status") == "success":
                    raw_data = c_res.get("data", {})
                    items = raw_data.get("items", []) if isinstance(raw_data, dict) else []
                    return _json({
                        "ok": True,
                        "result": {
                            "events": items,
                            "count": len(items),
                            "summary": raw_data.get("summary") if isinstance(raw_data, dict) else "",
                            "active_account": c_res.get("active_account"),
                            "all_connected_accounts": c_res.get("all_connected_accounts", []),
                        },
                    })
                return _error("calendar_query_failed", c_res.get("message", "Lỗi khi đọc lịch"))
        except Exception as exc:
            return _error("calendar_query_failed", str(exc))
    try:
        res = client.list_events(
            caller=caller,
            time_min=params.get("time_min"),
            time_max=params.get("time_max"),
            limit=params.get("limit", 20),
            calendar_id=params.get("calendar_id", "primary"),
        )
        return _json(res)
    except Exception as exc:
        return _error("calendar_query_failed", str(exc))

def handle_calendar_find_free_slots(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        date_str = params.get("date", "")
        if not date_str:
            return _error("date_parameter_required")
        user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
        account_email = params.get("account_email")
        if user_id:
            try:
                from tools.composio.calendar_tools import composio_calendar_find_free_slots
                from tools.composio.auth import check_connection_status
                if check_connection_status(user_id, app="googlecalendar") or check_connection_status(user_id, app="googlesuper"):
                    c_res = composio_calendar_find_free_slots(
                        user_id,
                        date_str=date_str,
                        duration_minutes=params.get("duration_minutes", 30),
                        calendar_id=params.get("calendar_id", "primary"),
                        account_email=account_email,
                    )
                    if c_res.get("status") == "success":
                        return _json({
                            "ok": True,
                            "result": c_res.get("data", {}),
                            "active_account": c_res.get("active_account"),
                        })
                    return _error("free_slots_search_failed", c_res.get("message", "Lỗi tìm khoảng trống"))
            except Exception as exc:
                return _error("free_slots_search_failed", str(exc))

        res = client.find_free_slots(
            caller=caller,
            date_str=date_str,
            duration_minutes=params.get("duration_minutes", 30),
            calendar_id=params.get("calendar_id", "primary"),
        )
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("free_slots_search_failed", str(exc))


def handle_calendar_create_draft_event(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        summary = str(params.get("summary", ""))
        start_time = str(params.get("start_time", ""))
        end_time = str(params.get("end_time", ""))
        if not summary or not start_time or not end_time:
            return _error("missing_required_event_fields")
        attendees = tuple(params.get("attendees", []))
        res = client.create_draft_event(
            caller=caller,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            location=str(params.get("location", "")),
            description=str(params.get("description", "")),
            attendees=attendees,
            calendar_id=str(params.get("calendar_id", "primary")),
            account_email=params.get("account_email"),
        )
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("create_draft_failed", str(exc))


def handle_calendar_confirm_event(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        draft_id = str(params.get("draft_id", ""))
        if not draft_id:
            return _error("draft_id_required")

        res = client.confirm_event(caller=caller, draft_id=draft_id)
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("confirm_event_failed", str(exc))


def handle_calendar_status(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del params, kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    if user_id:
        try:
            import re
            from tools.composio.auth import get_user_emails
            account_emails = get_user_emails(user_id)
            if account_emails:
                clean_emails = []
                for raw_em in account_emails.values():
                    match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_em)
                    clean = match.group(0).lower() if match else raw_em.lower()
                    if clean not in clean_emails:
                        clean_emails.append(clean)

                if clean_emails:
                    calendars = [
                        {"email": em, "calendar_id": "primary", "calendar_name": f"Google Calendar ({em})"}
                        for em in clean_emails
                    ]
                    return _json({
                        "ok": True,
                        "status": "connected",
                        "principal_id": getattr(caller, "principal_id", f"telegram:default:{user_id}"),
                        "connected_accounts": clean_emails,
                        "calendars": calendars,
                    })
        except Exception:
            pass

    try:
        res = client.status(caller)
        return _json(res)
    except Exception as exc:
        return _error("calendar_status_failed", str(exc))
def handle_calendar_get_event(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    event_id = str(params.get("event_id", "")).strip()
    if not event_id:
        return _error("event_id_required")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    account_email = params.get("account_email")

    if user_id:
        try:
            from tools.composio.calendar_tools import composio_calendar_get_event
            c_res = composio_calendar_get_event(
                user_id,
                event_id=event_id,
                calendar_id=params.get("calendar_id", "primary"),
                account_email=account_email,
            )
            if c_res.get("status") == "success":
                return _json({
                    "ok": True,
                    "result": {
                        "event": c_res.get("data", {}),
                        "active_account": c_res.get("active_account"),
                    },
                })
            return _error("get_event_failed", c_res.get("message", "Lỗi khi lấy thông tin sự kiện"))
        except Exception as exc:
            return _error("get_event_failed", str(exc))

    try:
        ev = client.service.get_event(caller=caller, event_id=event_id, calendar_id=params.get("calendar_id", "primary"))
        from dataclasses import asdict
        return _json({"ok": True, "result": {"event": asdict(ev)}})
    except Exception as exc:
        return _error("get_event_failed", str(exc))


def handle_calendar_create_event(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    """Directly create an event on Google Calendar without staging a draft."""
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    summary = str(params.get("summary", "")).strip()
    start_time = str(params.get("start_time", "")).strip()
    if not summary or not start_time:
        return _error("missing_required_event_fields", "summary and start_time are required")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    account_email = params.get("account_email")

    if user_id:
        try:
            from tools.composio.calendar_tools import composio_calendar_create_event
            c_res = composio_calendar_create_event(
                user_id,
                summary=summary,
                start_datetime=start_time,
                end_datetime=params.get("end_time"),
                duration_minutes=params.get("duration_minutes", 30),
                description=str(params.get("description", "")),
                location=str(params.get("location", "")),
                attendees=list(params.get("attendees", [])) if params.get("attendees") else None,
                calendar_id=str(params.get("calendar_id", "primary")),
                account_email=account_email,
            )
            if c_res.get("status") == "success":
                data = c_res.get("data", {})
                created_id = data.get("id") or data.get("event_id") or "composio_evt"
                return _json({
                    "ok": True,
                    "result": {
                        "status": "confirmed",
                        "event_id": created_id,
                        "event": data,
                        "summary": summary,
                        "start_time": start_time,
                        "active_account": c_res.get("active_account"),
                        "html_link": data.get("htmlLink") or data.get("display_url") or "",
                    },
                })
            return _error("create_event_failed", c_res.get("message", "Lỗi tạo sự kiện trên Calendar"))
        except Exception as exc:
            return _error("create_event_failed", str(exc))

    return _error("calendar_connector_unavailable")


def handle_calendar_update_event(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    """Reschedule or update specified fields of an existing Google Calendar event."""
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    event_id = str(params.get("event_id", "")).strip()
    if not event_id:
        return _error("event_id_required")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    account_email = params.get("account_email")

    if user_id:
        try:
            from tools.composio.calendar_tools import composio_calendar_patch_event
            c_res = composio_calendar_patch_event(
                user_id,
                event_id=event_id,
                calendar_id=params.get("calendar_id", "primary"),
                account_email=account_email,
                start_time=params.get("start_time"),
                end_time=params.get("end_time"),
                summary=params.get("summary"),
                description=params.get("description"),
                location=params.get("location"),
                attendees=list(params.get("attendees")) if params.get("attendees") is not None else None,
            )
            if c_res.get("status") == "success":
                data = c_res.get("data", {})
                return _json({
                    "ok": True,
                    "result": {
                        "status": "updated",
                        "event_id": event_id,
                        "event": data,
                        "active_account": c_res.get("active_account"),
                        "html_link": data.get("htmlLink") or data.get("display_url") or "",
                    },
                })
            return _error("update_event_failed", c_res.get("message", "Lỗi khi cập nhật sự kiện"))
        except Exception as exc:
            return _error("update_event_failed", str(exc))

    return _error("calendar_connector_unavailable")


def handle_calendar_delete_event(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    """Cancel and delete an event from Google Calendar."""
    del kwargs
    if client is None:
        return _error("calendar_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)

    event_id = str(params.get("event_id", "")).strip()
    if not event_id:
        return _error("event_id_required")

    user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
    account_email = params.get("account_email")

    if user_id:
        try:
            from tools.composio.calendar_tools import composio_calendar_delete_event
            c_res = composio_calendar_delete_event(
                user_id,
                event_id=event_id,
                calendar_id=params.get("calendar_id", "primary"),
                account_email=account_email,
            )
            if c_res.get("status") == "success":
                return _json({
                    "ok": True,
                    "result": {
                        "status": "deleted",
                        "deleted": True,
                        "event_id": event_id,
                        "active_account": c_res.get("active_account"),
                    },
                })
            return _error("delete_event_failed", c_res.get("message", "Lỗi khi xóa sự kiện"))
        except Exception as exc:
            return _error("delete_event_failed", str(exc))

    return _error("calendar_connector_unavailable")
