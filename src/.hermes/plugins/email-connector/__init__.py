"""Generic multi-user email connector plugin for Hermes Agent."""

from __future__ import annotations

from functools import partial
import logging
import sys
from pathlib import Path
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
            and (candidate / "tools" / "email").is_dir()
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

from client import get_default_client
from commands import (
    handle_connect_gmail,
    handle_disconnect_gmail,
    handle_email_grant,
    handle_mail_status,
    handle_share_mailbox,
)
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

_oauth_server = None
_oauth_thread = None


def _start_oauth_server_background(service: Any) -> None:
    global _oauth_server, _oauth_thread
    if _oauth_server is not None:
        return
    import os
    import threading
    port = int(os.environ.get("EMAIL_CONNECTOR_PORT", "8766"))
    host = os.environ.get("EMAIL_CONNECTOR_HOST", "0.0.0.0")
    try:
        from tools.email.service import create_http_server
        _oauth_server = create_http_server(service, host=host, port=port)
        _oauth_thread = threading.Thread(
            target=_oauth_server.serve_forever, daemon=True, name="gmail-oauth-listener"
        )
        _oauth_thread.start()
        logger.info("Started background Gmail OAuth callback server on %s:%d", host, port)
    except Exception as exc:
        logger.warning("Could not start background OAuth callback server on %s:%d: %s", host, port, exc)


def register(ctx: Any) -> PersonalGmailTools:
    guard = PersonalGmailTools()
    client = get_default_client()
    registry = guard.registry

    svc = getattr(client, "_service", None)
    if svc is not None:
        _start_oauth_server_background(svc)
    # 1. Register tools
    ctx.register_tool(
        name="email_search",
        toolset="email_connector",
        schema=EMAIL_SEARCH_SCHEMA,
        handler=partial(handle_email_search, client=client, registry=registry),
        description="Search accessible Gmail threads for the authenticated user.",
    )
    ctx.register_tool(
        name="email_get_thread",
        toolset="email_connector",
        schema=EMAIL_GET_THREAD_SCHEMA,
        handler=partial(handle_email_get_thread, client=client, registry=registry),
        description="Retrieve full message contents of a specific Gmail thread.",
    )
    ctx.register_tool(
        name="email_connection_status",
        toolset="email_connector",
        schema=EMAIL_CONNECTION_STATUS_SCHEMA,
        handler=partial(
            handle_email_connection_status, client=client, registry=registry
        ),
        description="Check status of connected Gmail mailboxes.",
    )

    # 2. Register commands (support both gmail and email/mail aliases)
    for cmd_name in (
        "connect_google",
        "connect-google",
        "google_connect",
        "google-connect",
        "connect_gmail",
        "connect-gmail",
        "connect_email",
        "connect-email",
        "connect_mail",
        "connect-mail",
    ):
        ctx.register_command(
            cmd_name,
            partial(handle_connect_gmail, client=client, registry=registry),
            description="Connect a Google account (Gmail, Calendar, YouTube)",
        )
    for cmd_name in ("mail_status", "mail-status", "email_status", "email-status"):
        ctx.register_command(
            cmd_name,
            partial(handle_mail_status, client=client, registry=registry),
            description="Check email connection status",
        )
    for cmd_name in (
        "disconnect_gmail",
        "disconnect-gmail",
        "disconnect_email",
        "disconnect-email",
    ):
        ctx.register_command(
            cmd_name,
            partial(handle_disconnect_gmail, client=client, registry=registry),
            description="Disconnect a connected Gmail account",
        )
    for cmd_name in ("share_mailbox", "share-mailbox"):
        ctx.register_command(
            cmd_name,
            partial(handle_share_mailbox, client=client, registry=registry),
            description="Propose sharing a mailbox with a Telegram destination",
        )
    for cmd_name in ("email_grant", "email-grant"):
        ctx.register_command(
            cmd_name,
            partial(handle_email_grant, client=client, registry=registry),
            description="Approve or deny a mailbox grant as an operator",
        )

    # One guard/registry is owned by this plugin registration; caller state is
    # scoped to host execution contexts by CallerContextRegistry.
    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
