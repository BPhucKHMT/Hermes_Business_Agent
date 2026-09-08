from __future__ import annotations

from dataclasses import asdict, is_dataclass
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CalendarConnectorClient:
    def __init__(self, service_factory: Callable[[], Any] | None = None) -> None:
        self._service_factory = service_factory
        self._service: Any = None
        self._lock = Lock()

    @property
    def service(self) -> Any:
        """Expose the local store for guard checks; provider calls use the bridge."""
        with self._lock:
            if self._service is None:
                factory = self._service_factory
                if factory is None:
                    from tools.calendar.cli import build_service

                    factory = build_service
                self._service = factory()
            return self._service

    @staticmethod
    def _principal(caller: Any) -> str:
        principal_id = str(getattr(caller, "principal_id", "")).strip()
        if not principal_id:
            raise LookupError("missing_caller_context")
        return principal_id

    @staticmethod
    def _call_google(
        operation: str,
        principal_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        try:
            from tools.composio.bridge import call_google
            return call_google(operation, principal_id, params)
        except (ImportError, ModuleNotFoundError):
            pass
        import importlib.util, sys
        for candidate in (
            Path(os.environ.get("HERMES_PROJECT_SRC", "")),
            Path("C:/Hermes-Business-Agent/src"),
            Path.cwd() / "src",
            Path.cwd(),
        ):
            target = candidate / "tools" / "composio" / "bridge.py"
            if target.is_file():
                src_dir = str(candidate.resolve())
                if src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
                try:
                    import tools
                    tools_dir = str((candidate / "tools").resolve())
                    if hasattr(tools, "__path__") and tools_dir not in tools.__path__:
                        tools.__path__.insert(0, tools_dir)
                except Exception:
                    pass
                spec = importlib.util.spec_from_file_location("tools.composio.bridge", str(target))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules["tools.composio.bridge"] = mod
                    spec.loader.exec_module(mod)
                    return mod.call_google(operation, principal_id, params)
        raise RuntimeError("call_google bridge unavailable; run python src/setup_local.py --local")

    def list_events(
        self,
        caller: Any,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 20,
        calendar_id: str = "primary",
        account_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._service_factory is not None:
            events = self.service.list_events(
                caller=caller,
                time_min=time_min,
                time_max=time_max,
                limit=limit,
                calendar_id=calendar_id,
                account_email=account_email,
            )
            events = [asdict(e) if is_dataclass(e) else e for e in events]
            return {"ok": True, "result": {"events": events, "count": len(events)}}
        principal_id = self._principal(caller)
        events = self._call_google(
            "calendar.list_events",
            principal_id,
            {
                "time_min": time_min,
                "time_max": time_max,
                "limit": limit,
                "calendar_id": calendar_id,
                "account_email": account_email,
            },
        )
        if not isinstance(events, list):
            raise RuntimeError("calendar_list_events_invalid_result")
        return {"ok": True, "result": {"events": events, "count": len(events)}}

    def find_free_slots(
        self,
        caller: Any,
        date_str: str,
        duration_minutes: int = 30,
        calendar_id: str = "primary",
        account_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._service_factory is not None:
            slots = self.service.find_free_slots(
                caller=caller,
                date_str=date_str,
                duration_minutes=duration_minutes,
                calendar_id=calendar_id,
                account_email=account_email,
            )
            slots = [asdict(s) if is_dataclass(s) else s for s in slots]
            return {
                "ok": True,
                "result": {"slots": slots, "count": len(slots), "date": date_str},
            }
        principal_id = self._principal(caller)
        slots = self._call_google(
            "calendar.find_free_slots",
            principal_id,
            {
                "date_str": date_str,
                "duration_minutes": duration_minutes,
                "calendar_id": calendar_id,
                "account_email": account_email,
            },
        )
        if not isinstance(slots, list):
            raise RuntimeError("calendar_free_slots_invalid_result")
        return {
            "ok": True,
            "result": {"slots": slots, "count": len(slots), "date": date_str},
        }

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
    ) -> Dict[str, Any]:
        if self._service_factory is not None:
            draft = self.service.create_draft_event(
                caller=caller,
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                location=location,
                description=description,
                attendees=attendees,
                calendar_id=calendar_id,
                account_email=account_email,
            )
            if is_dataclass(draft):
                draft = asdict(draft)
            return {
                "ok": True,
                "result": {
                    "draft": draft,
                    "action_required": "Please review details and invoke calendar_confirm_event with draft_id to commit to your calendar.",
                },
            }
        principal_id = self._principal(caller)
        draft = self._call_google(
            "calendar.create_draft_event",
            principal_id,
            {
                "summary": summary,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "description": description,
                "attendees": list(attendees),
                "calendar_id": calendar_id,
                "account_email": account_email,
            },
        )
        if is_dataclass(draft):
            draft = asdict(draft)
        elif not isinstance(draft, dict):
            raise RuntimeError("calendar_create_draft_invalid_result")
        return {
            "ok": True,
            "result": {
                "draft": draft,
                "action_required": "Please review details and invoke calendar_confirm_event with draft_id to commit to your calendar.",
            },
        }

    def confirm_event(self, caller: Any, draft_id: str) -> Dict[str, Any]:
        if self._service_factory is not None:
            event = self.service.confirm_event(caller=caller, draft_id=draft_id)
            if is_dataclass(event):
                event = asdict(event)
            return {"ok": True, "result": {"event": event, "confirmed": True}}
        principal_id = self._principal(caller)
        event = self._call_google(
            "calendar.confirm_event",
            principal_id,
            {"draft_id": draft_id},
        )
        if is_dataclass(event):
            event = asdict(event)
        elif not isinstance(event, dict):
            raise RuntimeError("calendar_confirm_event_invalid_result")
        return {"ok": True, "result": {"event": event, "confirmed": True}}

    def status(self, caller: Any) -> Dict[str, Any]:
        principal_id = self._principal(caller)
        status = self._call_google("calendar.status", principal_id)
        if not isinstance(status, dict):
            raise RuntimeError("calendar_status_invalid_result")
        return status

    def start_oauth(self, caller: Any) -> Dict[str, Any]:
        principal_id = self._principal(caller)
        try:
            url = self._call_google(
                "initiate_google_connection",
                principal_id,
                {"toolkit": "googlecalendar"},
            )
            if not isinstance(url, str) or not url:
                raise RuntimeError("oauth_url_missing")
            return {
                "ok": True,
                "result": {
                    "authorization_url": url,
                    "request_id": f"composio-{principal_id}",
                },
            }
        except Exception as exc:
            return {"ok": False, "error": {"code": "oauth_start_failed", "message": str(exc)}}

    def disconnect(self, caller: Any) -> Dict[str, Any]:
        principal_id = self._principal(caller)
        try:
            self._call_google("disconnect_user", principal_id, {"app": "googlecalendar"})
        except Exception as exc:
            logger.warning("Failed to revoke Composio connection for principal %s: %s", principal_id, exc)
        with self.service.store._connect() as conn:
            conn.execute("DELETE FROM calendar_connections WHERE principal_id = ?;", (principal_id,))
        return {"ok": True, "result": {"disconnected": True}}


_default_client: Optional[CalendarConnectorClient] = None
_default_lock = Lock()


def get_default_client() -> CalendarConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = CalendarConnectorClient()
        return _default_client
