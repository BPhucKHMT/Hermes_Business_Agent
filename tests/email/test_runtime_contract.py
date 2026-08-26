import asyncio
from dataclasses import replace
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"
UPSTREAM = Path(os.environ["LOCALAPPDATA"]) / "hermes/hermes-agent"

for p in (SRC, PLUGIN, UPSTREAM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import tools
if str(SRC / "tools") not in tools.__path__:
    tools.__path__.insert(0, str(SRC / "tools"))

from caller import CallerContext, CallerContextRegistry, DM_REDIRECT_TEXT, DmOnlyError
from delivery import PrivateDelivery
from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource, SessionStore, build_session_key
from gmail_tools import PersonalGmailTools


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

    def search_threads(self, query):
        self.calls.append(query)
        return [{"id": "t1"}]


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
        self.tools.pre_gateway_dispatch(event=event, session_store=self.session_store)
        session_key = build_session_key(
            event.source,
            profile=getattr(event.source, "profile", None),
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
        self.tools = {}
        self.commands = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"schema": schema, "handler": handler}

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler


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
    tools_instance = PersonalGmailTools()
    context = ProbePluginContext()
    context.register_hook("pre_gateway_dispatch", tools_instance.pre_gateway_dispatch)
    context.register_hook("pre_tool_call", tools_instance.pre_tool_call)

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
        _args={"query": "test"},
        task_id=entry.session_id,
        session_id=entry.session_id,
    )
    assert decision is None


def test_registered_group_guard_blocks_before_gmail_handler(
    installed_session_store,
    runtime_probe,
):
    store, config = installed_session_store
    tools_instance = PersonalGmailTools()
    context = ProbePluginContext()
    context.register_hook("pre_gateway_dispatch", tools_instance.pre_gateway_dispatch)
    context.register_hook("pre_tool_call", tools_instance.pre_tool_call)

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
        _args={"query": "test"},
        task_id=entry.session_id,
        session_id=entry.session_id,
    )
    assert decision == {"action": "block", "message": DM_REDIRECT_TEXT}


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

    result_raw = runtime_probe.tools.email_search(
        task_id=session_id,
        session_id=session_id,
        model_args={"query": "marker"},
    )
    result = json.loads(result_raw) if isinstance(result_raw, str) else result_raw

    assert result["status"] == "redirect_to_dm"
    assert runtime_probe.gmail.calls == []


def test_model_cannot_override_dm_principal(runtime_probe):
    session_id = runtime_probe.capture(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )

    result_raw = runtime_probe.tools.email_search(
        task_id=session_id,
        session_id=session_id,
        model_args={
            "query": "marker",
            "principal_id": "telegram:hermes-business:222",
            "chat_id": "222",
        },
    )
    result = json.loads(result_raw) if isinstance(result_raw, str) else result_raw

    assert result["status"] == "ok"
    assert runtime_probe.gmail.calls == ["marker"]



def test_command_caller_comes_from_trusted_gateway_hook(runtime_probe):
    runtime_probe.capture(runtime_probe.dm_event(user_id="111", chat_id="111"))

    caller = runtime_probe.registry.resolve_command()

    assert caller.principal_id == "telegram:hermes-business:111"


def test_group_command_context_is_dm_redirect_only(runtime_probe):
    runtime_probe.capture(runtime_probe.group_event(user_id="111"))

    with pytest.raises(DmOnlyError, match="Mở chat riêng"):
        runtime_probe.registry.resolve_command()

def test_conflicting_runtime_session_identifiers_are_rejected(runtime_probe):
    session_id = runtime_probe.capture(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )

    with pytest.raises(LookupError, match="conflicting"):
        runtime_probe.registry.resolve_dm_tool(
            task_id=session_id,
            session_id=f"{session_id}-other",
        )


def test_private_delivery_targets_only_the_registry_issued_dm(runtime_probe):
    caller = runtime_probe.capture_and_resolve_dm(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )
    adapter = ProbeTelegramAdapter()
    delivery = PrivateDelivery(
        SimpleNamespace(adapters={Platform.TELEGRAM: adapter}),
        runtime_probe.registry,
    )

    message_id = asyncio.run(delivery.send_dm(caller, "Nội dung Gmail riêng tư"))

    assert message_id == "telegram-111"
    assert adapter.calls == [("111", "Nội dung Gmail riêng tư", None, None)]


def test_private_delivery_rejects_identity_clone_of_issued_caller(runtime_probe):
    caller = runtime_probe.capture_and_resolve_dm(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )
    forged_clone = replace(caller)
    adapter = ProbeTelegramAdapter()
    delivery = PrivateDelivery(
        SimpleNamespace(adapters={Platform.TELEGRAM: adapter}),
        runtime_probe.registry,
    )

    with pytest.raises(PermissionError, match="does not match the issued host identity"):
        asyncio.run(delivery.send_dm(forged_clone, "Nội dung giả mạo"))

    assert adapter.calls == []


def test_session_finalize_forgets_issued_caller(runtime_probe):
    event = runtime_probe.dm_event(user_id="111", chat_id="111")
    session_id = runtime_probe.capture(event)
    runtime_probe.registry.resolve_dm_tool(task_id=session_id, session_id=session_id)

    session_key = build_session_key(event.source, profile=getattr(event.source, "profile", None))
    runtime_probe.session_store.remove(session_id)
    runtime_probe.tools.on_session_finalize(session_id=session_id)

    assert runtime_probe.registry.get_issued_dm(session_key) is None
    with pytest.raises(LookupError):
        runtime_probe.registry.resolve_dm_tool(
            task_id=session_id,
            session_id=session_id,
        )
