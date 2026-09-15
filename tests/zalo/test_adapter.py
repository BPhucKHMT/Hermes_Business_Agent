from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import types
from unittest.mock import AsyncMock
import uuid

import httpx
import pytest

try:
    import concurrent_log_handler  # noqa: F401 -- import only to detect optional handler availability
except ImportError:
    _dummy_clh = types.ModuleType("concurrent_log_handler")
    _dummy_clh.ConcurrentRotatingFileHandler = RotatingFileHandler
    sys.modules["concurrent_log_handler"] = _dummy_clh

from gateway.authz_mixin import (
    GatewayAuthorizationMixin,
)
from gateway.config import (
    PlatformConfig,
)
from gateway.platform_registry import (
    PlatformEntry,
    platform_registry,
)
from gateway.session import (
    build_session_key,
)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes" / "plugins" / "zalo-platform"


TOKEN = "zalo-test-" + "X" * 28
ZALO_DISPLAY_NAME = "Bot Hermes Business Agent"
ZALO_MENTION = f"@{ZALO_DISPLAY_NAME}"


def _run(awaitable):
    return asyncio.run(awaitable)


def _load_zalo_package():
    module_name = f"_h016_zalo_platform_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN / "__init__.py",
        submodule_search_locations=[str(PLUGIN)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Zalo plugin from {PLUGIN}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _RegistrationContext:
    def __init__(self):
        self.kwargs = None

    def register_platform(
        self,
        *,
        name,
        label,
        adapter_factory,
        check_fn,
        validate_config=None,
        required_env=None,
        install_hint="",
        **entry_kwargs,
    ):
        self.kwargs = {
            "name": name,
            "label": label,
            "adapter_factory": adapter_factory,
            "check_fn": check_fn,
            "validate_config": validate_config,
            "required_env": required_env or [],
            "install_hint": install_hint,
            **entry_kwargs,
        }
        entry_kwargs.setdefault("plugin_name", "zalo-platform")
        platform_registry.register(
            PlatformEntry(
                name=name,
                label=label,
                adapter_factory=adapter_factory,
                check_fn=check_fn,
                validate_config=validate_config,
                required_env=required_env or [],
                install_hint=install_hint,
                source="plugin",
                **entry_kwargs,
            ),
            scope=None,
        )


@pytest.fixture(scope="module")
def zalo_module():
    return _load_zalo_package()


@pytest.fixture(scope="module")
def registered_zalo(zalo_module):
    previous = platform_registry.snapshot_registration("zalo", scope=None)
    context = _RegistrationContext()
    zalo_module.register(context)
    try:
        yield context
    finally:
        current = platform_registry.snapshot_registration("zalo", scope=None)
        platform_registry.restore_registration("zalo", current, previous, scope=None)


@pytest.fixture
def adapter(registered_zalo, monkeypatch):
    monkeypatch.delenv("ZALO_BOT_TOKEN", raising=False)
    created = registered_zalo.kwargs["adapter_factory"](
        PlatformConfig(enabled=True, token=TOKEN)
    )
    monkeypatch.setattr(
        created,
        "_write_runtime_status_safe",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        created,
        "_acquire_platform_lock",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(created, "_release_platform_lock", lambda: None)
    created._install_http_log_filter()
    yield created
    created._remove_http_log_filter()


async def _using_client(adapter, handler, operation):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter._client = client
    adapter._running = True
    try:
        return await operation()
    finally:
        await client.aclose()


def _response(request, payload, status=200):
    return httpx.Response(status, json=payload, request=request)


def _request_body(request):
    return json.loads(request.content.decode("utf-8"))


def _message_update(
    *,
    user_id="user-a",
    chat_id=None,
    text="Xin chào",
    message_id="message-1",
    chat_type="PRIVATE",
    is_bot=False,
    event_name="message.text.received",
):
    return {
        "event_name": event_name,
        "message": {
            "from": {
                "id": str(user_id),
                "display_name": "Người dùng",
                "is_bot": is_bot,
            },
            "chat": {
                "id": str(chat_id or user_id),
                "chat_type": chat_type,
            },
            "text": text,
            "message_id": str(message_id),
            "date": 1725000000000,
        },
    }


def _valid_get_me(request):
    return _response(
        request,
        {"ok": True, "result": {"id": "bot-1", "name": "Hermes"}},
    )


def _valid_webhook_info(request):
    return _response(request, {"ok": True, "result": {"url": ""}})


def _patch_client_factory(monkeypatch, zalo_module, handler):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    clients = []

    def make_client(*_args, **_kwargs):
        client = real_client(transport=transport)
        clients.append(client)
        return client

    monkeypatch.setattr(zalo_module.adapter.httpx, "AsyncClient", make_client)
    return clients


def test_validate_config_uses_environment_or_actual_config_token(
    registered_zalo, monkeypatch
):
    validate = registered_zalo.kwargs["validate_config"]

    monkeypatch.delenv("ZALO_BOT_TOKEN", raising=False)
    assert validate(PlatformConfig(enabled=True, token=None)) is False
    assert validate(PlatformConfig(enabled=True, token=TOKEN)) is True

    monkeypatch.setenv("ZALO_BOT_TOKEN", TOKEN)
    assert validate(PlatformConfig(enabled=True, token=None)) is True


class _PairingStore:
    def __init__(self, approved=()):
        self.approved = {str(user_id) for user_id in approved}
        self.calls = []

    def is_approved(self, platform, user_id):
        self.calls.append((platform, str(user_id)))
        return str(user_id) in self.approved


class _AuthorizationProbe(GatewayAuthorizationMixin):
    def __init__(self, adapter, pairing_store):
        self.adapters = {adapter.platform: adapter}
        self.pairing_store = pairing_store


def test_registered_allowlist_authorizes_only_listed_zalo_sender(adapter, monkeypatch):
    monkeypatch.delenv("GATEWAY_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("ZALO_ALLOW_ALL_USERS", raising=False)
    monkeypatch.setenv("ZALO_ALLOWED_USERS", "approved-user")
    probe = _AuthorizationProbe(adapter, _PairingStore())

    denied = adapter.build_source(
        chat_id="denied-user",
        user_id="denied-user",
        user_name="Denied",
        chat_type="dm",
    )
    approved = adapter.build_source(
        chat_id="approved-user",
        user_id="approved-user",
        user_name="Approved",
        chat_type="dm",
    )
    denied_group = adapter.build_source(
        chat_id="group-1",
        user_id="denied-user",
        user_name="Denied",
        chat_type="group",
    )
    approved_group = adapter.build_source(
        chat_id="group-1",
        user_id="approved-user",
        user_name="Approved",
        chat_type="group",
    )

    assert probe._is_user_authorized(denied) is False
    assert probe._is_user_authorized(approved) is True
    assert probe._is_user_authorized(denied_group) is False
    assert probe._is_user_authorized(approved_group) is True


def test_native_pairing_grant_is_the_only_extra_authorization_path(
    adapter, monkeypatch
):
    for name in (
        "ZALO_ALLOWED_USERS",
        "GATEWAY_ALLOWED_USERS",
        "ZALO_ALLOW_ALL_USERS",
        "GATEWAY_ALLOW_ALL_USERS",
    ):
        monkeypatch.delenv(name, raising=False)
    pairing = _PairingStore({"paired-user"})
    probe = _AuthorizationProbe(adapter, pairing)

    denied = adapter.build_source(
        chat_id="unknown-user",
        user_id="unknown-user",
        user_name="Unknown",
        chat_type="dm",
    )
    paired = adapter.build_source(
        chat_id="paired-user",
        user_id="paired-user",
        user_name="Paired",
        chat_type="dm",
    )

    assert probe._is_user_authorized(denied) is False
    assert probe._is_user_authorized(paired) is True
    assert pairing.calls[-1] == ("zalo", "paired-user")


def test_private_messages_preserve_same_session_and_isolate_other_users(adapter):
    received = []

    async def handle_message(event):
        received.append(event)

    adapter.handle_message = handle_message
    adapter._message_handler = object()
    _run(adapter._dispatch_update(_message_update(message_id="m-1")))
    _run(
        adapter._dispatch_update(
            _message_update(text="Tin nhắn thứ hai", message_id="m-2")
        )
    )
    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="user-b",
                chat_id="user-b",
                text="Người khác",
                message_id="m-3",
            )
        )
    )

    assert [event.message_id for event in received] == ["m-1", "m-2", "m-3"]
    assert received[0].source.chat_type == "dm"
    assert received[0].source.user_id == received[1].source.user_id == "user-a"
    assert received[0].source.chat_id == received[1].source.chat_id == "user-a"
    assert build_session_key(received[0].source) == build_session_key(
        received[1].source
    )
    assert build_session_key(received[1].source) != build_session_key(
        received[2].source
    )


def test_group_message_dispatches_with_group_source_and_sender_identity(adapter):
    received = []

    async def handle_message(event):
        received.append(event)

    adapter.handle_message = handle_message
    adapter._message_handler = object()
    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="member-a",
                chat_id="group-1",
                text="Chào bot",
                message_id="g-1",
                chat_type="GROUP",
            )
        )
    )

    assert len(received) == 1
    event = received[0]
    assert event.source.chat_type == "group"
    assert event.source.chat_id == "group-1"
    assert event.source.user_id == "member-a"
    assert event.source.user_name == "Người dùng"


@pytest.mark.parametrize(
    ("suffix", "expected_text", "expected_command", "expected_args"),
    [
        ("/help", "/help", "help", ""),
        ("/new   Project alpha", "/new   Project alpha", "new", "Project alpha"),
        (
            "/connect-google --account work",
            "/connect-google --account work",
            "connect-google",
            "--account work",
        ),
        ("/unknown what now", "/unknown what now", "unknown", "what now"),
    ],
)
def test_group_bot_mentions_dispatch_as_native_commands(
    adapter, monkeypatch, suffix, expected_text, expected_command, expected_args
):
    monkeypatch.setenv("ZALO_BOT_DISPLAY_NAME", ZALO_DISPLAY_NAME)
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()

    _run(
        adapter._dispatch_update(
            _message_update(
                chat_id="group-commands",
                chat_type="GROUP",
                text=f"{ZALO_MENTION} {suffix}",
            )
        )
    )

    event = adapter.handle_message.await_args.args[0]
    assert event.text == expected_text
    assert event.get_command() == expected_command
    assert event.get_command_args() == expected_args


@pytest.mark.parametrize(
    ("chat_type", "text", "configured_name"),
    [
        ("GROUP", "@Wrong Bot /help", ZALO_DISPLAY_NAME),
        ("GROUP", f"{ZALO_MENTION}Pro /help", ZALO_DISPLAY_NAME),
        ("GROUP", "Please use /help when ready", ZALO_DISPLAY_NAME),
        ("GROUP", f"{ZALO_MENTION} /help", None),
        ("PRIVATE", f"{ZALO_MENTION} /help", ZALO_DISPLAY_NAME),
    ],
)
def test_non_matching_mentions_remain_plain_text(
    adapter, monkeypatch, chat_type, text, configured_name
):
    if configured_name is None:
        monkeypatch.delenv("ZALO_BOT_DISPLAY_NAME", raising=False)
    else:
        monkeypatch.setenv("ZALO_BOT_DISPLAY_NAME", configured_name)
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()

    _run(
        adapter._dispatch_update(
            _message_update(
                chat_id="group-boundaries" if chat_type == "GROUP" else None,
                chat_type=chat_type,
                text=text,
            )
        )
    )

    event = adapter.handle_message.await_args.args[0]
    assert event.text == text
    assert event.get_command() is None
    assert event.get_command_args() == text


def test_group_sessions_stay_separate_per_member_chat_and_from_dm(adapter):
    received = []

    async def handle_message(event):
        received.append(event)

    adapter.handle_message = handle_message
    adapter._message_handler = object()
    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="member-a",
                chat_id="group-1",
                message_id="g-1",
                chat_type="GROUP",
            )
        )
    )
    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="member-b",
                chat_id="group-1",
                message_id="g-2",
                chat_type="GROUP",
            )
        )
    )
    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="member-a",
                chat_id="group-2",
                message_id="g-3",
                chat_type="GROUP",
            )
        )
    )
    _run(
        adapter._dispatch_update(_message_update(user_id="member-a", message_id="d-1"))
    )

    keys = [build_session_key(event.source) for event in received]
    assert keys[0] != keys[1]
    assert keys[0] != keys[2]
    assert keys[0] != keys[3]


def test_get_chat_info_reports_observed_group_and_unknown_metadata(adapter):
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="member-a",
                chat_id="group-1",
                message_id="g-1",
                chat_type="GROUP",
            )
        )
    )
    _run(
        adapter._dispatch_update(_message_update(user_id="member-a", message_id="d-1"))
    )

    assert _run(adapter.get_chat_info("group-1"))["type"] == "group"
    assert _run(adapter.get_chat_info("member-a"))["type"] == "dm"
    assert _run(adapter.get_chat_info("unseen-chat"))["type"] == "unknown"


def test_get_chat_info_reports_unknown_for_evicted_metadata(adapter):
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()

    async def dispatch_updates():
        for index in range(513):
            await adapter._dispatch_update(
                _message_update(
                    user_id=f"member-{index}",
                    chat_id=f"group-{index}",
                    message_id=f"message-{index}",
                    chat_type="GROUP",
                )
            )

    _run(dispatch_updates())

    assert _run(adapter.get_chat_info("group-0"))["type"] == "unknown"
    assert _run(adapter.get_chat_info("group-512"))["type"] == "group"


def test_malformed_unsupported_and_self_events_never_dispatch(adapter):
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    cases = [
        {"event_name": "message.image.received", "message": {}},
        _message_update(chat_type="CHANNEL"),
        _message_update(chat_type=""),
        _message_update(chat_type=[]),
        _message_update(chat_type={}),
        _message_update(is_bot=True),
        {"event_name": "message.text.received", "message": None},
        {"event_name": "message.text.received", "message": {"text": "x"}},
        _message_update(text=None),
        _message_update(text=123),
    ]

    for update in cases:
        _run(adapter._dispatch_update(update))

    assert adapter.handle_message.await_count == 0


def test_unsupported_event_routes_through_message_handler_without_direct_send(
    adapter,
):
    received = []

    async def handle_message(event):
        received.append(event)

    adapter.handle_message = handle_message
    adapter._message_handler = object()
    adapter.send = AsyncMock()

    _run(
        adapter._dispatch_update(
            _message_update(
                user_id="sender-1",
                chat_id="chat-1",
                chat_type="GROUP",
                message_id="unsupported-1",
                event_name="message.unsupported.received",
            )
        )
    )

    assert adapter.send.await_count == 0
    assert len(received) == 1
    event = received[0]
    assert event.message_type.value == "text"
    assert event.source.chat_type == "group"
    assert event.source.chat_id == "chat-1"
    assert event.source.user_id == "sender-1"
    assert event.media_urls == []
    assert event.media_types == []
    text = event.text.casefold()
    assert any(
        marker in text for marker in ("chưa hỗ trợ", "không hỗ trợ", "unsupported")
    )
    assert "pdf" not in text
    assert "excel" not in text


def test_invalid_getme_credentials_fail_fatal_and_sanitize_provider_details(
    adapter, caplog
):
    provider_detail = f"invalid credential detail {TOKEN}"

    async def handler(request):
        return _response(
            request,
            {
                "ok": False,
                "error_code": 401,
                "description": provider_detail,
            },
        )

    async def connect():
        return await _using_client(adapter, handler, adapter.connect)

    with caplog.at_level(logging.DEBUG):
        connected = _run(connect())

    assert connected is False
    assert adapter.has_fatal_error is True
    assert adapter.fatal_error_retryable is False
    assert TOKEN not in (adapter.fatal_error_message or "")
    assert provider_detail not in caplog.text
    assert TOKEN not in caplog.text


def test_malformed_api_response_raises_sanitized_numeric_error(
    adapter, zalo_module, caplog
):
    provider_detail = f"malformed response {TOKEN}"

    async def handler(request):
        return _response(request, {"ok": True, "detail": provider_detail})

    async def request():
        return await _using_client(adapter, handler, lambda: adapter._request("getMe"))

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(zalo_module.ZaloAPIError) as raised,
    ):
        _run(request())

    error = raised.value
    assert isinstance(error.code, int)
    assert TOKEN not in str(error)
    assert provider_detail not in str(error)
    assert TOKEN not in caplog.text
    assert provider_detail not in caplog.text


def test_network_error_is_retryable_but_sanitized(adapter, zalo_module, caplog):
    async def handler(request):
        raise httpx.ConnectError(f"connect failed for {TOKEN}", request=request)

    async def request():
        return await _using_client(adapter, handler, lambda: adapter._request("getMe"))

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(zalo_module.ZaloAPIError) as raised,
    ):
        _run(request())

    error = raised.value
    assert isinstance(error.code, int)
    assert error.retryable is True
    assert TOKEN not in str(error)
    assert TOKEN not in caplog.text


def test_existing_webhook_fails_closed_without_deleting_it(
    adapter, monkeypatch, zalo_module, caplog
):
    calls = []

    async def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/getMe"):
            return _valid_get_me(request)
        if request.url.path.endswith("/getWebhookInfo"):
            return _response(
                request,
                {
                    "ok": True,
                    "result": {"url": "https://operator.example/zalo-hook"},
                },
            )
        raise AssertionError(f"unexpected endpoint: {request.url.path}")

    clients = _patch_client_factory(monkeypatch, zalo_module, handler)
    with caplog.at_level(logging.DEBUG):
        connected = _run(adapter.connect())

    assert connected is False
    assert adapter.has_fatal_error is True
    assert sum(path.endswith("/getWebhookInfo") for path in calls) == 1
    assert not any(path.endswith("/deleteWebhook") for path in calls)
    assert not any(path.endswith("/getUpdates") for path in calls)
    assert TOKEN not in caplog.text

    async def close_clients():
        await asyncio.gather(*(client.aclose() for client in clients))

    _run(close_clients())


def test_polling_survives_malformed_update_transient_error_and_idle_408(
    adapter, caplog
):
    async def scenario():
        requests = []
        reached_final = asyncio.Event()
        valid_update = _message_update(
            user_id="poll-user", chat_id="poll-user", message_id="poll-1"
        )
        scripted = [
            (200, {"ok": True}),
            (
                200,
                {
                    "ok": True,
                    "result": _message_update(chat_type="CHANNEL"),
                },
            ),
            (
                200,
                {
                    "ok": False,
                    "error_code": 500,
                    "description": f"temporary backend detail {TOKEN}",
                },
            ),
            (
                200,
                {
                    "ok": False,
                    "error_code": 408,
                    "description": f"long poll idle {TOKEN}",
                },
            ),
            (200, {"ok": True, "result": valid_update}),
        ]
        received = []

        async def handle_message(event):
            received.append(event)

        async def handler(request):
            if not request.url.path.endswith("/getUpdates"):
                raise AssertionError(f"unexpected endpoint: {request.url.path}")
            requests.append(_request_body(request))
            status, payload = scripted.pop(0)
            if not scripted:
                adapter._running = False
                reached_final.set()
            return _response(request, payload, status)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter._client = client
        adapter.handle_message = handle_message
        adapter._message_handler = object()
        adapter._running = True
        poll_task = asyncio.create_task(adapter._poll_loop())
        try:
            await asyncio.wait_for(reached_final.wait(), timeout=2)
            await asyncio.wait_for(asyncio.shield(poll_task), timeout=2)
            return requests, received
        finally:
            if not poll_task.done():
                poll_task.cancel()
                await asyncio.gather(poll_task, return_exceptions=True)
            await client.aclose()

    real_sleep = asyncio.sleep
    original_sleep = asyncio.sleep

    async def no_backoff(_delay):
        await real_sleep(0)

    asyncio.sleep = no_backoff
    try:
        with caplog.at_level(logging.DEBUG):
            requests, received = _run(scenario())
    finally:
        asyncio.sleep = original_sleep

    assert len(requests) == 5
    assert all(request.get("timeout") == "30" for request in requests)
    assert [event.message_id for event in received] == ["poll-1"]
    assert adapter.has_fatal_error is False
    assert TOKEN not in caplog.text


def test_send_chunks_utf16_safe_vietnamese_and_emoji_content_and_returns_last_id(
    adapter,
):
    sent = []

    async def handler(request):
        payload = _request_body(request)
        sent.append(payload)
        message_id = f"sent-{len(sent)}"
        return _response(
            request,
            {"ok": True, "result": {"message_id": message_id}},
        )

    content = "Xin chào — dữ liệu khách hàng 👩🏽‍💻 ✅\n" * 260

    async def send():
        return await _using_client(
            adapter, handler, lambda: adapter.send("private-chat", content)
        )

    result = _run(send())
    chunks = [payload["text"] for payload in sent]

    assert result.success is True
    assert result.message_id == f"sent-{len(chunks)}"
    assert len(chunks) > 1
    assert all(len(chunk.encode("utf-16-le")) // 2 <= 2000 for chunk in chunks)
    assert "".join(chunks) == content
    assert all(payload["chat_id"] == "private-chat" for payload in sent)


def test_ambiguous_send_timeout_does_not_retry_whole_message(adapter, caplog):
    attempts = []

    async def handler(request):
        attempts.append(_request_body(request))
        raise httpx.ReadTimeout(f"ambiguous send {TOKEN}", request=request)

    async def send():
        return await _using_client(
            adapter,
            handler,
            lambda: adapter.send("private-chat", "nội dung chưa xác nhận"),
        )

    with caplog.at_level(logging.DEBUG):
        result = _run(send())

    assert len(attempts) == 1
    assert result.success is False
    assert result.retryable is False
    assert TOKEN not in str(result)
    assert TOKEN not in caplog.text


def test_partial_send_failure_does_not_retry_delivered_chunk(adapter):
    sent = []

    async def handler(request):
        sent.append(_request_body(request))
        if len(sent) == 1:
            return _response(
                request,
                {"ok": True, "result": {"message_id": "first-id"}},
            )
        raise httpx.ReadTimeout("ambiguous continuation", request=request)

    content = "A" * 2000 + "B" * 2000

    async def send():
        return await _using_client(
            adapter, handler, lambda: adapter.send("private-chat", content)
        )

    result = _run(send())

    assert len(sent) == 2
    assert sent[0]["text"] != sent[1]["text"]
    assert result.success is False
    assert result.message_id == "first-id"
    assert result.retryable is False


def test_disconnect_cancels_poll_closes_client_and_restart_uses_new_client(
    adapter, monkeypatch, zalo_module
):
    async def scenario():
        poll_started = [asyncio.Event(), asyncio.Event()]
        poll_blocks = [asyncio.Event(), asyncio.Event()]
        poll_number = 0
        calls = []

        async def handler(request):
            nonlocal poll_number
            calls.append(request.url.path)
            if request.url.path.endswith("/getMe"):
                return _valid_get_me(request)
            if request.url.path.endswith("/getWebhookInfo"):
                return _valid_webhook_info(request)
            if request.url.path.endswith("/getUpdates"):
                index = poll_number
                poll_number += 1
                poll_started[index].set()
                await poll_blocks[index].wait()
                return _response(request, {"ok": True, "result": {}})
            raise AssertionError(f"unexpected endpoint: {request.url.path}")

        clients = _patch_client_factory(monkeypatch, zalo_module, handler)
        first_connect = await adapter.connect()
        assert first_connect is True
        await asyncio.wait_for(poll_started[0].wait(), timeout=2)
        first_task = adapter._poll_task
        await adapter.disconnect()
        first_closed = clients[0].is_closed
        first_done = first_task is None or first_task.done()

        second_connect = await adapter.connect()
        assert second_connect is True
        await asyncio.wait_for(poll_started[1].wait(), timeout=2)
        second_task = adapter._poll_task
        await adapter.disconnect()

        return (
            clients,
            calls,
            first_closed,
            first_done,
            second_task is None or second_task.done(),
            adapter.is_connected,
        )

    clients, calls, first_closed, first_done, second_done, connected = _run(scenario())

    assert first_closed is True
    assert first_done is True
    assert second_done is True
    assert len(clients) == 2
    assert all(client.is_closed for client in clients)
    assert sum(path.endswith("/getMe") for path in calls) == 2
    assert connected is False


def test_image_update_downloads_and_exposes_cached_media(
    adapter, zalo_module, monkeypatch
):
    monkeypatch.setattr(
        zalo_module.adapter,
        "_cache_zalo_image",
        AsyncMock(return_value=("/tmp/hermes-image.jpg", "image/jpeg")),
    )
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    update = {
        "event_name": "message.image.received",
        "message": {
            "from": {
                "id": "image-user",
                "display_name": "Người dùng",
                "is_bot": False,
            },
            "chat": {"id": "image-chat", "chat_type": "PRIVATE"},
            "photo": "https://cdn.example/image.jpg",
            "caption": "Xem ảnh này",
            "message_id": "image-1",
            "date": 1725000000000,
        },
    }

    _run(adapter._dispatch_update(update))

    event = adapter.handle_message.await_args.args[0]
    assert event.text == "Xem ảnh này"
    assert event.media_urls == ["/tmp/hermes-image.jpg"]
    assert event.media_types == ["image/jpeg"]
    assert event.message_type == zalo_module.adapter.MessageType.PHOTO


def test_sticker_update_downloads_and_frames_as_reaction(
    adapter, zalo_module, monkeypatch
):
    monkeypatch.setattr(
        zalo_module.adapter,
        "_cache_zalo_image",
        AsyncMock(return_value=("/tmp/hermes-sticker.webp", "image/webp")),
    )
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    update = {
        "event_name": "message.sticker.received",
        "message": {
            "from": {
                "id": "sticker-user",
                "display_name": "Người dùng",
                "is_bot": False,
            },
            "chat": {"id": "sticker-chat", "chat_type": "PRIVATE"},
            "sticker": "sticker-42",
            "url": "https://stickers.zaloapp.com/sticker-42.webp",
            "message_id": "sticker-1",
            "date": 1725000000000,
        },
    }

    _run(adapter._dispatch_update(update))

    event = adapter.handle_message.await_args.args[0]
    assert event.text == (
        "[The user reacted with a sticker — reply to its intent in one "
        "short natural sentence, do not describe the sticker]"
    )
    assert event.media_urls == ["/tmp/hermes-sticker.webp"]
    assert event.media_types == ["image/webp"]
    assert event.message_type == zalo_module.adapter.MessageType.STICKER


def test_sticker_without_identifier_still_frames_as_reaction(
    adapter, zalo_module, monkeypatch
):
    monkeypatch.setattr(
        zalo_module.adapter,
        "_cache_zalo_image",
        AsyncMock(return_value=("/tmp/hermes-sticker.webp", "image/webp")),
    )
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    update = {
        "event_name": "message.sticker.received",
        "message": {
            "from": {
                "id": "sticker-user",
                "display_name": "Người dùng",
                "is_bot": False,
            },
            "chat": {"id": "sticker-chat", "chat_type": "PRIVATE"},
            "url": "https://stickers.zaloapp.com/sticker-42.webp",
            "message_id": "sticker-2",
            "date": 1725000000000,
        },
    }

    _run(adapter._dispatch_update(update))

    event = adapter.handle_message.await_args.args[0]
    assert event.text == (
        "[The user reacted with a sticker — reply to its intent in one "
        "short natural sentence, do not describe the sticker]"
    )
    assert event.media_urls == ["/tmp/hermes-sticker.webp"]
    assert event.message_type == zalo_module.adapter.MessageType.STICKER


def test_image_download_failure_keeps_caption_and_does_not_pass_remote_url(
    adapter, zalo_module, monkeypatch
):
    monkeypatch.setattr(
        zalo_module.adapter,
        "_cache_zalo_image",
        AsyncMock(return_value=None),
    )
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    update = {
        "event_name": "message.image.received",
        "message": {
            "from": {
                "id": "image-user",
                "display_name": "Người dùng",
                "is_bot": False,
            },
            "chat": {"id": "image-chat", "chat_type": "PRIVATE"},
            "photo": "https://cdn.example/image.jpg",
            "caption": "Không tải được ảnh",
            "message_id": "image-2",
            "date": 1725000000000,
        },
    }

    _run(adapter._dispatch_update(update))

    event = adapter.handle_message.await_args.args[0]
    assert event.text == "Không tải được ảnh"
    assert event.media_urls == []
    assert event.media_types == []


def test_captionless_failed_image_tells_agent_media_was_sent(
    adapter, zalo_module, monkeypatch
):
    monkeypatch.setattr(
        zalo_module.adapter,
        "_cache_zalo_image",
        AsyncMock(return_value=None),
    )
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    update = {
        "event_name": "message.image.received",
        "message": {
            "from": {"id": "u", "display_name": "U", "is_bot": False},
            "chat": {"id": "c", "chat_type": "PRIVATE"},
            "photo": "https://cdn.example/image.jpg",
            "message_id": "image-3",
            "date": 1725000000000,
        },
    }

    _run(adapter._dispatch_update(update))

    event = adapter.handle_message.await_args.args[0]
    assert event.text == "[The user sent an image, but it could not be downloaded]"
    assert event.media_urls == []


def test_voice_update_caches_audio_and_uses_stt_placeholder(
    adapter, zalo_module, monkeypatch
):
    monkeypatch.setattr(
        zalo_module.adapter,
        "_cache_zalo_voice",
        AsyncMock(return_value=("/tmp/hermes-voice.ogg", "audio/ogg")),
    )
    adapter.handle_message = AsyncMock()
    adapter._message_handler = object()
    update = {
        "event_name": "message.voice.received",
        "message": {
            "from": {"id": "voice-user", "display_name": "U", "is_bot": False},
            "chat": {"id": "voice-chat", "chat_type": "PRIVATE"},
            "voice_url": "https://cdn.example/voice.ogg",
            "message_id": "voice-1",
            "date": 1725000000000,
        },
    }

    _run(adapter._dispatch_update(update))

    event = adapter.handle_message.await_args.args[0]
    assert event.media_urls == ["/tmp/hermes-voice.ogg"]
    assert event.media_types == ["audio/ogg"]
    assert event.message_type == zalo_module.adapter.MessageType.VOICE
    # The gateway strips this exact placeholder and prepends the transcript.
    assert event.text == "(The user sent a message with no text content)"
    from gateway.run import (  # noqa: PLC0415 -- defer full gateway entrypoint until fixture-loaded Zalo adapter reaches STT contract
        _event_media_is_stt_input,
    )

    assert _event_media_is_stt_input(event, 0) is True


def test_captionless_photo_url_success_has_no_failure_or_private_log(
    adapter, zalo_module, monkeypatch, caplog
):
    download = AsyncMock(return_value="/tmp/cached.jpg")
    monkeypatch.setattr(zalo_module.adapter, "cache_image_from_url", download)
    adapter.handle_message = AsyncMock()
    update = _message_update()
    update["event_name"] = "message.image.received"
    update["message"].update(
        photo_url="https://example.com/private.jpg?signature=private-marker",
        caption="",
    )
    with caplog.at_level(logging.INFO):
        _run(adapter._dispatch_update(update))
    event = adapter.handle_message.await_args.args[0]
    assert event.media_urls == ["/tmp/cached.jpg"]
    assert "could not be downloaded" not in event.text
    assert "private-marker" not in caplog.text
    assert "media update fields" not in caplog.text


def test_malformed_media_url_is_contained(zalo_module, monkeypatch):
    download = AsyncMock()
    monkeypatch.setattr(zalo_module.adapter, "cache_image_from_url", download)
    assert _run(zalo_module.adapter._cache_zalo_image("https://[invalid")) is None
    download.assert_not_awaited()


def test_voice_mime_matches_cached_container(zalo_module, monkeypatch):
    monkeypatch.setattr(
        zalo_module.adapter,
        "cache_audio_from_url",
        AsyncMock(return_value="/tmp/detected.mp3"),
    )
    assert _run(
        zalo_module.adapter._cache_zalo_voice("https://example.com/voice.ogg")
    ) == ("/tmp/detected.mp3", "audio/mpeg")


def test_typing_accepts_documented_success_without_result(adapter):
    async def handler(request):
        return _response(request, {"ok": True})

    result = _run(
        _using_client(
            adapter,
            handler,
            lambda: adapter._request(
                "sendChatAction", {"chat_id": "test-chat", "action": "typing"}
            ),
        )
    )
    assert result == {}
