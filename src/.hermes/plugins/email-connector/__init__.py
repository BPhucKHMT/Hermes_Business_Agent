"""Generic multi-user email connector plugin for Hermes Agent."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from caller import CallerContextRegistry, DM_REDIRECT_TEXT
from commands import handle_connect_gmail, handle_disconnect_gmail, handle_mail_status
from gmail_tools import PersonalGmailTools
from schemas import (
    EMAIL_CONNECTION_STATUS_SCHEMA,
    EMAIL_GET_THREAD_SCHEMA,
    EMAIL_SEARCH_SCHEMA,
)
from plugin_tools import (
    handle_email_connection_status,
    handle_email_get_thread,
    handle_email_search,
)

logger = logging.getLogger(__name__)

# Module-level default tools guard instance shared across hook lifecycle for this plugin instance
default_guard = PersonalGmailTools()


def register(ctx: Any) -> PersonalGmailTools:
    # 1. Register tools
    ctx.register_tool(
        name="email_search",
        toolset="email_connector",
        schema=EMAIL_SEARCH_SCHEMA,
        handler=handle_email_search,
        description="Search accessible Gmail threads for the authenticated user.",
    )
    ctx.register_tool(
        name="email_get_thread",
        toolset="email_connector",
        schema=EMAIL_GET_THREAD_SCHEMA,
        handler=handle_email_get_thread,
        description="Retrieve full message contents of a specific Gmail thread.",
    )
    ctx.register_tool(
        name="email_connection_status",
        toolset="email_connector",
        schema=EMAIL_CONNECTION_STATUS_SCHEMA,
        handler=handle_email_connection_status,
        description="Check status of connected Gmail mailboxes.",
    )

    # 2. Register commands
    ctx.register_command("connect_gmail", handle_connect_gmail, description="Connect a private Gmail account")
    ctx.register_command("mail_status", handle_mail_status, description="Check email connection status")
    ctx.register_command("disconnect_gmail", handle_disconnect_gmail, description="Disconnect a connected Gmail account")

    # 3. Register safety hooks using shared default_guard
    ctx.register_hook("pre_gateway_dispatch", default_guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", default_guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", default_guard.on_session_finalize)
    return default_guard
