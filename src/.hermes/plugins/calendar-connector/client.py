from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import sys
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC = _PLUGIN_DIR.parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

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


_default_client: Optional[CalendarConnectorClient] = None
_default_lock = Lock()


def get_default_client() -> CalendarConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = CalendarConnectorClient()
        return _default_client
