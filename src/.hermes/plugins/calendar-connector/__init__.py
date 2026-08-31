from __future__ import annotations

from functools import partial
import os
from pathlib import Path
import sys
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC = _PLUGIN_DIR.parents[2]
for candidate in (
    Path(os.environ.get("HERMES_PROJECT_SRC", "")),
    Path(os.environ.get("HERMES_SRC_DIR", "")),
    _SRC,
    Path.cwd(),
):
    if candidate.is_dir() and (candidate / "tools/calendar").is_dir():
        resolved = str(candidate.resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        break

from client import get_default_client
from guard import CalendarToolsGuard
from plugin_tools import (
    handle_calendar_confirm_event,
    handle_calendar_create_draft_event,
    handle_calendar_find_free_slots,
    handle_calendar_list_events,
    handle_calendar_status,
)
from schemas import (
    CALENDAR_CONFIRM_EVENT_SCHEMA,
    CALENDAR_CREATE_DRAFT_EVENT_SCHEMA,
    CALENDAR_FIND_FREE_SLOTS_SCHEMA,
    CALENDAR_LIST_EVENTS_SCHEMA,
    CALENDAR_STATUS_SCHEMA,
)


def register(ctx: Any) -> CalendarToolsGuard:
    guard = CalendarToolsGuard()
    client = get_default_client()
    registry = guard.registry

    ctx.register_tool(
        name="calendar_list_events",
        toolset="calendar_connector",
        schema=CALENDAR_LIST_EVENTS_SCHEMA,
        handler=partial(handle_calendar_list_events, client=client, registry=registry),
        description="List upcoming Google Calendar events for the user.",
    )
    ctx.register_tool(
        name="calendar_find_free_slots",
        toolset="calendar_connector",
        schema=CALENDAR_FIND_FREE_SLOTS_SCHEMA,
        handler=partial(handle_calendar_find_free_slots, client=client, registry=registry),
        description="Find available meeting slots within working hours.",
    )
    ctx.register_tool(
        name="calendar_create_draft_event",
        toolset="calendar_connector",
        schema=CALENDAR_CREATE_DRAFT_EVENT_SCHEMA,
        handler=partial(handle_calendar_create_draft_event, client=client, registry=registry),
        description="Stage a new calendar event draft (Tier 2).",
    )
    ctx.register_tool(
        name="calendar_confirm_event",
        toolset="calendar_connector",
        schema=CALENDAR_CONFIRM_EVENT_SCHEMA,
        handler=partial(handle_calendar_confirm_event, client=client, registry=registry),
        description="Commit a previously staged event draft to Google Calendar.",
    )
    ctx.register_tool(
        name="calendar_status",
        toolset="calendar_connector",
        schema=CALENDAR_STATUS_SCHEMA,
        handler=partial(handle_calendar_status, client=client, registry=registry),
        description="Check Google Calendar connection status.",
    )

    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
