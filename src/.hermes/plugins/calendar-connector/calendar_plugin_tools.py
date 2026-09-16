from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any

from calendar_caller import CallerContextRegistry, DmOnlyError

logger = logging.getLogger(__name__)


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(code: str, message: str = "") -> str:
    err: dict[str, Any] = {"code": code}
    if message:
        err["message"] = message
        lower = message.lower()
        if any(
            term in lower
            for term in ("missing_access_token", "invalid_grant", "401", "unauthorized")
        ):
            err["hint"] = (
                "Google account is not connected or the token has expired. Use /connect_google to reconnect."
            )
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


def _candidate_src_dirs() -> list[Path]:
    candidates: list[Path] = []
    for key in ("HERMES_PROJECT_SRC", "HERMES_SRC_DIR"):
        val = os.environ.get(key)
        if val and (Path(val) / "tools").is_dir():
            candidates.append(Path(val))
    if len(Path(__file__).resolve().parents) >= 3:
        parent_candidate = Path(__file__).resolve().parents[2]
        if (parent_candidate / "tools").is_dir():
            candidates.append(parent_candidate)
    for env_file in (
        Path.home() / ".hermes" / ".env",
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
        if os.name == "nt"
        else None,
    ):
        if env_file and env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("HERMES_PROJECT_SRC="):
                        val = (
                            line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        )
                        if val and (Path(val) / "tools").is_dir():
                            candidates.append(Path(val))
            except OSError:
                pass
    for cwd_cand in (Path.cwd() / "src", Path.cwd()):
        if (cwd_cand / "tools").is_dir():
            candidates.append(cwd_cand)
    return candidates


_composio_bridge = None
try:
    from tools.composio import bridge as _composio_bridge
except (ImportError, ModuleNotFoundError):
    for _cand in _candidate_src_dirs():
        _target = _cand / "tools" / "composio" / "bridge.py"
        if _target.is_file():
            _src_dir = str(_cand.resolve())
            if _src_dir not in sys.path:
                sys.path.insert(0, _src_dir)
            _spec = importlib.util.spec_from_file_location(
                "tools.composio.bridge", str(_target)
            )
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                sys.modules["tools.composio.bridge"] = _mod
                _spec.loader.exec_module(_mod)
                _composio_bridge = _mod
                break


def _call_google(
    operation: str,
    principal_id: str,
    params: dict[str, Any] | None = None,
) -> Any:
    bridge = sys.modules.get("tools.composio.bridge") or _composio_bridge
    if bridge is None or not hasattr(bridge, "call_google"):
        raise RuntimeError(
            "call_google bridge unavailable; run python src/setup_local.py --local"
        )
    return bridge.call_google(operation, principal_id, params)


def _resolve_principal(caller: Any) -> str:
    principal_id = str(getattr(caller, "principal_id", "")).strip()
    if not principal_id:
        raise LookupError("caller_principal_unavailable")
    return principal_id


def handle_calendar_list_events(
    params: dict[str, Any],
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

    try:
        principal_id = _resolve_principal(caller)
    except LookupError as exc:
        return _caller_error(exc)
    account_email = params.get("account_email")
    use_composio = bool(getattr(caller, "user_id", None))

    if use_composio:
        try:
            c_res = _call_google(
                "composio_calendar_list_events",
                principal_id,
                {
                    "calendar_id": params.get("calendar_id", "primary"),
                    "account_email": account_email,
                    "time_min": params.get("time_min"),
                    "time_max": params.get("time_max"),
                    "query": params.get("query"),
                    "limit": params.get("limit", 20),
                },
            )
            if c_res.get("status") == "success":
                raw_data = c_res.get("data", {})
                items = raw_data.get("items", []) if isinstance(raw_data, dict) else []
                return _json(
                    {
                        "ok": True,
                        "result": {
                            "events": items,
                            "count": len(items),
                            "summary": raw_data.get("summary")
                            if isinstance(raw_data, dict)
                            else "",
                            "active_account": c_res.get("active_account"),
                            "all_connected_accounts": c_res.get(
                                "all_connected_accounts", []
                            ),
                        },
                    }
                )
            return _error(
                c_res.get("error_code", "calendar_query_failed").lower(),
                c_res.get("message", "Failed to read calendar"),
            )
        except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
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
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("calendar_query_failed", str(exc))


def handle_calendar_find_free_slots(
    params: dict[str, Any],
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
        principal_id = _resolve_principal(caller)
        account_email = params.get("account_email")
        use_composio = bool(getattr(caller, "user_id", None))
        if use_composio:
            try:
                c_res = _call_google(
                    "composio_calendar_find_free_slots",
                    principal_id,
                    {
                        "date_str": date_str,
                        "duration_minutes": params.get("duration_minutes", 30),
                        "calendar_id": params.get("calendar_id", "primary"),
                        "account_email": account_email,
                    },
                )
                if c_res.get("status") == "success":
                    return _json(
                        {
                            "ok": True,
                            "result": c_res.get("data", {}),
                            "active_account": c_res.get("active_account"),
                        }
                    )
                return _error(
                    c_res.get("error_code", "free_slots_search_failed").lower(),
                    c_res.get("message", "Failed to find free slots"),
                )
            except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
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
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("free_slots_search_failed", str(exc))


def handle_calendar_create_draft_event(
    params: dict[str, Any],
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
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("create_draft_failed", str(exc))


def handle_calendar_confirm_event(
    params: dict[str, Any],
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
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("confirm_event_failed", str(exc))


def handle_calendar_status(
    params: dict[str, Any],
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

    try:
        principal_id = _resolve_principal(caller)
    except LookupError as exc:
        return _caller_error(exc)
    if principal_id:
        try:
            account_emails = _call_google("get_user_emails", principal_id)
            if account_emails:
                clean_emails = []
                for raw_em in account_emails.values():
                    match = re.search(
                        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", raw_em
                    )
                    clean = match.group(0).lower() if match else raw_em.lower()
                    if clean not in clean_emails:
                        clean_emails.append(clean)

                if clean_emails:
                    calendars = [
                        {
                            "email": em,
                            "calendar_id": "primary",
                            "calendar_name": f"Google Calendar ({em})",
                        }
                        for em in clean_emails
                    ]
                    return _json(
                        {
                            "ok": True,
                            "status": "connected",
                            "principal_id": principal_id,
                            "connected_accounts": clean_emails,
                            "calendars": calendars,
                        }
                    )
        except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
            logger.debug(
                "Failed querying Composio account emails for status (%s): %s",
                principal_id,
                exc,
            )

    try:
        res = client.status(caller)
        return _json(res)
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("calendar_status_failed", str(exc))


def handle_calendar_get_event(
    params: dict[str, Any],
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

    try:
        principal_id = _resolve_principal(caller)
    except LookupError as exc:
        return _caller_error(exc)
    account_email = params.get("account_email")
    try:
        c_res = _call_google(
            "composio_calendar_get_event",
            principal_id,
            {
                "event_id": event_id,
                "calendar_id": params.get("calendar_id", "primary"),
                "account_email": account_email,
            },
        )
        if c_res.get("status") == "success":
            return _json(
                {
                    "ok": True,
                    "result": {
                        "event": c_res.get("data", {}),
                        "active_account": c_res.get("active_account"),
                    },
                }
            )
        return _error(
            c_res.get("error_code", "get_event_failed").lower(),
            c_res.get("message", "Failed to get event details"),
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("get_event_failed", str(exc))


def handle_calendar_create_event(
    params: dict[str, Any],
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
        return _error(
            "missing_required_event_fields", "summary and start_time are required"
        )

    try:
        principal_id = _resolve_principal(caller)
    except LookupError as exc:
        return _caller_error(exc)
    account_email = params.get("account_email")

    try:
        c_res = _call_google(
            "composio_calendar_create_event",
            principal_id,
            {
                "summary": summary,
                "start_datetime": start_time,
                "end_datetime": params.get("end_time"),
                "duration_minutes": params.get("duration_minutes", 30),
                "description": str(params.get("description", "")),
                "location": str(params.get("location", "")),
                "attendees": list(params.get("attendees", []))
                if params.get("attendees")
                else None,
                "calendar_id": str(params.get("calendar_id", "primary")),
                "account_email": account_email,
            },
        )
        if c_res.get("status") == "success":
            data = c_res.get("data", {})
            created_id = data.get("id") or data.get("event_id")
            if not created_id:
                return _error("create_event_failed", "provider_missing_event_id")
            return _json(
                {
                    "ok": True,
                    "result": {
                        "status": "confirmed",
                        "event_id": created_id,
                        "event": data,
                        "summary": summary,
                        "start_time": start_time,
                        "active_account": c_res.get("active_account"),
                        "html_link": data.get("htmlLink")
                        or data.get("display_url")
                        or "",
                    },
                }
            )
        return _error(
            "create_event_failed",
            c_res.get("message", "Failed to create Calendar event"),
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("create_event_failed", str(exc))


def handle_calendar_update_event(
    params: dict[str, Any],
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

    try:
        principal_id = _resolve_principal(caller)
    except LookupError as exc:
        return _caller_error(exc)
    account_email = params.get("account_email")

    try:
        c_res = _call_google(
            "composio_calendar_patch_event",
            principal_id,
            {
                "event_id": event_id,
                "calendar_id": params.get("calendar_id", "primary"),
                "account_email": account_email,
                "start_time": params.get("start_time"),
                "end_time": params.get("end_time"),
                "summary": params.get("summary"),
                "description": params.get("description"),
                "location": params.get("location"),
                "attendees": list(params.get("attendees"))
                if params.get("attendees") is not None
                else None,
            },
        )
        if c_res.get("status") == "success":
            data = c_res.get("data", {})
            return _json(
                {
                    "ok": True,
                    "result": {
                        "status": "updated",
                        "event_id": event_id,
                        "event": data,
                        "active_account": c_res.get("active_account"),
                        "html_link": data.get("htmlLink")
                        or data.get("display_url")
                        or "",
                    },
                }
            )
        return _error(
            "update_event_failed", c_res.get("message", "Failed to update the event")
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("update_event_failed", str(exc))


def handle_calendar_delete_event(
    params: dict[str, Any],
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

    try:
        principal_id = _resolve_principal(caller)
    except LookupError as exc:
        return _caller_error(exc)
    account_email = params.get("account_email")

    try:
        c_res = _call_google(
            "composio_calendar_delete_event",
            principal_id,
            {
                "event_id": event_id,
                "calendar_id": params.get("calendar_id", "primary"),
                "account_email": account_email,
            },
        )
        if c_res.get("status") == "success":
            return _json(
                {
                    "ok": True,
                    "result": {
                        "status": "deleted",
                        "deleted": True,
                        "event_id": event_id,
                        "active_account": c_res.get("active_account"),
                    },
                }
            )
        return _error(
            "delete_event_failed", c_res.get("message", "Failed to delete the calendar")
        )
    except Exception as exc:  # noqa: BLE001 -- tool/gateway boundary maps to error payload
        return _error("delete_event_failed", str(exc))
