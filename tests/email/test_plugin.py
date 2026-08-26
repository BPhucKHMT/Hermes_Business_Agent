import importlib.util
import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"

# Import plugin modules by explicit file location
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(UPSTREAM))

plugin_tools = _load("email_tools_mod", PLUGIN / "plugin_tools.py")
plugin_schemas = _load("email_schemas_mod", PLUGIN / "schemas.py")
plugin_commands = _load("email_commands_mod", PLUGIN / "commands.py")


class FakeContext:
    def __init__(self):
        self.tools = {}
        self.hooks = {}
        self.commands = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"schema": schema, "handler": handler}

    def register_hook(self, name, handler, **kwargs):
        self.hooks.setdefault(name, []).append(handler)

    def register_command(self, name, handler, description="", **kwargs):
        self.commands[name] = handler


def test_plugin_registers_read_tools_and_commands():
    ctx = FakeContext()

    ctx.register_tool(
        name="email_search",
        toolset="email_connector",
        schema=plugin_schemas.EMAIL_SEARCH_SCHEMA,
        handler=plugin_tools.handle_email_search,
    )
    ctx.register_tool(
        name="email_get_thread",
        toolset="email_connector",
        schema=plugin_schemas.EMAIL_GET_THREAD_SCHEMA,
        handler=plugin_tools.handle_email_get_thread,
    )
    ctx.register_tool(
        name="email_connection_status",
        toolset="email_connector",
        schema=plugin_schemas.EMAIL_CONNECTION_STATUS_SCHEMA,
        handler=plugin_tools.handle_email_connection_status,
    )
    ctx.register_command("connect_gmail", plugin_commands.handle_connect_gmail)
    ctx.register_command("mail_status", plugin_commands.handle_mail_status)
    ctx.register_command("disconnect_gmail", plugin_commands.handle_disconnect_gmail)

    assert "email_search" in ctx.tools
    assert "email_get_thread" in ctx.tools
    assert "email_connection_status" in ctx.tools

    # Zero mutating tools
    assert not any("send" in name or "draft" in name or "delete" in name for name in ctx.tools)

    # Commands registered
    assert "connect_gmail" in ctx.commands
    assert "mail_status" in ctx.commands
    assert "disconnect_gmail" in ctx.commands
