from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from tools.calendar.contracts import (
    CalendarEvent,
    EventDraft,
    EventDraftStatus,
    FreeSlot,
    compute_draft_idempotency_key,
)
from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import CalendarPolicy
from tools.calendar.store import CalendarStore
import tools.composio.auth as composio_auth
import tools.composio.calendar_tools as composio_calendar
logger = logging.getLogger(__name__)


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

    @staticmethod
    def _principal(caller: Any) -> str:
        principal_id = getattr(caller, "principal_id", "")
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id_required")
        return principal_id.strip()

    @staticmethod
    def _uses_composio(token_data: Dict[str, Any]) -> bool:
        provider = str(token_data.get("provider", "")).casefold()
        access_token = token_data.get("access_token")
        return bool(
            provider == "composio"
            or token_data.get("composio") is True
            or token_data.get("account_id")
            or token_data.get("account_email")
            or (
                isinstance(access_token, str)
                and (access_token.startswith("ca_") or "composio" in access_token.casefold())
            )
        )

    @staticmethod
    def _normalize_account(account_email: Optional[str]) -> Optional[str]:
        if account_email is None:
            return None
        normalized = account_email.strip().casefold()
        return normalized or None

    @staticmethod
    def _normalize_payload(data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        nested = data.get("response_data")
        if isinstance(nested, dict):
            merged = dict(nested)
            for key, value in data.items():
                if key != "response_data":
                    merged.setdefault(key, value)
            return merged
        return data

    @classmethod
    def _event_from_payload(
        cls,
        data: Dict[str, Any],
        calendar_id: str,
        *,
        require_id: bool = True,
    ) -> CalendarEvent:
        payload = cls._normalize_payload(data)
        event_id = str(payload.get("id") or payload.get("event_id") or "").strip()
        if require_id and not event_id:
            raise ValueError("provider_event_id_missing")

        start = payload.get("start")
        end = payload.get("end")
        start_time = ""
        end_time = ""
        if isinstance(start, dict):
            start_time = str(start.get("dateTime") or start.get("date") or "")
        if isinstance(end, dict):
            end_time = str(end.get("dateTime") or end.get("date") or "")
        start_time = start_time or str(
            payload.get("start_time") or payload.get("start_datetime") or ""
        )
        end_time = end_time or str(
            payload.get("end_time") or payload.get("end_datetime") or ""
        )
        attendees = payload.get("attendees", [])
        attendee_emails = tuple(
            str(item.get("email", ""))
            for item in attendees
            if isinstance(item, dict) and item.get("email")
        )
        return CalendarEvent(
            event_id=event_id,
            calendar_id=str(payload.get("calendarId") or payload.get("calendar_id") or calendar_id),
            summary=str(payload.get("summary", "")),
            description=str(payload.get("description", "")),
            location=str(payload.get("location", "")),
            start_time=start_time,
            end_time=end_time,
            html_link=str(payload.get("htmlLink") or payload.get("display_url") or ""),
            status=str(payload.get("status", "confirmed")),
            attendees=attendee_emails,
            is_all_day=bool(
                isinstance(start, dict) and start.get("date") and not start.get("dateTime")
            ),
        )

    @staticmethod
    def _same_time(expected: str, observed: str) -> bool:
        if not expected or not observed:
            return False
        try:
            expected_dt = datetime.fromisoformat(expected.replace("Z", "+00:00"))
            observed_dt = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError:
            return expected.strip() == observed.strip()
        if expected_dt.tzinfo is None:
            expected_dt = expected_dt.replace(tzinfo=timezone.utc)
        if observed_dt.tzinfo is None:
            observed_dt = observed_dt.replace(tzinfo=timezone.utc)
        return expected_dt.astimezone(timezone.utc) == observed_dt.astimezone(timezone.utc)

    @classmethod
    def _validate_event(
        cls,
        event: CalendarEvent,
        draft: EventDraft,
        expected_event_id: str,
    ) -> None:
        if event.event_id != expected_event_id:
            raise RuntimeError("provider_event_id_mismatch")
        if event.calendar_id != draft.calendar_id:
            raise RuntimeError("provider_calendar_id_mismatch")
        if not cls._same_time(draft.start_time, event.start_time):
            raise RuntimeError("provider_start_time_mismatch")
        if not cls._same_time(draft.end_time, event.end_time):
            raise RuntimeError("provider_end_time_mismatch")

    def _default_token_resolver(self, principal_id: str) -> Dict[str, Any]:
        try:
            connections = composio_auth.list_user_connections(principal_id)
            for connection in connections:
                if str(connection.get("status", "")).upper() == "ACTIVE":
                    return {
                        "provider": "composio",
                        "account_id": connection.get("id"),
                        "account_email": self._normalize_account(connection.get("email")),
                    }
        except Exception as exc:
            logger.debug("Failed resolving Composio connections for %s: %s", principal_id, exc)

        connection = self.store.get_connection_by_principal(principal_id)
        if connection:
            return {
                "provider": "composio",
                "account_id": connection.connection_id,
                "account_email": self._normalize_account(connection.email),
            }
        return {"access_token": ""}

    def _composio_account_for_draft(self, principal_id: str, draft: EventDraft) -> str:
        if draft.account_email:
            return draft.account_email
        emails = composio_auth.get_user_emails(principal_id)
        unique = {email.casefold(): email for email in emails.values() if email}
        if len(unique) != 1:
            raise ValueError("draft_account_target_required")
        account_email = next(iter(unique.values())).casefold()
        self.store.bind_draft_account(draft.draft_id, account_email)
        return account_email

    @staticmethod
    def _composio_error(response: Dict[str, Any], fallback: str) -> str:
        message = response.get("message") or response.get("error") or fallback
        return str(message)

    def _readback_composio(
        self,
        principal_id: str,
        draft: EventDraft,
        account_email: str,
        event_id: str,
    ) -> CalendarEvent:
        response = composio_calendar.composio_calendar_get_event(
            principal_id,
            event_id=event_id,
            calendar_id=draft.calendar_id,
            account_email=account_email,
        )
        if response.get("status") != "success":
            raise RuntimeError(self._composio_error(response, "provider_event_readback_failed"))
        active_account = self._normalize_account(response.get("active_account"))
        if active_account and active_account != account_email:
            raise RuntimeError("provider_account_mismatch")
        event = self._event_from_payload(response.get("data", {}), draft.calendar_id)
        self._validate_event(event, draft, event_id)
        return event

    def _readback_google(
        self,
        token_data: Dict[str, Any],
        draft: EventDraft,
        event_id: str,
    ) -> CalendarEvent:
        event = self.google_client.get_event(token_data, draft.calendar_id, event_id)
        self._validate_event(event, draft, event_id)
        return event

    def list_events(
        self,
        caller: Any,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 20,
        calendar_id: str = "primary",
        account_email: Optional[str] = None,
    ) -> List[CalendarEvent]:
        principal_id = self._principal(caller)
        token_data = self.token_resolver(principal_id)
        limit = min(max(1, limit), self.policy.max_list_results)
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        selected_account = self._normalize_account(account_email) or self._normalize_account(
            token_data.get("account_email")
        )
        if self._uses_composio(token_data):
            response = composio_calendar.composio_calendar_list_events(
                principal_id,
                calendar_id=calendar_id,
                account_email=selected_account,
                time_min=time_min,
                time_max=time_max,
                limit=limit,
            )
            if response.get("status") != "success":
                raise RuntimeError(self._composio_error(response, "composio_list_events_failed"))
            data = self._normalize_payload(response.get("data", {}))
            items = data.get("items", []) if isinstance(data, dict) else []
            events = [self._event_from_payload(item, calendar_id, require_id=False) for item in items]
        else:
            events = self.google_client.list_events(
                token_data=token_data,
                calendar_id=calendar_id,
                time_min=time_min,
                time_max=time_max,
                max_results=limit,
            )

        self.store.record_audit(
            principal_id=principal_id,
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
        account_email: Optional[str] = None,
        timezone_str: Optional[str] = None,
        working_hours_start: Optional[str] = None,
        working_hours_end: Optional[str] = None,
    ) -> List[FreeSlot]:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if duration_minutes <= 0:
            raise ValueError("duration_minutes_must_be_positive")
        working_start = working_hours_start or self.policy.working_hours.start
        working_end = working_hours_end or self.policy.working_hours.end
        wh_start_t = datetime.strptime(working_start, "%H:%M").time()
        wh_end_t = datetime.strptime(working_end, "%H:%M").time()

        try:
            tz = ZoneInfo(timezone_str or self.policy.default_timezone)
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
            account_email=account_email,
        )

        busy_intervals = []
        for event in events:
            if event.is_all_day:
                continue
            try:
                event_start = datetime.fromisoformat(event.start_time.replace("Z", "+00:00"))
                event_end = datetime.fromisoformat(event.end_time.replace("Z", "+00:00"))
                event_start = max(event_start, day_start)
                event_end = min(event_end, day_end)
                if event_end > event_start:
                    busy_intervals.append((event_start, event_end))
            except (TypeError, ValueError):
                continue

        busy_intervals.sort(key=lambda interval: interval[0])
        merged_busy: list[tuple[datetime, datetime]] = []
        for start, end in busy_intervals:
            if not merged_busy or start > merged_busy[-1][1]:
                merged_busy.append((start, end))
            else:
                merged_busy[-1] = (merged_busy[-1][0], max(merged_busy[-1][1], end))

        free_slots: List[FreeSlot] = []
        cursor = day_start
        for busy_start, busy_end in merged_busy:
            if busy_start > cursor:
                self._append_slot(free_slots, cursor, busy_start, duration_minutes)
            cursor = max(cursor, busy_end)
        if cursor < day_end:
            self._append_slot(free_slots, cursor, day_end, duration_minutes)
        return free_slots

    @staticmethod
    def _append_slot(
        slots: List[FreeSlot],
        start: datetime,
        end: datetime,
        requested_duration: int,
    ) -> None:
        duration = int((end - start).total_seconds() / 60)
        if duration >= requested_duration:
            slots.append(
                FreeSlot(
                    start_time=start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    end_time=end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    duration_minutes=duration,
                )
            )

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
        principal_id = self._principal(caller)
        if not summary.strip():
            raise ValueError("summary_required")

        dt_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        self.policy.validate_event_time_window(dt_start, dt_end)
        self.policy.validate_lookahead(dt_start)

        normalized_account = self._normalize_account(account_email)
        token_data = self.token_resolver(principal_id)
        if self._uses_composio(token_data):
            _, resolved_email = composio_auth.resolve_account_target(principal_id, account_email)
            normalized_account = self._normalize_account(resolved_email)
        idempotency_key = compute_draft_idempotency_key(
            principal_id=principal_id,
            calendar_id=calendar_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            account_email=normalized_account,
        )
        draft = EventDraft(
            draft_id=f"drf-{uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            principal_id=principal_id,
            calendar_id=calendar_id,
            summary=summary.strip(),
            description=description.strip(),
            location=location.strip(),
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            status=EventDraftStatus.DRAFT,
            account_email=normalized_account,
        )
        persisted = self.store.create_or_get_draft(draft)
        self.store.record_audit(
            principal_id=principal_id,
            action="create_draft_event",
            target_id=persisted.draft_id,
            details={
                "summary": persisted.summary,
                "start_time": persisted.start_time,
                "end_time": persisted.end_time,
                "account_email": persisted.account_email,
            },
        )
        return persisted

    def confirm_event(self, caller: Any, draft_id: str) -> CalendarEvent:
        principal_id = self._principal(caller)
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise KeyError("draft_not_found")
        if draft.principal_id != principal_id:
            raise PermissionError("principal_not_authorized_for_draft")
        if draft.status not in (EventDraftStatus.DRAFT, EventDraftStatus.COMMITTED):
            raise ValueError(f"cannot_confirm_draft_in_status_{draft.status.value}")

        token_data = self.token_resolver(principal_id)
        use_composio = self._uses_composio(token_data)
        account_email = self._normalize_account(draft.account_email)
        if use_composio and not account_email:
            account_email = self._composio_account_for_draft(principal_id, draft)
            draft = self.store.get_draft(draft_id) or draft

        if draft.status == EventDraftStatus.COMMITTED:
            if not draft.committed_event_id:
                raise RuntimeError("committed_draft_missing_event_id")
            if use_composio:
                return self._readback_composio(
                    principal_id, draft, account_email or "", draft.committed_event_id
                )
            return self._readback_google(token_data, draft, draft.committed_event_id)

        if draft.committed_event_id:
            if use_composio:
                event = self._readback_composio(
                    principal_id, draft, account_email or "", draft.committed_event_id
                )
            else:
                event = self._readback_google(token_data, draft, draft.committed_event_id)
            self.store.transition_draft_status(
                draft_id=draft_id,
                from_status=EventDraftStatus.DRAFT,
                to_status=EventDraftStatus.COMMITTED,
                committed_event_id=draft.committed_event_id,
            )
            return event

        if use_composio:
            response = composio_calendar.composio_calendar_create_event(
                principal_id,
                summary=draft.summary,
                start_datetime=draft.start_time,
                end_datetime=draft.end_time,
                description=draft.description,
                location=draft.location,
                attendees=list(draft.attendees) if draft.attendees else None,
                calendar_id=draft.calendar_id,
                account_email=account_email,
            )
            if response.get("status") != "success":
                raise RuntimeError(self._composio_error(response, "composio_create_event_failed"))
            data = self._normalize_payload(response.get("data", {}))
            event_id = str(data.get("id") or data.get("event_id") or "").strip()
            if not event_id:
                raise RuntimeError("provider_event_id_missing")
            active_account = self._normalize_account(response.get("active_account"))
            if account_email and active_account and active_account != account_email:
                self.store.record_pending_event_id(draft_id, event_id)
                raise RuntimeError("provider_account_mismatch")
            self.store.record_pending_event_id(draft_id, event_id)
            event = self._readback_composio(principal_id, draft, account_email or "", event_id)
        else:
            created = self.google_client.create_event(
                token_data=token_data,
                calendar_id=draft.calendar_id,
                draft=draft,
            )
            if not created.event_id:
                raise RuntimeError("provider_event_id_missing")
            self.store.record_pending_event_id(draft_id, created.event_id)
            event = self._readback_google(token_data, draft, created.event_id)

        self.store.transition_draft_status(
            draft_id=draft_id,
            from_status=EventDraftStatus.DRAFT,
            to_status=EventDraftStatus.COMMITTED,
            committed_event_id=event.event_id,
        )
        self.store.record_audit(
            principal_id=principal_id,
            action="confirm_event",
            target_id=draft_id,
            details={"event_id": event.event_id, "html_link": event.html_link},
        )
        return event

    def get_event(
        self,
        caller: Any,
        event_id: str,
        calendar_id: str = "primary",
        account_email: Optional[str] = None,
    ) -> CalendarEvent:
        principal_id = self._principal(caller)
        token_data = self.token_resolver(principal_id)
        selected_account = self._normalize_account(account_email) or self._normalize_account(
            token_data.get("account_email")
        )
        if self._uses_composio(token_data):
            response = composio_calendar.composio_calendar_get_event(
                principal_id,
                event_id=event_id,
                calendar_id=calendar_id,
                account_email=selected_account,
            )
            if response.get("status") != "success":
                raise RuntimeError(self._composio_error(response, "composio_get_event_failed"))
            return self._event_from_payload(response.get("data", {}), calendar_id)

        event = self.google_client.get_event(token_data, calendar_id, event_id)
        self.store.record_audit(
            principal_id=principal_id,
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
        account_email: Optional[str] = None,
    ) -> bool:
        principal_id = self._principal(caller)
        token_data = self.token_resolver(principal_id)
        selected_account = self._normalize_account(account_email) or self._normalize_account(
            token_data.get("account_email")
        )
        if self._uses_composio(token_data):
            response = composio_calendar.composio_calendar_delete_event(
                principal_id,
                event_id=event_id,
                calendar_id=calendar_id,
                account_email=selected_account,
            )
            deleted = response.get("status") == "success"
        else:
            deleted = self.google_client.delete_event(token_data, calendar_id, event_id)
        self.store.record_audit(
            principal_id=principal_id,
            action="delete_event",
            target_id=event_id,
            details={"calendar_id": calendar_id, "deleted": deleted},
        )
        return deleted

    def status(self, caller: Any) -> Dict[str, Any]:
        principal_id = self._principal(caller)
        try:
            if any(
                composio_auth.check_connection_status(principal_id, app=app)
                for app in ("googlesuper", "googlecalendar", "gmail")
            ):
                account_emails = list(dict.fromkeys(composio_auth.get_user_emails(principal_id).values()))
                return {
                    "ok": True,
                    "status": "connected",
                    "principal_id": principal_id,
                    "connected_accounts": account_emails,
                }
        except Exception as exc:
            logger.debug("Composio status lookup failed for %s: %s", principal_id, exc)

        connection = self.store.get_connection_by_principal(principal_id)
        if not connection:
            return {
                "ok": True,
                "status": "unconnected",
                "principal_id": principal_id,
                "message": "No Google Calendar connected. Use /connect-google to authorize.",
            }
        return {
            "ok": True,
            "status": connection.status.value,
            "principal_id": principal_id,
            "email": connection.email,
            "calendar_id": connection.calendar_id,
            "calendar_name": connection.calendar_name,
        }
