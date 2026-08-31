import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


PACKAGE = "hermes_social_browser_assist"


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/social-browser-assist"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"


sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(UPSTREAM))
package = sys.modules.setdefault(PACKAGE, ModuleType(PACKAGE))
package.__path__ = [str(PLUGIN)]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

caller = load(
    f"{PACKAGE}.social_caller",
    PLUGIN / "social_caller.py",
)
plugin_tools = load(
    f"{PACKAGE}.social_plugin_tools",
    PLUGIN / "social_plugin_tools.py",
)
plugin_module = load("social_plugin", PLUGIN / "__init__.py")
plugin_client = load(
    f"{PACKAGE}.social_client",
    PLUGIN / "social_client.py",
)


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


class FakeService:
    def prepare(self, request):
        from tools.social_browser.contracts import PreparationResult, RunStatus

        return PreparationResult(
            run_id="social-run",
            status=RunStatus.READY_FOR_HUMAN,
            account_label=request.account_label,
            text_digest="digest",
            media_digests=(),
            audience=request.audience,
            evidence_paths=(),
        )


class FakeClient:
    def prepare(self, caller, params):
        return {"ok": True, "result": {"status": "ready_for_human"}}

    def status(self, caller, run_id):
        return {"ok": True, "result": {"run_id": run_id}}

    def verify(self, caller, run_id):
        return {"ok": True, "result": {"run_id": run_id}}


def test_plugin_exposes_only_narrow_tools(monkeypatch) -> None:
    context = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: FakeClient())

    plugin_module.register(context)

    assert set(context.tools) == {
        "social_prepare_facebook_post",
        "social_browser_status",
        "social_verify_facebook_post",
    }
    forbidden = {"browser_cdp", "browser_js", "browser_click", "social_publish"}
    assert forbidden.isdisjoint(context.tools)


def test_prepare_requires_dm() -> None:
    registry = FakeRegistry(error=plugin_tools.DmOnlyError("dm required"))

    raw = plugin_tools.handle_prepare(
        {"account_label": "test", "text": "hello", "audience": "friends"},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )

    assert json.loads(raw)["error"]["code"] == "dm_required"


def test_prepare_passes_bound_caller() -> None:
    caller = SimpleNamespace(user_id="123", principal_id="telegram:default:123")
    registry = FakeRegistry(caller=caller)

    raw = plugin_tools.handle_prepare(
        {"account_label": "test", "text": "hello", "audience": "friends"},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )

    assert json.loads(raw)["result"]["status"] == "ready_for_human"


def test_client_fails_closed_without_caller_allowlist(monkeypatch) -> None:
    monkeypatch.delenv("SOCIAL_BROWSER_ALLOWED_TELEGRAM_USERS", raising=False)
    client = plugin_client.SocialBrowserClient(lambda: FakeService())
    caller = SimpleNamespace(user_id="123")

    try:
        client.prepare(
            caller,
            {
                "account_label": "test",
                "text": "hello",
                "audience": "friends",
            },
        )
    except PermissionError as exc:
        assert str(exc) == "social_browser_caller_allowlist_required"
    else:
        raise AssertionError("empty caller allowlist was accepted")


def test_client_accepts_explicitly_allowed_caller(monkeypatch) -> None:
    monkeypatch.setenv("SOCIAL_BROWSER_ALLOWED_TELEGRAM_USERS", "123")
    client = plugin_client.SocialBrowserClient(lambda: FakeService())
    caller = SimpleNamespace(user_id="123")

    result = client.prepare(
        caller,
        {
            "account_label": "test",
            "text": "hello",
            "audience": "friends",
        },
    )

    assert result["result"]["status"] == "ready_for_human"
