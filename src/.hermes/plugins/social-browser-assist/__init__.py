from __future__ import annotations

from functools import partial
import os
from pathlib import Path
import sys
from typing import Any
from types import ModuleType


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

import importlib.util
_namespace = sys.modules.setdefault(
    "hermes_social_browser_assist", ModuleType("hermes_social_browser_assist")
)
_namespace.__path__ = [str(_PLUGIN_DIR)]


def _load_plugin_module(name: str):
    qualified = f"hermes_social_browser_assist.{name}"
    module = sys.modules.get(qualified)
    if module is not None:
        return module
    path = _PLUGIN_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"social_plugin_module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_caller = _load_plugin_module("social_caller")
_guard = _load_plugin_module("social_guard")
_client = _load_plugin_module("social_client")
_tools = _load_plugin_module("social_plugin_tools")
_schemas = _load_plugin_module("social_schemas")

get_default_client = _client.get_default_client
SocialBrowserTools = _guard.SocialBrowserTools
handle_connection_status = _tools.handle_connection_status
SOCIAL_CONNECTION_STATUS_SCHEMA = _schemas.SOCIAL_CONNECTION_STATUS_SCHEMA


def register(ctx: Any) -> SocialBrowserTools:
    guard = SocialBrowserTools()
    client = get_default_client()
    registry = guard.registry
    ctx.register_tool(
        name="social_connection_status",
        toolset="social_browser_assist",
        schema=SOCIAL_CONNECTION_STATUS_SCHEMA,
        handler=partial(
            handle_connection_status, client=client, registry=registry
        ),
        description=(
            "Check official social connection status for this Telegram caller; "
            "personal Facebook publishing is unsupported."
        ),
    )
    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
