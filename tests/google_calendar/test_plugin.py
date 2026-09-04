import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/calendar-connector"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"

sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(UPSTREAM))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin_tools = load_module("calendar_plugin_tools", PLUGIN / "calendar_plugin_tools.py")
plugin_module = load_module("calendar_plugin", PLUGIN / "__init__.py")

class FakeContext:
    def __init__(self) -> None:
        self.tools = {}
        self.commands = {}
        self.hooks = {}

    def register_tool(self, name, **kwargs):
        self.tools[name] = kwargs

    def register_command(self, name, handler, description=""):
        self.commands[name] = {"handler": handler, "description": description}

    def register_hook(self, name, handler):
        self.hooks[name] = handler


class FakeRegistry:
    def __init__(self, caller=None, error=None) -> None:
        self.caller = caller
        self.error = error

    def resolve_dm_tool(self, **kwargs):
        if self.error:
            raise self.error
        return self.caller


class FakeClient:
    def list_events(self, caller, **kwargs):
        return {"ok": True, "result": {"events": [{"summary": "Test Meeting"}]}}

    def find_free_slots(self, caller, **kwargs):
        return {"ok": True, "result": {"slots": [{"start_time": "2026-09-01T09:00:00Z"}]}}

    def create_draft_event(self, caller, **kwargs):
        return {"ok": True, "result": {"draft": {"draft_id": "drf-test-1"}}}

    def confirm_event(self, caller, **kwargs):
        return {"ok": True, "result": {"event": {"event_id": "evt-test-1"}}}

    def status(self, caller):
        return {"ok": True, "status": "connected", "calendar_name": "Test Cal"}


def test_plugin_exposes_calendar_tools(monkeypatch) -> None:
    context = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: FakeClient())

    plugin_module.register(context)

    expected = {
        "calendar_list_events",
        "calendar_get_event",
        "calendar_create_event",
        "calendar_create_draft_event",
        "calendar_confirm_event",
        "calendar_update_event",
        "calendar_delete_event",
        "calendar_find_free_slots",
        "calendar_status",
    }
    assert set(context.tools) == expected


def test_calendar_handler_dm_enforcement() -> None:
    registry = FakeRegistry(error=plugin_tools.DmOnlyError("dm required"))

    raw = plugin_tools.handle_calendar_list_events(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )
    res = json.loads(raw)
    assert res["ok"] is False
    assert res["error"]["code"] == "dm_required"


def test_calendar_handler_success() -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    registry = FakeRegistry(caller=caller)

    raw = plugin_tools.handle_calendar_list_events(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )
    res = json.loads(raw)
    assert res["ok"] is True
    assert len(res["result"]["events"]) == 1
