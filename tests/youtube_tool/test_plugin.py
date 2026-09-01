import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/youtube-connector"
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


plugin_tools = load_module("youtube_plugin_tools", PLUGIN / "youtube_plugin_tools.py")
plugin_module = load_module("youtube_plugin", PLUGIN / "__init__.py")


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
    def get_channel_status(self, caller):
        return {"ok": True, "result": {"channel_id": "UC-123", "title": "Test Channel"}}

    def list_videos(self, caller, limit=10):
        return {"ok": True, "result": {"videos": [{"title": "Video 1"}], "count": 1}}

    def create_draft_video(self, caller, **kwargs):
        return {"ok": True, "result": {"draft": {"draft_id": "drf-yt-1"}}}

    def upload_video(self, caller, draft_id):
        return {"ok": True, "result": {"video": {"video_id": "v-123"}}}

    def update_metadata(self, caller, **kwargs):
        return {"ok": True, "result": {"video": {"title": "Updated"}}}


def test_plugin_exposes_youtube_tools(monkeypatch) -> None:
    context = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: FakeClient())

    plugin_module.register(context)

    expected = {
        "youtube_channel_status",
        "youtube_list_videos",
        "youtube_create_draft_video",
        "youtube_upload_video",
        "youtube_update_video_metadata",
    }
    assert set(context.tools) == expected


def test_youtube_handler_dm_enforcement() -> None:
    registry = FakeRegistry(error=plugin_tools.DmOnlyError("dm required"))

    raw = plugin_tools.handle_youtube_channel_status(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )
    res = json.loads(raw)
    assert res["ok"] is False
    assert res["error"]["code"] == "dm_required"


def test_youtube_handler_success() -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    registry = FakeRegistry(caller=caller)

    raw = plugin_tools.handle_youtube_channel_status(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )
    res = json.loads(raw)
    assert res["ok"] is True
    assert res["result"]["channel_id"] == "UC-123"
