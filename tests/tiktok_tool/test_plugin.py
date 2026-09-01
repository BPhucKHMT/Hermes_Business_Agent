import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/tiktok-connector"
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


plugin_tools = load_module("tiktok_plugin_tools", PLUGIN / "tiktok_plugin_tools.py")
plugin_module = load_module("tiktok_plugin", PLUGIN / "__init__.py")


class FakeContext:
    def __init__(self) -> None:
        self.tools = {}
        self.hooks = {}

    def register_tool(self, name, **kwargs):
        self.tools[name] = kwargs

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
    def get_creator_info(self, caller):
        return {"ok": True, "result": {"open_id": "open-tt-1", "creator_nickname": "Test Creator"}}

    def create_draft_post(self, caller, **kwargs):
        return {"ok": True, "result": {"draft": {"draft_id": "drf-tt-1"}}}

    def publish_video(self, caller, draft_id):
        return {"ok": True, "result": {"publish_id": "pub-tt-1"}}

    def get_post_status(self, caller, publish_id):
        return {"ok": True, "result": {"status": "SUCCESS", "post_id": "post-tt-1"}}


def test_plugin_exposes_tiktok_tools(monkeypatch) -> None:
    context = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: FakeClient())

    plugin_module.register(context)

    expected = {
        "tiktok_creator_info",
        "tiktok_create_draft_post",
        "tiktok_publish_video",
        "tiktok_post_status",
    }
    assert set(context.tools) == expected


def test_tiktok_handler_dm_enforcement() -> None:
    registry = FakeRegistry(error=plugin_tools.DmOnlyError("dm required"))

    raw = plugin_tools.handle_tiktok_creator_info(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )
    res = json.loads(raw)
    assert res["ok"] is False
    assert res["error"]["code"] == "dm_required"


def test_tiktok_handler_success() -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    registry = FakeRegistry(caller=caller)

    raw = plugin_tools.handle_tiktok_creator_info(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )
    res = json.loads(raw)
    assert res["ok"] is True
    assert res["result"]["open_id"] == "open-tt-1"
