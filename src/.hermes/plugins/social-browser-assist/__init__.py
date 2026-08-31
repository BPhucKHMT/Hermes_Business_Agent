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
    if candidate.is_dir() and (candidate / "tools/social_browser").is_dir():
        resolved = str(candidate.resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        break

from client import get_default_client
from guard import SocialBrowserTools
from plugin_tools import handle_prepare, handle_status, handle_verify
from schemas import SOCIAL_PREPARE_SCHEMA, SOCIAL_STATUS_SCHEMA, SOCIAL_VERIFY_SCHEMA


def register(ctx: Any) -> SocialBrowserTools:
    guard = SocialBrowserTools()
    client = get_default_client()
    registry = guard.registry
    ctx.register_tool(
        name="social_prepare_facebook_post",
        toolset="social_browser_assist",
        schema=SOCIAL_PREPARE_SCHEMA,
        handler=partial(handle_prepare, client=client, registry=registry),
        description="Prepare a Facebook post and stop before human Publish.",
    )
    ctx.register_tool(
        name="social_browser_status",
        toolset="social_browser_assist",
        schema=SOCIAL_STATUS_SCHEMA,
        handler=partial(handle_status, client=client, registry=registry),
        description="Read durable status for a social-browser preparation run.",
    )
    ctx.register_tool(
        name="social_verify_facebook_post",
        toolset="social_browser_assist",
        schema=SOCIAL_VERIFY_SCHEMA,
        handler=partial(handle_verify, client=client, registry=registry),
        description="Verify a Facebook post only after the human publishes it.",
    )
    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
