import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "src/.hermes/plugins/email-connector"
UPSTREAM = Path(os.environ["LOCALAPPDATA"]) / "hermes/hermes-agent"
for path in (PLUGIN, UPSTREAM):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from caller import CallerContext, CallerContextRegistry, DM_REDIRECT_TEXT
from delivery import PrivateDelivery
from gateway.config import Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource, SessionStore, build_session_key
from gmail_tools import PersonalGmailTools


class ProbeSessionStore:
    def __init__(self):
        self._by_id = {}

    def bind(self, session_id, session_key):
        self._by_id[session_id] = SimpleNamespace(session_key=session_key)

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


@pytest.fixture
def runtime_probe():
    return RuntimeProbe()


def test_installed_session_store_exposes_public_session_id_lookup():
    assert callable(SessionStore.lookup_by_session_id)


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


def test_private_delivery_rejects_forged_caller(runtime_probe):
    adapter = ProbeTelegramAdapter()
    gateway = SimpleNamespace(adapters={Platform.TELEGRAM: adapter})
    forged = CallerContext(
        principal_id="telegram:hermes-business:222",
        platform="telegram",
        user_id="222",
        chat_id="222",
        thread_id=None,
        chat_type="dm",
        profile="hermes-business",
        session_key="agent:hermes-business:telegram:dm:222",
    )

    with pytest.raises(LookupError, match="registry-issued"):
        asyncio.run(
            PrivateDelivery(gateway, runtime_probe.registry).send_dm(
                forged,
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

    runtime_probe.tools.on_session_finalize(session_id=session_id)

    with pytest.raises(LookupError, match="captured"):
        runtime_probe.registry.require_issued(caller)
