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

from caller import CallerContextRegistry, DmOnlyError
from delivery import PrivateDelivery
from gateway.config import Platform
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionSource, SessionStore, build_session_key


REDIRECT_TEXT = "Mở chat riêng với Hermes để xem Gmail cá nhân."


class ProbeSessionStore:
    def __init__(self):
        self._by_id = {}

    def bind(self, session_id, session_key):
        self._by_id[session_id] = SimpleNamespace(session_key=session_key)

    def lookup_by_session_id(self, session_id):
        return self._by_id.get(session_id)


class ProbeTelegramAdapter:
    def __init__(self):
        self.calls = []

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.calls.append((chat_id, content, reply_to, metadata))
        return SendResult(success=True, message_id=f"telegram-{chat_id}")


class RuntimeProbe:
    def __init__(self):
        self.session_store = ProbeSessionStore()
        self.registry = CallerContextRegistry(self.session_store)
        self.gmail_calls = 0

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

    def capture_and_resolve_dm(self, event):
        session_key = build_session_key(
            event.source,
            profile=event.source.profile,
        )
        self.registry.capture_dm(event, session_key)
        session_id = f"session-{event.source.user_id}"
        self.session_store.bind(session_id, session_key)
        return self.registry.resolve_dm_tool(
            task_id=session_id,
            session_id=session_id,
        )

    def request_personal_mail_from_group(self, user_id):
        event = self.group_event(user_id)
        session_key = build_session_key(
            event.source,
            profile=event.source.profile,
        )
        try:
            self.registry.capture_dm(event, session_key)
        except DmOnlyError as exc:
            return SimpleNamespace(public_text=str(exc), gmail_calls=self.gmail_calls)
        self.gmail_calls += 1
        return SimpleNamespace(public_text="unexpected", gmail_calls=self.gmail_calls)

    def invoke_dm_tool(self, user_id, model_args):
        del model_args
        return self.capture_and_resolve_dm(self.dm_event(user_id, user_id))


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

    assert a.principal_id.endswith(":111")
    assert b.principal_id.endswith(":222")
    assert a.principal_id != b.principal_id


def test_group_personal_request_redirects_without_gmail_call(runtime_probe):
    result = runtime_probe.request_personal_mail_from_group(user_id="111")
    assert result.public_text == REDIRECT_TEXT
    assert result.gmail_calls == 0


def test_model_cannot_override_dm_principal(runtime_probe):
    resolved = runtime_probe.invoke_dm_tool(
        user_id="111",
        model_args={"principal_id": "telegram:hermes-business:222"},
    )
    assert resolved.principal_id == "telegram:hermes-business:111"


def test_private_delivery_targets_only_the_captured_dm(runtime_probe):
    caller = runtime_probe.capture_and_resolve_dm(
        runtime_probe.dm_event(user_id="111", chat_id="111")
    )
    adapter = ProbeTelegramAdapter()
    gateway = SimpleNamespace(adapters={Platform.TELEGRAM: adapter})

    message_id = asyncio.run(
        PrivateDelivery(gateway).send_dm(caller, "Nội dung Gmail riêng tư")
    )

    assert message_id == "telegram-111"
    assert adapter.calls == [("111", "Nội dung Gmail riêng tư", None, None)]
