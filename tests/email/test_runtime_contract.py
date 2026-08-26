import asyncio
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "src/.hermes/plugins/email-connector"
UPSTREAM = Path(os.environ["LOCALAPPDATA"]) / "hermes/hermes-agent"
if str(UPSTREAM) not in sys.path:
    sys.path.insert(0, str(UPSTREAM))

PLUGIN_PACKAGE = "h009_email_connector_plugin"
PLUGIN_SPEC = spec_from_file_location(
    PLUGIN_PACKAGE,
    PLUGIN / "__init__.py",
    submodule_search_locations=[str(PLUGIN)],
)
PLUGIN_MODULE = module_from_spec(PLUGIN_SPEC)
sys.modules[PLUGIN_PACKAGE] = PLUGIN_MODULE
PLUGIN_SPEC.loader.exec_module(PLUGIN_MODULE)

from h009_email_connector_plugin.caller import DM_REDIRECT_TEXT
from h009_email_connector_plugin.delivery import PrivateDelivery
from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource, SessionStore, build_session_key
from h009_email_connector_plugin.gmail_tools import PersonalGmailTools


class ProbeSessionStore:
    def __init__(self):
        self._by_id = {}

    def bind(self, session_id, session_key):
        self._by_id[session_id] = SimpleNamespace(session_key=session_key)
    def remove(self, session_id):
        self._by_id.pop(session_id, None)

    def lookup_by_session_id(self, session_id):
        return self._by_id.get(session_id)


class ProbeGmailClient:
    def __init__(self):
        self.calls = []

    def search(self, principal_id, query):
        self.calls.append((principal_id, query))
        return {"status": "ok", "principal_id": principal_id}


class ProbeTelegramAdapter:
    def __init__(self):
        self.calls = []

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.calls.append((chat_id, content, reply_to, metadata))
        return SendResult(success=True, message_id=f"telegram-{chat_id}")


class RuntimeProbe:
    def __init__(self):
        self.session_store = ProbeSessionStore()
        self.gmail = ProbeGmailClient()
        self.tools = PersonalGmailTools(self.session_store, self.gmail)
        self.registry = self.tools.registry

    @staticmethod
    def dm_event(user_id, chat_id):
        source = SessionSource(
            platform=Platform.TELEGRAM,
            user_id=user_id,
            chat_id=chat_id,
            chat_type="dm",
            profile="hermes-business",
        )
        return MessageEvent(text="xem Gmail", source=source, user_id=user_id)

    @staticmethod
    def group_event(user_id):
        source = SessionSource(
            platform=Platform.TELEGRAM,
            user_id=user_id,
            chat_id="-100777",
            chat_type="group",
            profile="hermes-business",
        )
        return MessageEvent(text="xem Gmail", source=source, user_id=user_id)

    def capture(self, event):
        self.tools.pre_gateway_dispatch(event=event)
        session_key = build_session_key(
            event.source,
            profile=event.source.profile,
        )
        session_id = f"session-{event.source.user_id}-{event.source.chat_id}"
        self.session_store.bind(session_id, session_key)
        return session_id

    def capture_and_resolve_dm(self, event):
        session_id = self.capture(event)
        return self.registry.resolve_dm_tool(
            task_id=session_id,
            session_id=session_id,
        )

class ProbePluginContext:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback


def load_registered_plugin():
    context = ProbePluginContext()
    guard = PLUGIN_MODULE.register(context)
    return context, guard


@pytest.fixture
def runtime_probe():
    return RuntimeProbe()

@pytest.fixture
def installed_session_store(tmp_path, monkeypatch):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    config = GatewayConfig(
        sessions_dir=home / "sessions",
        write_sessions_json=False,
    )
    store = SessionStore(config.sessions_dir, config)
    try:
        yield store, config
    finally:
        store.close_all_db_handles()


def test_registered_guard_binds_actual_hermes_session_lifecycle(
    installed_session_store,
    runtime_probe,
):
    store, config = installed_session_store
    context, guard = load_registered_plugin()
    event = runtime_probe.dm_event(user_id="111", chat_id="111")
    gateway = SimpleNamespace(config=config)

    context.hooks["pre_gateway_dispatch"](
        event=event,
        gateway=gateway,
        session_store=store,
    )
    entry = store.get_or_create_session(event.source)
    decision = context.hooks["pre_tool_call"](
        tool_name="email_search",
        args={"query": "marker"},
        task_id=entry.session_id,
        session_id=entry.session_id,
    )
    caller = guard.registry.resolve_dm_tool(
        task_id=entry.session_id,
        session_id=entry.session_id,
    )

    assert decision is None
    assert caller.principal_id == "telegram:hermes-business:111"
    assert caller.session_key == entry.session_key


def test_registered_group_guard_blocks_before_gmail_handler(
    installed_session_store,
    runtime_probe,
):
    store, config = installed_session_store
    context, _guard = load_registered_plugin()
    event = runtime_probe.group_event(user_id="111")
    gateway = SimpleNamespace(config=config)

    context.hooks["pre_gateway_dispatch"](
        event=event,
        gateway=gateway,
        session_store=store,
    )
    entry = store.get_or_create_session(event.source)
    decision = context.hooks["pre_tool_call"](
        tool_name="email_search",
        args={"query": "marker"},
        task_id=entry.session_id,
        session_id=entry.session_id,
    )
    if decision is None:
        runtime_probe.gmail.search("unexpected", "marker")

    assert decision == {"action": "block", "message": DM_REDIRECT_TEXT}
    assert runtime_probe.gmail.calls == []


def test_concurrent_dm_callers_never_swap_identity(runtime_probe):
    caller_a = runtime_probe.dm_event(user_id="111", chat_id="111")
    caller_b = runtime_probe.dm_event(user_id="222", chat_id="222")

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(runtime_probe.capture_and_resolve_dm, caller_a)
        future_b = pool.submit(runtime_probe.capture_and_resolve_dm, caller_b)
        a = future_a.result()
        b = future_b.result()

    assert a.principal_id == "telegram:hermes-business:111"
    assert b.principal_id == "telegram:hermes-business:222"


def test_group_personal_request_redirects_without_gmail_call(runtime_probe):
    session_id = runtime_probe.capture(runtime_probe.group_event(user_id="111"))

    result = runtime_probe.tools.email_search(
        task_id=session_id,
        session_id=session_id,
        model_args={"query": "marker"},
    )

    assert result == {
        "status": "redirect_to_dm",
        "public_text": DM_REDIRECT_TEXT,
    }
    assert runtime_probe.gmail.calls == []


def test_model_cannot_override_dm_principal(runtime_probe):
    session_id = runtime_probe.capture(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )

    result = runtime_probe.tools.email_search(
        task_id=session_id,
        session_id=session_id,
        model_args={
            "query": "marker",
            "principal_id": "telegram:hermes-business:222",
            "chat_id": "222",
        },
    )

    assert result["principal_id"] == "telegram:hermes-business:111"
    assert runtime_probe.gmail.calls == [
        ("telegram:hermes-business:111", "marker")
    ]


def test_conflicting_runtime_session_identifiers_are_rejected(runtime_probe):
    session_id = runtime_probe.capture(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )

    with pytest.raises(LookupError, match="conflicting"):
        runtime_probe.registry.resolve_dm_tool(
            task_id="session-for-another-caller",
            session_id=session_id,
        )


def test_private_delivery_targets_only_the_registry_issued_dm(runtime_probe):
    caller = runtime_probe.capture_and_resolve_dm(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )
    adapter = ProbeTelegramAdapter()
    gateway = SimpleNamespace(adapters={Platform.TELEGRAM: adapter})

    message_id = asyncio.run(
        PrivateDelivery(gateway, runtime_probe.registry).send_dm(
            caller,
            "Nội dung Gmail riêng tư",
        )
    )

    assert message_id == "telegram-111"
    assert adapter.calls == [("111", "Nội dung Gmail riêng tư", None, None)]


def test_private_delivery_rejects_identity_clone_of_issued_caller(runtime_probe):
    caller = runtime_probe.capture_and_resolve_dm(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )
    clone = replace(caller)
    adapter = ProbeTelegramAdapter()
    gateway = SimpleNamespace(adapters={Platform.TELEGRAM: adapter})

    with pytest.raises(LookupError, match="registry-issued"):
        asyncio.run(
            PrivateDelivery(gateway, runtime_probe.registry).send_dm(
                clone,
                "stolen",
            )
        )

    assert adapter.calls == []


def test_session_finalize_forgets_issued_caller(runtime_probe):
    session_id = runtime_probe.capture(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )
    caller = runtime_probe.registry.resolve_dm_tool(
        task_id=session_id,
        session_id=session_id,
    )
    runtime_probe.session_store.remove(session_id)

    runtime_probe.tools.on_session_finalize(session_id=session_id)

    with pytest.raises(LookupError, match="captured"):
        runtime_probe.registry.require_issued(caller)
