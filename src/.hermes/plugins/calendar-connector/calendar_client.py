from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import sys
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

for candidate in (
    Path(os.environ.get("HERMES_PROJECT_SRC", "")),
    Path(os.environ.get("HERMES_SRC_DIR", "")),
    Path.home() / "Hermes-Business-Agent" / "src",
    Path("/home/azureuser/Hermes-Business-Agent/src"),
    _PLUGIN_DIR.parents[2] / "Hermes-Business-Agent" / "src",
    _PLUGIN_DIR.parents[2],
    Path("C:/Hermes-Business-Agent/src"),
    Path.cwd() / "src",
    Path.cwd(),
):
    try:
        if (
            candidate
            and candidate.is_dir()
            and (candidate / "tools" / "calendar").is_dir()
        ):
            cand_str = str(candidate.resolve())
            if cand_str not in sys.path:
                sys.path.insert(0, cand_str)
            import tools

            tools_path_str = str((candidate / "tools").resolve())
            if tools_path_str not in tools.__path__:
                tools.__path__.insert(0, tools_path_str)
            break
    except Exception:
        continue
from tools.calendar.cli import build_service
from tools.calendar.service import CalendarService

class CalendarConnectorClient:
    def __init__(self, service_factory: Callable[[], CalendarService] = build_service) -> None:
        self._service_factory = service_factory
        self._service: Optional[CalendarService] = None
        self._lock = Lock()

    @property
    def service(self) -> CalendarService:
        with self._lock:
            if self._service is None:
                self._service = self._service_factory()
            return self._service

    def list_events(
        self,
        caller: Any,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 20,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        events = self.service.list_events(
            caller=caller,
            time_min=time_min,
            time_max=time_max,
            limit=limit,
            calendar_id=calendar_id,
        )
        return {"ok": True, "result": {"events": [asdict(ev) for ev in events], "count": len(events)}}

    def find_free_slots(
        self,
        caller: Any,
        date_str: str,
        duration_minutes: int = 30,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        slots = self.service.find_free_slots(
            caller=caller,
            date_str=date_str,
            duration_minutes=duration_minutes,
            calendar_id=calendar_id,
        )
        return {"ok": True, "result": {"slots": [asdict(s) for s in slots], "count": len(slots), "date": date_str}}

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
        return {
            "ok": True,
            "result": {
                "draft": asdict(draft),
                "action_required": "Please review details and invoke calendar_confirm_event with draft_id to commit to your calendar.",
            },
        }

    def confirm_event(self, caller: Any, draft_id: str) -> Dict[str, Any]:
        event = self.service.confirm_event(caller=caller, draft_id=draft_id)
        return {"ok": True, "result": {"event": asdict(event), "confirmed": True}}

    def status(self, caller: Any) -> Dict[str, Any]:
        return self.service.status(caller)
    def start_oauth(self, caller: Any) -> Dict[str, Any]:
        user_id = getattr(caller, "user_id", None) or getattr(caller, "chat_id", None)
        user_key = user_id or getattr(caller, "principal_id", "default")
        try:
            from tools.composio.auth import initiate_google_connection
            url = initiate_google_connection(user_key, toolkit="googlecalendar")
            return {"ok": True, "result": {"authorization_url": url, "request_id": f"composio-{user_key}"}}
        except Exception as exc:
            return {"ok": False, "error": {"code": "oauth_start_failed", "message": str(exc)}}
    def disconnect(self, caller: Any) -> Dict[str, Any]:
        with self.service.store._connect() as conn:
            conn.execute("DELETE FROM calendar_connections WHERE principal_id = ?;", (caller.principal_id,))
        return {"ok": True, "result": {"disconnected": True}}


_default_client: Optional[CalendarConnectorClient] = None
_default_lock = Lock()


def get_default_client() -> CalendarConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = CalendarConnectorClient()
        return _default_client
