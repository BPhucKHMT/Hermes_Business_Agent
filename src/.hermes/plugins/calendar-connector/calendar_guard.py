from __future__ import annotations

import contextlib
import hashlib
import json
from typing import Any

from calendar_caller import CallerContextRegistry, DmOnlyError

CALENDAR_TOOL_NAMES = frozenset(
    {
        "calendar_list_events",
        "calendar_get_event",
        "calendar_create_event",
        "calendar_create_draft_event",
        "calendar_confirm_event",
        "calendar_update_event",
        "calendar_delete_event",
        "calendar_find_free_slots",
        "calendar_status",
    }
)


class CalendarToolsGuard:
    """Calendar caller protection and native staged-event approval."""

    def __init__(
        self,
        registry: CallerContextRegistry | None = None,
        client: Any = None,
    ) -> None:
        self.registry = registry or CallerContextRegistry()
        self._client = client

    def pre_gateway_dispatch(
        self,
        event: object,
        gateway: object = None,
        session_store: object = None,
        **kwargs: Any,
    ) -> None:
        del gateway, kwargs
        if session_store is not None:
            self.registry.set_session_store(session_store)
        with contextlib.suppress(DmOnlyError):
            self.registry.capture(event)

    def _draft_for(self, draft_id: str) -> Any:
        if self._client is None:
            return None
        service = getattr(self._client, "service", None)
        store = getattr(service, "store", None)
        if store is None:
            return None
        return store.get_draft(draft_id)

    @staticmethod
    def _rule_key(caller: Any, draft: Any) -> str:
        immutable = {
            "principal_id": str(caller.principal_id),
            "draft_id": str(draft.draft_id),
            "account_email": str(getattr(draft, "account_email", "") or "").casefold(),
            "calendar_id": str(draft.calendar_id),
            "summary": str(draft.summary),
            "description": str(draft.description),
            "location": str(draft.location),
            "start_time": str(draft.start_time),
            "end_time": str(draft.end_time),
            "attendees": sorted(str(address) for address in draft.attendees),
        }
        digest = hashlib.sha256(
            json.dumps(immutable, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"calendar_confirm:{digest}"

    def _confirm_directive(
        self,
        args: dict[str, Any] | None,
        caller: Any,
    ) -> dict[str, Any]:
        draft_id = str((args or {}).get("draft_id", "")).strip()
        try:
            draft = self._draft_for(draft_id)
        except Exception:  # noqa: BLE001 -- store failure must fail closed as a block
            return {"action": "block", "message": "calendar draft lookup unavailable"}
        if draft is None:
            return {"action": "block", "message": "calendar draft not found"}
        if str(getattr(draft, "principal_id", "")) != str(caller.principal_id):
            return {
                "action": "block",
                "message": "calendar draft belongs to another caller",
            }
        return {
            "action": "approve",
            "message": "Confirm this staged Google Calendar event.",
            "rule_key": self._rule_key(caller, draft),
        }

    def pre_tool_call(
        self,
        tool_name: str,
        _args: dict | None = None,
        task_id: str = "",
        session_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        del kwargs
        if tool_name not in CALENDAR_TOOL_NAMES:
            return None
        try:
            caller = self.registry.resolve_dm_tool(
                task_id=task_id, session_id=session_id
            )
        except DmOnlyError as error:
            return {"action": "block", "message": str(error)}
        except LookupError as error:
            return {"action": "block", "message": str(error)}
        if tool_name == "calendar_confirm_event":
            return self._confirm_directive(_args, caller)
        return None

    def on_session_finalize(
        self,
        session_id: str | None = None,
        platform: str = "",
        **kwargs: Any,
    ) -> None:
        del platform, kwargs
        if session_id:
            self.registry.forget_by_session_id(session_id)
