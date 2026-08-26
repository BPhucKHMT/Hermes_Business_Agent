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

import tools
if str(SRC / "tools") not in tools.__path__:
    tools.__path__.insert(0, str(SRC / "tools"))

plugin_tools = _load("email_tools_mod", PLUGIN / "plugin_tools.py")
plugin_schemas = _load("email_schemas_mod", PLUGIN / "schemas.py")
plugin_commands = _load("email_commands_mod", PLUGIN / "commands.py")
plugin_module = _load("email_plugin_mod", PLUGIN / "__init__.py")
plugin_client = _load("email_client_mod", PLUGIN / "client.py")


class FakeRegistry:
    def __init__(self, caller=None, error=None):
        self.caller = caller
        self.error = error

    def resolve_dm_tool(self, **kwargs):
        if self.error:
            raise self.error
        return self.caller

    def resolve_command(self):
        if self.error:
            raise self.error
        return self.caller


class FakeConnectorClient:
    def __init__(self):
        self.calls = []

    def search(self, caller, query, limit):
        self.calls.append(("search", caller.principal_id, query, limit))
        return {"ok": True, "result": {"hits": [{"thread_id": "real-t1"}]}}

    def get_thread(self, caller, thread_id):
        self.calls.append(("thread", caller.principal_id, thread_id))
        return {"ok": True, "result": {"thread": {"thread_id": thread_id, "text": "real body"}}}

    def connections(self, caller):
        self.calls.append(("connections", caller.principal_id))
        return {
            "ok": True,
            "result": {
                "connections": [
                    {"connection_id": "conn-1", "masked_address": "u***@gmail.com", "status": "connected"}
                ]
            },
        }

    def start_oauth(self, caller):
        self.calls.append(("oauth", caller.principal_id))
        return {"ok": True, "result": {"authorization_url": "https://accounts.google.com/real"}}

    def disconnect(self, caller, connection_id):
        self.calls.append(("disconnect", caller.principal_id, connection_id))
        return {"ok": True, "result": {"connection_id": connection_id, "status": "revoked"}}


CALLER = type(
    "Caller",
    (),
    {
        "principal_id": "telegram:hermes-business:111",
        "platform": "telegram",
        "user_id": "111",
        "chat_id": "111",
        "thread_id": None,
        "chat_type": "dm",
        "profile": "hermes-business",
        "session_key": "telegram:dm:111",
    },
)()


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


def test_plugin_registers_read_tools_and_commands(monkeypatch):
    ctx = FakeContext()
    client = FakeConnectorClient()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: client)

    plugin_module.register(ctx)

    assert set(ctx.tools) == {
        "email_search",
        "email_get_thread",
        "email_connection_status",
    }
    assert not any(
        word in name
        for name in ctx.tools
        for word in ("send", "draft", "label", "delete")
    )
    assert set(ctx.commands) == {
        "connect_gmail",
        "mail_status",
        "disconnect_gmail",
    }


def test_registered_tool_handlers_invoke_connector_without_placeholders(monkeypatch):
    client = FakeConnectorClient()
    ctx = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: client)
    guard = plugin_module.register(ctx)
    monkeypatch.setattr(guard.registry, "resolve_dm_tool", lambda **kwargs: CALLER)

    search = ctx.tools["email_search"]["handler"](
        {"query": "from:supplier", "limit": 3},
        task_id="session-1",
        session_id="session-1",
    )
    thread = ctx.tools["email_get_thread"]["handler"](
        {"thread_id": "real-t1"},
        task_id="session-1",
        session_id="session-1",
    )
    status = ctx.tools["email_connection_status"]["handler"](
        {},
        task_id="session-1",
        session_id="session-1",
    )

    assert "Grounded search" not in search
    assert "Grounded thread" not in thread
    assert '"real-t1"' in search
    assert '"real body"' in thread
    assert '"conn-1"' in status
    assert client.calls == [
        ("search", CALLER.principal_id, "from:supplier", 3),
        ("thread", CALLER.principal_id, "real-t1"),
        ("connections", CALLER.principal_id),
    ]


def test_registered_commands_invoke_connector_and_never_fake_success(monkeypatch):
    client = FakeConnectorClient()
    ctx = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: client)
    guard = plugin_module.register(ctx)
    monkeypatch.setattr(guard.registry, "resolve_command", lambda: CALLER)

    connect = ctx.commands["connect_gmail"]("")
    status = ctx.commands["mail_status"]("")
    disconnect = ctx.commands["disconnect_gmail"]("conn-1")

    assert "accounts.google.com/real" in connect
    assert "conn-1" in status
    assert "revoked" in disconnect
    assert client.calls == [
        ("oauth", CALLER.principal_id),
        ("connections", CALLER.principal_id),
        ("disconnect", CALLER.principal_id, "conn-1"),
    ]


def test_missing_connector_or_caller_fails_closed():
    no_caller = plugin_tools.handle_email_connection_status(
        {},
        client=FakeConnectorClient(),
        registry=FakeRegistry(error=LookupError("no trusted caller")),
        task_id="unknown",
        session_id="unknown",
    )
    no_client = plugin_commands.handle_mail_status(
        "",
        client=None,
        registry=FakeRegistry(CALLER),
    )

    assert '"ok": false' in no_caller
    assert "connected" not in no_caller
    assert "không khả dụng" in no_client.lower()
    assert "connected" not in no_client.lower()


def test_missing_runtime_config_returns_connector_unavailable(monkeypatch):
    for name in (
        "AZURE_KEY_VAULT_URL",
        "EMAIL_GOOGLE_CLIENT_ID",
        "EMAIL_OAUTH_REDIRECT_URI",
        "EMAIL_CONNECTOR_SHARED_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    ctx = FakeContext()
    unavailable = plugin_client._build_default_client()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: unavailable)
    guard = plugin_module.register(ctx)
    monkeypatch.setattr(guard.registry, "resolve_dm_tool", lambda **kwargs: CALLER)

    result = ctx.tools["email_connection_status"]["handler"](
        {},
        task_id="session-1",
        session_id="session-1",
    )

    assert '"ok": false' in result
    assert '"code": "connector_unavailable"' in result
    assert "connected" not in result
