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
    _PLUGIN_DIR.parents[2],
    Path("C:/Hermes-Business-Agent/src"),
    Path.cwd() / "src",
    Path.cwd(),
):
    try:
        if (
            candidate
            and candidate.is_dir()
            and (candidate / "tools" / "tiktok").is_dir()
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
from tiktok_client_plugin import get_default_client
from tiktok_guard import TikTokToolsGuard
from tiktok_plugin_tools import (
    handle_tiktok_create_draft_post,
    handle_tiktok_creator_info,
    handle_tiktok_post_status,
    handle_tiktok_publish_video,
)
from tiktok_schemas import (
    TIKTOK_CREATE_DRAFT_POST_SCHEMA,
    TIKTOK_CREATOR_INFO_SCHEMA,
    TIKTOK_POST_STATUS_SCHEMA,
    TIKTOK_PUBLISH_VIDEO_SCHEMA,
)


def register(ctx: Any) -> TikTokToolsGuard:
    guard = TikTokToolsGuard()
    client = get_default_client()
    registry = guard.registry

    ctx.register_tool(
        name="tiktok_creator_info",
        toolset="tiktok_connector",
        schema=TIKTOK_CREATOR_INFO_SCHEMA,
        handler=partial(handle_tiktok_creator_info, client=client, registry=registry),
        description="Inspect TikTok creator account information and allowed privacy settings.",
    )
    ctx.register_tool(
        name="tiktok_create_draft_post",
        toolset="tiktok_connector",
        schema=TIKTOK_CREATE_DRAFT_POST_SCHEMA,
        handler=partial(handle_tiktok_create_draft_post, client=client, registry=registry),
        description="Stage a new TikTok video post draft with caption and privacy settings (Tier 2).",
    )
    ctx.register_tool(
        name="tiktok_publish_video",
        toolset="tiktok_connector",
        schema=TIKTOK_PUBLISH_VIDEO_SCHEMA,
        handler=partial(handle_tiktok_publish_video, client=client, registry=registry),
        description="Publish a staged draft to TikTok via Content Posting API.",
    )
    ctx.register_tool(
        name="tiktok_post_status",
        toolset="tiktok_connector",
        schema=TIKTOK_POST_STATUS_SCHEMA,
        handler=partial(handle_tiktok_post_status, client=client, registry=registry),
        description="Query the publishing and processing status of a TikTok post.",
    )

    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
