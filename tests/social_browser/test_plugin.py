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
    def connection_status(self, caller):
        return {
            "ok": True,
            "result": {"principal_id": caller.principal_id, "status": "not_connected"},
        }



def test_plugin_exposes_truthful_customer_tools(monkeypatch) -> None:
    context = FakeContext()
    monkeypatch.setattr(plugin_module, "get_default_client", lambda: FakeClient())

    plugin_module.register(context)

    assert set(context.tools) == {"social_connection_status"}
    forbidden = {
        "social_prepare_facebook_post",
        "social_browser_status",
        "social_verify_facebook_post",
        "browser_cdp",
        "browser_js",
        "browser_click",
        "social_publish",
    }
    assert forbidden.isdisjoint(context.tools)


def test_new_telegram_dm_can_query_connection_status_without_operator_env(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SOCIAL_BROWSER_ALLOWED_TELEGRAM_USERS", raising=False)
    registry = FakeRegistry(
        caller=SimpleNamespace(
            user_id="new-customer",
            principal_id="telegram:default:new-customer",
        )
    )

    raw = plugin_tools.handle_connection_status(
        {},
        client=FakeClient(),
        registry=registry,
        session_id="session-1",
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "not_connected"
    assert payload["result"]["principal_id"] == "telegram:default:new-customer"


def test_personal_facebook_prepare_is_not_publicly_available() -> None:
    assert not hasattr(plugin_tools, "handle_prepare")
    assert not hasattr(plugin_module, "SOCIAL_PREPARE_SCHEMA")
