"""Read-only Gmail connector with explicit local-owner support."""

from __future__ import annotations

from functools import partial
import logging
import os
from pathlib import Path
import sys
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

for candidate in (
    Path(os.environ.get("HERMES_PROJECT_SRC", "")),
    Path(os.environ.get("HERMES_SRC_DIR", "")),
    _PLUGIN_DIR.resolve().parents[2],
    _PLUGIN_DIR.parents[2] / "Hermes-Business-Agent" / "src",
    _PLUGIN_DIR.parents[2],
    Path.home() / "Hermes-Business-Agent" / "src",
    Path.cwd() / "src",
    Path.cwd(),
):
    try:
        if candidate.is_dir() and (candidate / "tools" / "composio").is_dir():
            cand_str = str(candidate.resolve())
            if cand_str not in sys.path:
                sys.path.insert(0, cand_str)
            import tools

            tools_path_str = str((candidate / "tools").resolve())
            if tools_path_str not in tools.__path__:
                tools.__path__.insert(0, tools_path_str)
            break
    except (ImportError, OSError, ValueError):
        continue

try:
    from .client import get_default_client
    from .commands import (
        handle_connect_gmail,
        handle_disconnect_gmail,
        handle_email_grant,
        handle_mail_status,
        handle_share_mailbox,
    )
    from .gmail_tools import PersonalGmailTools
    from .plugin_tools import (
        handle_email_connection_status,
        handle_email_create_draft,
        handle_email_get_thread,
        handle_email_reply,
        handle_email_search,
        handle_email_send,
    )
    from .schemas import (
        EMAIL_CONNECTION_STATUS_SCHEMA,
        EMAIL_CREATE_DRAFT_SCHEMA,
        EMAIL_GET_THREAD_SCHEMA,
        EMAIL_REPLY_SCHEMA,
        EMAIL_SEARCH_SCHEMA,
        EMAIL_SEND_SCHEMA,
    )
    from .workspace_schemas import (
        GOOGLE_DOC_READ_SCHEMA,
        GOOGLE_DRIVE_FIND_SCHEMA,
        GOOGLE_FILE_READ_SCHEMA,
        GOOGLE_SHEET_READ_SCHEMA,
        GOOGLE_SLIDE_READ_SCHEMA,
    )
    from .workspace_tools import (
        handle_google_doc_read,
        handle_google_drive_find,
        handle_google_file_read,
        handle_google_sheet_read,
        handle_google_slide_read,
    )
except (ImportError, ValueError, KeyError):
    from client import get_default_client
    from commands import (
        handle_connect_gmail,
        handle_disconnect_gmail,
        handle_email_grant,
        handle_mail_status,
        handle_share_mailbox,
    )
    from gmail_tools import PersonalGmailTools
    from plugin_tools import (
        handle_email_connection_status,
        handle_email_create_draft,
        handle_email_get_thread,
        handle_email_reply,
        handle_email_search,
        handle_email_send,
    )
    from schemas import (
        EMAIL_CONNECTION_STATUS_SCHEMA,
        EMAIL_CREATE_DRAFT_SCHEMA,
        EMAIL_GET_THREAD_SCHEMA,
        EMAIL_REPLY_SCHEMA,
        EMAIL_SEARCH_SCHEMA,
        EMAIL_SEND_SCHEMA,
    )
    from workspace_schemas import (
        GOOGLE_DOC_READ_SCHEMA,
        GOOGLE_DRIVE_FIND_SCHEMA,
        GOOGLE_FILE_READ_SCHEMA,
        GOOGLE_SHEET_READ_SCHEMA,
        GOOGLE_SLIDE_READ_SCHEMA,
    )
    from workspace_tools import (
        handle_google_doc_read,
        handle_google_drive_find,
        handle_google_file_read,
        handle_google_sheet_read,
        handle_google_slide_read,
    )

logger = logging.getLogger(__name__)


def register(ctx: Any) -> PersonalGmailTools:
    guard = PersonalGmailTools()
    client = get_default_client()
    registry = guard.registry

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
            handle_email_connection_status,
            client=client,
            registry=registry,
        ),
        description="Check status of connected Gmail mailboxes.",
    )
    ctx.register_tool(
        name="email_send",
        toolset="email_connector",
        schema=EMAIL_SEND_SCHEMA,
        handler=partial(handle_email_send, client=client, registry=registry),
        description="Send an outbound email directly from the user's connected Gmail account.",
    )
    ctx.register_tool(
        name="email_create_draft",
        toolset="email_connector",
        schema=EMAIL_CREATE_DRAFT_SCHEMA,
        handler=partial(handle_email_create_draft, client=client, registry=registry),
        description="Create an email draft in the user's connected Gmail account without sending it immediately.",
    )
    ctx.register_tool(
        name="email_reply",
        toolset="email_connector",
        schema=EMAIL_REPLY_SCHEMA,
        handler=partial(handle_email_reply, client=client, registry=registry),
        description="Reply to an existing Gmail thread from the user's connected Gmail account.",
    )
    for schema, handler, description in (
        (
            GOOGLE_DRIVE_FIND_SCHEMA,
            handle_google_drive_find,
            "Search the user's Google Drive files and folders.",
        ),
        (
            GOOGLE_FILE_READ_SCHEMA,
            handle_google_file_read,
            "Read a Google resource by link or ID with the user's connected account.",
        ),
        (
            GOOGLE_DOC_READ_SCHEMA,
            handle_google_doc_read,
            "Read a Google Docs document's content.",
        ),
        (
            GOOGLE_SHEET_READ_SCHEMA,
            handle_google_sheet_read,
            "Read values from a Google Sheets spreadsheet.",
        ),
        (
            GOOGLE_SLIDE_READ_SCHEMA,
            handle_google_slide_read,
            "Read a Google Slides presentation's content.",
        ),
    ):
        ctx.register_tool(
            name=schema["name"],
            toolset="email_connector",
            schema=schema,
            handler=partial(handler, client=client, registry=registry),
            description=description,
        )

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
    for cmd_name in (
        "mail_status",
        "mail-status",
        "email_status",
        "email-status",
        "status_mail",
        "status-mail",
        "status_email",
        "status-email",
    ):
        ctx.register_command(
            cmd_name,
            partial(handle_mail_status, client=client, registry=registry),
            description="Check email connection status",
        )
    for cmd_name in (
        "disconnect_google",
        "disconnect-google",
        "google_disconnect",
        "google-disconnect",
        "disconnect_gmail",
        "disconnect-gmail",
        "disconnect_email",
        "disconnect-email",
    ):
        ctx.register_command(
            cmd_name,
            partial(handle_disconnect_gmail, client=client, registry=registry),
            description="Disconnect a connected Google account",
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

    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
