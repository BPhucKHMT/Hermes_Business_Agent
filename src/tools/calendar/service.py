from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)
from tools.calendar.contracts import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEvent,
    EventDraft,
    EventDraftStatus,
    EventVerification,
    FreeSlot,
    compute_draft_idempotency_key,
)
from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import CalendarPolicy, load_calendar_policy
from tools.calendar.store import CalendarStore


class CalendarService:
    def __init__(
        self,
        policy: CalendarPolicy,
        store: CalendarStore,
        google_client: GoogleCalendarClient,
        token_resolver: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self.policy = policy
        self.store = store
        self.google_client = google_client
        self.token_resolver = token_resolver or self._default_token_resolver

    def _default_token_resolver(self, principal_id: str) -> Dict[str, Any]:
        try:
            from tools.composio.auth import list_user_connections
            conns = list_user_connections(principal_id)
            for c in conns:
                if c.get("status") == "ACTIVE":
                    return {
                        "access_token": c.get("id"),
                        "account_email": c.get("email"),
                        "mock_mode": False,
                    }
        except Exception:
            pass
        conn = self.store.get_connection_by_principal(principal_id)
        if conn:
            return {"access_token": conn.connection_id, "mock_mode": False}
        return {"access_token": "mock_token_for_test", "mock_mode": True}
    def list_events(
        self,
        caller: Any,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 20,
        calendar_id: str = "primary",
    ) -> List[CalendarEvent]:
        token_data = self.token_resolver(caller.principal_id)
        limit = min(max(1, limit), self.policy.max_list_results)

        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        access_token = token_data.get("access_token", "")
        if isinstance(access_token, str) and (access_token.startswith("ca_") or "composio" in access_token):
            try:
                from tools.composio.calendar_tools import composio_calendar_list_events
                user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None) or getattr(caller, "principal_id", "")
                account_email = token_data.get("account_email")
                c_res = composio_calendar_list_events(
                    user_id,
                    calendar_id=calendar_id,
                    account_email=account_email,
                    time_min=time_min,
                    time_max=time_max,
                    limit=limit,
                )
                if c_res.get("status") == "success":
                    raw_data = c_res.get("data", {})
                    items = raw_data.get("items", []) if isinstance(raw_data, dict) else []
                    events = []
                    for it in items:
                        st = it.get("start", {})
                        st_val = st.get("dateTime") or st.get("date") or ""
                        et = it.get("end", {})
                        et_val = et.get("dateTime") or et.get("date") or ""
                        events.append(CalendarEvent(
                            event_id=it.get("id", ""),
                            calendar_id=calendar_id,
                            summary=it.get("summary", ""),
                            start_time=st_val,
                            end_time=et_val,
                            html_link=it.get("htmlLink") or it.get("display_url") or "",
                            status=it.get("status", "confirmed"),
                            location=it.get("location", ""),
                            description=it.get("description", ""),
                            attendees=tuple(a.get("email", "") for a in it.get("attendees", []) if isinstance(a, dict) and a.get("email")),
                            is_all_day=bool(st.get("date") and not st.get("dateTime")),
                        ))
                    self.store.record_audit(
                        principal_id=caller.principal_id,
                        action="list_events",
                        target_id=calendar_id,
                        details={"count": len(events), "time_min": time_min, "time_max": time_max},
                    )
                    return events
            except Exception:
                pass

        events = self.google_client.list_events(
            token_data=token_data,
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=limit,
        )
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="list_events",
            target_id=calendar_id,
            details={"count": len(events), "time_min": time_min, "time_max": time_max},
        )
        return events

    def find_free_slots(
        self,
        caller: Any,
        date_str: str,
        duration_minutes: int = 30,
        calendar_id: str = "primary",
    ) -> List[FreeSlot]:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        wh_start_t = datetime.strptime(self.policy.working_hours.start, "%H:%M").time()
        wh_end_t = datetime.strptime(self.policy.working_hours.end, "%H:%M").time()

        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(self.policy.default_timezone)
        except Exception:
            tz = timezone(timedelta(hours=7))

        day_start_local = datetime.combine(target_date, wh_start_t, tzinfo=tz)
        day_end_local = datetime.combine(target_date, wh_end_t, tzinfo=tz)
        day_start = day_start_local.astimezone(timezone.utc)
        day_end = day_end_local.astimezone(timezone.utc)

        events = self.list_events(
            caller=caller,
            time_min=day_start.isoformat().replace("+00:00", "Z"),
            time_max=day_end.isoformat().replace("+00:00", "Z"),
            limit=self.policy.max_list_results,
            calendar_id=calendar_id,
        )

        busy_intervals = []
        for ev in events:
            if ev.is_all_day:
                continue
            try:
                ev_start = datetime.fromisoformat(ev.start_time.replace("Z", "+00:00"))
                ev_end = datetime.fromisoformat(ev.end_time.replace("Z", "+00:00"))
                ev_start = max(ev_start, day_start)
                ev_end = min(ev_end, day_end)
                if ev_end > ev_start:
                    busy_intervals.append((ev_start, ev_end))
            except Exception:
                continue

        busy_intervals.sort(key=lambda x: x[0])

        merged_busy = []
        for start, end in busy_intervals:
            if not merged_busy:
                merged_busy.append((start, end))
            else:
                last_start, last_end = merged_busy[-1]
                if start <= last_end:
                    merged_busy[-1] = (last_start, max(last_end, end))
                else:
                    merged_busy.append((start, end))

        free_slots: List[FreeSlot] = []
        current_cursor = day_start

        for busy_start, busy_end in merged_busy:
            if busy_start > current_cursor:
                slot_duration = int((busy_start - current_cursor).total_seconds() / 60)
                if slot_duration >= duration_minutes:
                    free_slots.append(
                        FreeSlot(
                            start_time=current_cursor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                            end_time=busy_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                            duration_minutes=slot_duration,
                        )
                    )
            current_cursor = max(current_cursor, busy_end)

        if current_cursor < day_end:
            slot_duration = int((day_end - current_cursor).total_seconds() / 60)
            if slot_duration >= duration_minutes:
                free_slots.append(
                    FreeSlot(
                        start_time=current_cursor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        end_time=day_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        duration_minutes=slot_duration,
                    )
                )

        return free_slots

    def create_draft_event(
        self,
        caller: Any,
        summary: str,
        start_time: str,
        end_time: str,
        location: str = "",
        description: str = "",
        attendees: tuple[str, ...] = (),
        calendar_id: str = "primary",
        account_email: Optional[str] = None,
    ) -> EventDraft:
        if not summary.strip():
            raise ValueError("summary_required")

        dt_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        self.policy.validate_event_time_window(dt_start, dt_end)
        self.policy.validate_lookahead(dt_start)

        idempotency_key = compute_draft_idempotency_key(
            principal_id=caller.principal_id,
            calendar_id=calendar_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
        )

        draft = EventDraft(
            draft_id=f"drf-{uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            principal_id=caller.principal_id,
            calendar_id=calendar_id,
            summary=summary.strip(),
            description=description.strip(),
            location=location.strip(),
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            status=EventDraftStatus.DRAFT,
            account_email=account_email,
        )
        persisted = self.store.create_or_get_draft(draft)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="create_draft_event",
            target_id=persisted.draft_id,
            details={"summary": summary, "start_time": start_time, "end_time": end_time},
        )
        return persisted

    def confirm_event(
        self,
        caller: Any,
        draft_id: str,
    ) -> CalendarEvent:
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise KeyError("draft_not_found")
        if draft.principal_id != caller.principal_id:
            raise PermissionError("principal_not_authorized_for_draft")
        if draft.status == EventDraftStatus.COMMITTED and draft.committed_event_id:
            token_data = self.token_resolver(caller.principal_id)
            return self.google_client.get_event(token_data, draft.calendar_id, draft.committed_event_id)
        if draft.status != EventDraftStatus.DRAFT:
            raise ValueError(f"cannot_confirm_draft_in_status_{draft.status.value}")

        token_data = self.token_resolver(caller.principal_id)
        access_token = token_data.get("access_token", "")
        if isinstance(access_token, str) and (access_token.startswith("ca_") or "composio" in access_token):
            from tools.composio.calendar_tools import composio_calendar_create_event
            user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None) or getattr(caller, "principal_id", "")
            account_email = draft.account_email or token_data.get("account_email")
            c_res = composio_calendar_create_event(
                user_id,
                summary=draft.summary,
                start_datetime=draft.start_time,
                end_datetime=draft.end_time,
                description=draft.description,
                location=draft.location,
                attendees=list(draft.attendees) if draft.attendees else None,
                calendar_id=draft.calendar_id,
                account_email=account_email,
            )
            if c_res.get("status") == "success":
                data = c_res.get("data", {})
                created_id = str(data.get("id") or data.get("event_id") or "composio_evt")
                created_event = CalendarEvent(
                    event_id=created_id,
                    calendar_id=draft.calendar_id,
                    summary=draft.summary,
                    start_time=draft.start_time,
                    end_time=draft.end_time,
                    html_link=data.get("htmlLink") or data.get("display_url") or "",
                    status="confirmed",
                    location=draft.location,
                    description=draft.description,
                    attendees=draft.attendees,
                )
            else:
                raise RuntimeError(c_res.get("message", "composio_create_event_failed"))
        else:
            created_event = self.google_client.create_event(
                token_data=token_data,
                calendar_id=draft.calendar_id,
                draft=draft,
            )

        self.store.transition_draft_status(
            draft_id=draft_id,
            from_status=EventDraftStatus.DRAFT,
            to_status=EventDraftStatus.COMMITTED,
            committed_event_id=created_event.event_id,
        )

        self.store.record_audit(
            principal_id=caller.principal_id,
            action="confirm_event",
            target_id=draft_id,
            details={"event_id": created_event.event_id, "html_link": created_event.html_link},
        )
        return created_event

    def get_event(
        self,
        caller: Any,
        event_id: str,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        token_data = self.token_resolver(caller.principal_id)
        access_token = token_data.get("access_token", "")
        if isinstance(access_token, str) and (access_token.startswith("ca_") or "composio" in access_token):
            from tools.composio.calendar_tools import composio_calendar_get_event
            user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None) or getattr(caller, "principal_id", "")
            account_email = token_data.get("account_email")
            c_res = composio_calendar_get_event(user_id, event_id=event_id, calendar_id=calendar_id, account_email=account_email)
            if c_res.get("status") == "success":
                data = c_res.get("data", {})
                st = data.get("start", {})
                st_val = st.get("dateTime") or st.get("date") or ""
                et = data.get("end", {})
                et_val = et.get("dateTime") or et.get("date") or ""
                return CalendarEvent(
                    event_id=event_id,
                    calendar_id=calendar_id,
                    summary=data.get("summary", ""),
                    start_time=st_val,
                    end_time=et_val,
                    html_link=data.get("htmlLink") or data.get("display_url") or "",
                    status=data.get("status", "confirmed"),
                    location=data.get("location", ""),
                    description=data.get("description", ""),
                    attendees=tuple(a.get("email", "") for a in data.get("attendees", []) if isinstance(a, dict) and a.get("email")),
                )

        event = self.google_client.get_event(token_data, calendar_id, event_id)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="get_event",
            target_id=event_id,
            details={"calendar_id": calendar_id},
        )
        return event

    def delete_event(
        self,
        caller: Any,
        event_id: str,
        calendar_id: str = "primary",
    ) -> bool:
        token_data = self.token_resolver(caller.principal_id)
        access_token = token_data.get("access_token", "")
        if isinstance(access_token, str) and (access_token.startswith("ca_") or "composio" in access_token):
            from tools.composio.calendar_tools import composio_calendar_delete_event
            user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None) or getattr(caller, "principal_id", "")
            account_email = token_data.get("account_email")
            c_res = composio_calendar_delete_event(user_id, event_id=event_id, calendar_id=calendar_id, account_email=account_email)
            deleted = c_res.get("status") == "success"
            self.store.record_audit(
                principal_id=caller.principal_id,
                action="delete_event",
                target_id=event_id,
                details={"calendar_id": calendar_id, "deleted": deleted},
            )
            return deleted

        deleted = self.google_client.delete_event(token_data, calendar_id, event_id)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="delete_event",
            target_id=event_id,
            details={"calendar_id": calendar_id, "deleted": deleted},
        )
        return deleted

    def status(self, caller: Any) -> Dict[str, Any]:
        conn = self.store.get_connection_by_principal(caller.principal_id)
        if not conn:
            return {
                "ok": True,
                "status": "unconnected",
                "principal_id": caller.principal_id,
                "message": "No Google Calendar connected. Use /connect_calendar to authorize.",
            }
        return {
            "ok": True,
            "status": conn.status.value,
            "principal_id": caller.principal_id,
            "email": conn.email,
            "calendar_id": conn.calendar_id,
            "calendar_name": conn.calendar_name,
        }
