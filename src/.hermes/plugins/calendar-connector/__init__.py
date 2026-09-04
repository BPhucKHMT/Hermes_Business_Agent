from __future__ import annotations

from functools import partial
import os
from pathlib import Path
import sys
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import os

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
from calendar_client import get_default_client
from calendar_commands import (
    handle_calendar_status_cmd,
    handle_connect_calendar,
    handle_disconnect_calendar,
)
from calendar_guard import CalendarToolsGuard
from calendar_plugin_tools import (
    handle_calendar_confirm_event,
    handle_calendar_create_draft_event,
    handle_calendar_create_event,
    handle_calendar_delete_event,
    handle_calendar_find_free_slots,
    handle_calendar_get_event,
    handle_calendar_list_events,
    handle_calendar_status,
    handle_calendar_update_event,
)
from calendar_schemas import (
    CALENDAR_CONFIRM_EVENT_SCHEMA,
    CALENDAR_CREATE_DRAFT_EVENT_SCHEMA,
    CALENDAR_CREATE_EVENT_SCHEMA,
    CALENDAR_DELETE_EVENT_SCHEMA,
    CALENDAR_FIND_FREE_SLOTS_SCHEMA,
    CALENDAR_GET_EVENT_SCHEMA,
    CALENDAR_LIST_EVENTS_SCHEMA,
    CALENDAR_STATUS_SCHEMA,
    CALENDAR_UPDATE_EVENT_SCHEMA,
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
    ctx.register_tool(
        name="calendar_get_event",
        toolset="calendar_connector",
        schema=CALENDAR_GET_EVENT_SCHEMA,
        handler=partial(handle_calendar_get_event, client=client, registry=registry),
        description="Retrieve details of a single Google Calendar event by ID.",
    )
    ctx.register_tool(
        name="calendar_create_event",
        toolset="calendar_connector",
        schema=CALENDAR_CREATE_EVENT_SCHEMA,
        handler=partial(handle_calendar_create_event, client=client, registry=registry),
        description="Directly create an event on Google Calendar without staging a draft.",
    )
    ctx.register_tool(
        name="calendar_update_event",
        toolset="calendar_connector",
        schema=CALENDAR_UPDATE_EVENT_SCHEMA,
        handler=partial(handle_calendar_update_event, client=client, registry=registry),
        description="Reschedule or update specified fields of an existing Google Calendar event.",
    )
    ctx.register_tool(
        name="calendar_delete_event",
        toolset="calendar_connector",
        schema=CALENDAR_DELETE_EVENT_SCHEMA,
        handler=partial(handle_calendar_delete_event, client=client, registry=registry),
        description="Cancel and delete an event from Google Calendar.",
    )

    # Register slash commands
    for cmd in ("connect_google", "connect-google", "google_connect", "connect_calendar", "connect-calendar"):
        ctx.register_command(
            cmd,
            partial(handle_connect_calendar, client=client, registry=registry),
            description="Connect a Google Calendar account",
        )
    for cmd in ("calendar_status", "calendar-status"):
        ctx.register_command(
            cmd,
            partial(handle_calendar_status_cmd, client=client, registry=registry),
            description="Check calendar connection status",
        )
    for cmd in ("disconnect_calendar", "disconnect-calendar"):
        ctx.register_command(
            cmd,
            partial(handle_disconnect_calendar, client=client, registry=registry),
            description="Disconnect connected calendar",
        )

    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
