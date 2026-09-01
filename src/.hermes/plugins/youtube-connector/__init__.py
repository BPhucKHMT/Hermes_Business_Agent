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
            and (candidate / "tools" / "youtube").is_dir()
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
from youtube_client_plugin import get_default_client
from youtube_guard import YouTubeToolsGuard
from youtube_plugin_tools import (
    handle_youtube_channel_status,
    handle_youtube_create_draft_video,
    handle_youtube_list_videos,
    handle_youtube_update_video_metadata,
    handle_youtube_upload_video,
)
from youtube_schemas import (
    YOUTUBE_CHANNEL_STATUS_SCHEMA,
    YOUTUBE_CREATE_DRAFT_VIDEO_SCHEMA,
    YOUTUBE_LIST_VIDEOS_SCHEMA,
    YOUTUBE_UPDATE_METADATA_SCHEMA,
    YOUTUBE_UPLOAD_VIDEO_SCHEMA,
)


def register(ctx: Any) -> YouTubeToolsGuard:
    guard = YouTubeToolsGuard()
    client = get_default_client()
    registry = guard.registry

    ctx.register_tool(
        name="youtube_channel_status",
        toolset="youtube_connector",
        schema=YOUTUBE_CHANNEL_STATUS_SCHEMA,
        handler=partial(handle_youtube_channel_status, client=client, registry=registry),
        description="Check YouTube channel status, title, subscriber count, and video count.",
    )
    ctx.register_tool(
        name="youtube_list_videos",
        toolset="youtube_connector",
        schema=YOUTUBE_LIST_VIDEOS_SCHEMA,
        handler=partial(handle_youtube_list_videos, client=client, registry=registry),
        description="List recent channel videos.",
    )
    ctx.register_tool(
        name="youtube_create_draft_video",
        toolset="youtube_connector",
        schema=YOUTUBE_CREATE_DRAFT_VIDEO_SCHEMA,
        handler=partial(handle_youtube_create_draft_video, client=client, registry=registry),
        description="Stage a new video draft with metadata and file path (Tier 2).",
    )
    ctx.register_tool(
        name="youtube_upload_video",
        toolset="youtube_connector",
        schema=YOUTUBE_UPLOAD_VIDEO_SCHEMA,
        handler=partial(handle_youtube_upload_video, client=client, registry=registry),
        description="Upload an approved video draft to YouTube.",
    )
    ctx.register_tool(
        name="youtube_update_video_metadata",
        toolset="youtube_connector",
        schema=YOUTUBE_UPDATE_METADATA_SCHEMA,
        handler=partial(handle_youtube_update_video_metadata, client=client, registry=registry),
        description="Update metadata of an existing YouTube video.",
    )

    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
