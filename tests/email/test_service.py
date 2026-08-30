import json
import os
import sys
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"

for p in (PLUGIN, SRC, UPSTREAM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import tools

if str(SRC / "tools") not in tools.__path__:
    tools.__path__.insert(0, str(SRC / "tools"))

from tools.email.service import (
    EmailConnectorService,
    create_http_server,
    make_signed_headers,
)
from tools.email.store import MailStore
from tools.email.policy import MailPolicy
from google.auth.exceptions import RefreshError
from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    ConnectionStatus,
    Destination,
    MailConnection,
    MailboxType,
    SearchHit,
    ThreadResult,
)


class FakeSecretStore:
    def __init__(self):
        self.data = {}

    def put_json(self, name: str, value: dict) -> str:
        ref = f"keyvault://{name}"
        self.data[ref] = value
        return ref

    def get_json(self, secret_ref: str) -> dict:
        return self.data[secret_ref]

    def delete(self, secret_ref: str) -> None:
        self.data.pop(secret_ref, None)


class FakeGmailReader:
    def __init__(self):
        self.calls = []

    def search_threads(self, token_data, query, limit):
        self.calls.append(("search", token_data, query, limit))
        return (
            SearchHit(
                thread_id="t-123",
                subject="Báo giá",
                snippet="Giá 50tr",
                last_message_date="2026-08-26",
                from_address="supplier@whey.vn",
            ),
        )

    def get_thread(self, token_data, thread_id, text_bytes_max):
        self.calls.append(("thread", token_data, thread_id, text_bytes_max))
        return ThreadResult(
            thread_id=thread_id, subject="Báo giá", text="Nội dung báo giá 50tr"
        )

    def get_attachment(self, token_data, message_id, attachment_id):
        self.calls.append(("attachment", token_data, message_id, attachment_id))
        return b"mock-pdf-bytes"


class FakeOAuthManager:
    def __init__(self):
        self.calls = []

    def create_authorization_start(self, principal_id):
        self.calls.append(principal_id)
        return SimpleNamespace(
            url="https://accounts.google.com/o/oauth2/v2/auth?real=1",
            state="opaque-state",
            request_id="link-real",
        )

    def complete_callback(self, state, code):
        self.calls.append(("callback", state, code))
        return MailConnection(
            connection_id="conn-callback",
            owner_principal_id="telegram:bot:alice",
            mailbox_type=MailboxType.PERSONAL,
            masked_address="a***@gmail.com",
            provider_subject_hash="sub-callback",
            secret_ref="keyvault://conn-callback",
            granted_scopes=(GMAIL_READONLY_SCOPE,),
            status="connected",
        )


@pytest.fixture
def service_env(tmp_path):
    db_path = tmp_path / "mail_state.db"
    store = MailStore(db_path)
    secrets = FakeSecretStore()
    secrets.put_json("conn-alice", {"token": "fake-token"})

    conn = MailConnection(
        connection_id="conn-alice",
        owner_principal_id="telegram:bot:alice",
        mailbox_type=MailboxType.PERSONAL,
        masked_address="a***@gmail.com",
        provider_subject_hash="sub-alice",
        secret_ref="keyvault://conn-alice",
        granted_scopes=(GMAIL_READONLY_SCOPE,),
        status="connected",
    )
    store.add_connection(conn)

    policy = MailPolicy(store=store, operator_allowlist=("999",))
    oauth = FakeOAuthManager()
    gmail = FakeGmailReader()
    service = EmailConnectorService(
        store=store,
        secret_store=secrets,
        policy=policy,
        gmail_reader=gmail,
        oauth_manager=oauth,
        shared_secret="test-hmac-secret-123",
    )
    return SimpleNamespace(
        service=service, store=store, secrets=secrets, oauth=oauth, gmail=gmail
    )


def test_unsigned_request_rejected(service_env):
    payload = {"caller": {"principal_id": "telegram:bot:alice", "chat_type": "dm"}}
    res = service_env.service.handle_internal_request(
        "POST", "/v1/search", json.dumps(payload).encode("utf-8"), headers={}
    )
    assert res.status == 401


def test_signed_dm_search_succeeds(service_env):
    payload = {
        "caller": {
            "principal_id": "telegram:bot:alice",
            "platform": "telegram",
            "user_id": "alice",
            "chat_id": "alice",
            "thread_id": None,
            "chat_type": "dm",
        },
        "query": "newer_than:7d",
    }
    body = json.dumps(payload).encode("utf-8")
    headers = make_signed_headers("POST", "/v1/search", body, "test-hmac-secret-123")
    res = service_env.service.handle_internal_request(
        "POST", "/v1/search", body, headers=headers
    )
    assert res.status == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["ok"] is True
    assert len(data["result"]["hits"]) == 1
    assert data["result"]["hits"][0]["thread_id"] == "t-123"
    assert service_env.gmail.calls == [
        ("search", {"token": "fake-token"}, "newer_than:7d", 10)
    ]
    audit = service_env.store.list_audit_events()
    assert [(event.event_type, event.outcome) for event in audit] == [("search", "ok")]
    assert audit[0].query_hash != "newer_than:7d"
    assert b"newer_than:7d" not in service_env.store.db_path.read_bytes()


def test_signed_group_search_redirects_to_dm(service_env):
    payload = {
        "caller": {
            "principal_id": "telegram:bot:alice",
            "platform": "telegram",
            "user_id": "alice",
            "chat_id": "-1003835812097",
            "thread_id": "11",
            "chat_type": "group",
        },
        "query": "newer_than:7d",
    }
    body = json.dumps(payload).encode("utf-8")
    headers = make_signed_headers("POST", "/v1/search", body, "test-hmac-secret-123")
    res = service_env.service.handle_internal_request(
        "POST", "/v1/search", body, headers=headers
    )
    assert res.status == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["ok"] is True
    assert data["result"]["delivery"] == "redirect_to_dm"
    assert "Mở chat riêng" in data["result"]["public_text"]
    assert service_env.gmail.calls == []
    assert service_env.store.list_audit_events()[-1].outcome == "redirect_to_dm"


def test_oauth_start_and_disconnect_use_real_composed_dependencies(service_env):
    caller = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    start_body = json.dumps({"caller": caller}).encode("utf-8")
    start = service_env.service.handle_internal_request(
        "POST",
        "/v1/oauth/start",
        start_body,
        make_signed_headers(
            "POST", "/v1/oauth/start", start_body, "test-hmac-secret-123"
        ),
    )
    start_data = json.loads(start.body)

    disconnect_body = json.dumps(
        {"caller": caller, "connection_id": "conn-alice"}
    ).encode("utf-8")
    disconnect = service_env.service.handle_internal_request(
        "POST",
        "/v1/disconnect",
        disconnect_body,
        make_signed_headers(
            "POST", "/v1/disconnect", disconnect_body, "test-hmac-secret-123"
        ),
    )
    disconnect_data = json.loads(disconnect.body)

    assert start_data["result"]["authorization_url"].startswith(
        "https://accounts.google.com/"
    )
    assert service_env.oauth.calls == ["telegram:bot:alice"]
    assert disconnect_data["result"]["status"] == "revoked"
    assert service_env.store.list_connections("telegram:bot:alice") == ()
    assert "keyvault://conn-alice" not in service_env.secrets.data
    assert service_env.store.list_audit_events()[-1].event_type == "revoke"
    assert service_env.store.list_audit_events()[-1].outcome == "revoked"


def test_oauth_start_fails_closed_without_oauth_manager(service_env):
    service_env.service.oauth_manager = None
    body = json.dumps(
        {"caller": {"principal_id": "telegram:bot:alice", "chat_type": "dm"}}
    ).encode("utf-8")
    response = service_env.service.handle_internal_request(
        "POST",
        "/v1/oauth/start",
        body,
        make_signed_headers("POST", "/v1/oauth/start", body, "test-hmac-secret-123"),
    )
    data = json.loads(response.body)
    assert response.status == 503
    assert data["ok"] is False
    assert data["error"]["code"] == "oauth_not_configured"


def test_thread_and_status_calls_are_audited(service_env):
    caller = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    thread = _signed_request(
        service_env.service,
        "POST",
        "/v1/thread",
        {"caller": caller, "thread_id": "t-123"},
    )
    status = _signed_request(
        service_env.service,
        "GET",
        "/v1/connections",
        {"caller": caller},
    )

    assert json.loads(thread.body)["result"]["thread"]["thread_id"] == "t-123"
    assert json.loads(status.body)["result"]["connections"][0]["status"] == "connected"
    assert [event.event_type for event in service_env.store.list_audit_events()] == [
        "thread",
        "status",
    ]


def _signed_request(service, method, path, payload):
    body = json.dumps(payload).encode("utf-8")
    return service.handle_internal_request(
        method,
        path,
        body,
        make_signed_headers(method, path, body, "test-hmac-secret-123"),
    )


def test_public_http_callback_completes_oauth_without_exposing_account(service_env):
    server = create_http_server(service_env.service, "127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urlopen(
            f"http://127.0.0.1:{port}/gmail/oauth/callback?state=opaque&code=code",
            timeout=5,
        ) as response:
            body = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Gmail connected" in body
    assert "a***@gmail.com" not in body
    assert service_env.oauth.calls == [("callback", "opaque", "code")]
    assert service_env.store.list_audit_events()[-1].event_type == "connect"


def test_owner_proposes_and_numeric_operator_approves_shared_grant(service_env):
    owner = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    proposed = _signed_request(
        service_env.service,
        "POST",
        "/v1/grants/propose",
        {
            "caller": owner,
            "connection_id": "conn-alice",
            "destination": {
                "platform": "telegram",
                "chat_id": "-1001",
                "thread_id": "11",
            },
        },
    )
    request_id = json.loads(proposed.body)["result"]["request_id"]

    operator = {
        "principal_id": "telegram:bot:999",
        "platform": "telegram",
        "user_id": "999",
        "chat_id": "999",
        "chat_type": "dm",
    }
    decided = _signed_request(
        service_env.service,
        "POST",
        "/v1/grants/decide",
        {"caller": operator, "request_id": request_id, "decision": "approve"},
    )

    assert proposed.status == 200
    assert json.loads(decided.body)["result"]["status"] == "approved"
    assert (
        service_env.store.destination_grant(
            "conn-alice",
            Destination("telegram", "-1001", "11"),
        )
        is not None
    )
    assert [event.event_type for event in service_env.store.list_audit_events()] == [
        "grant",
        "grant",
    ]


def test_operator_denial_is_audited_without_creating_grant(service_env):
    owner = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    proposed = _signed_request(
        service_env.service,
        "POST",
        "/v1/grants/propose",
        {
            "caller": owner,
            "connection_id": "conn-alice",
            "destination": {"platform": "telegram", "chat_id": "-1001"},
        },
    )
    request_id = json.loads(proposed.body)["result"]["request_id"]
    denied = _signed_request(
        service_env.service,
        "POST",
        "/v1/grants/decide",
        {
            "caller": {
                "principal_id": "telegram:bot:999",
                "platform": "telegram",
                "user_id": "999",
                "chat_id": "999",
                "chat_type": "dm",
            },
            "request_id": request_id,
            "decision": "deny",
        },
    )

    assert json.loads(denied.body)["result"]["status"] == "denied"
    assert (
        service_env.store.destination_grant(
            "conn-alice",
            Destination("telegram", "-1001"),
        )
        is None
    )
    assert service_env.store.list_audit_events()[-1].outcome == "denied"


def test_search_refresh_error_transitions_status_to_reconnect_required(service_env):
    def failing_search(token_data, query, limit):
        raise RefreshError("invalid_grant: Bad Request")

    service_env.gmail.search_threads = failing_search
    caller = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    res = _signed_request(
        service_env.service,
        "POST",
        "/v1/search",
        {"caller": caller, "query": "newer_than:7d"},
    )
    assert res.status == 401
    data = json.loads(res.body)
    assert data["ok"] is False
    assert data["error"]["code"] == "reconnect_required"

    conns = service_env.store.list_connections("telegram:bot:alice")
    assert conns[0].status == ConnectionStatus.RECONNECT_REQUIRED

    last_audit = service_env.store.list_audit_events()[-1]
    assert last_audit.event_type == "token_refresh_failed"
    assert last_audit.outcome == "failed"
    assert last_audit.connection_id == "conn-alice"


def test_thread_refresh_error_transitions_status_to_reconnect_required(service_env):
    def failing_thread(token_data, thread_id, text_bytes_max):
        raise RefreshError("invalid_grant: Bad Request")

    service_env.gmail.get_thread = failing_thread
    caller = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    res = _signed_request(
        service_env.service,
        "POST",
        "/v1/thread",
        {"caller": caller, "thread_id": "t-123"},
    )
    assert res.status == 401
    data = json.loads(res.body)
    assert data["ok"] is False
    assert data["error"]["code"] == "reconnect_required"

    conns = service_env.store.list_connections("telegram:bot:alice")
    assert conns[0].status == ConnectionStatus.RECONNECT_REQUIRED


def test_attachment_happy_path_and_security(service_env):
    # 1. Missing params
    caller = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    res_bad = _signed_request(
        service_env.service,
        "POST",
        "/v1/attachment",
        {"caller": caller, "message_id": "m-1"},
    )
    assert res_bad.status == 400
    assert json.loads(res_bad.body)["error"]["code"] == "missing_attachment_params"

    # 2. Unauthorized caller
    res_unauth = _signed_request(
        service_env.service,
        "POST",
        "/v1/attachment",
        {
            "caller": {
                "principal_id": "telegram:bot:stranger",
                "platform": "telegram",
                "user_id": "stranger",
                "chat_id": "stranger",
                "chat_type": "dm",
            },
            "message_id": "m-1",
            "attachment_id": "att-1",
        },
    )
    assert res_unauth.status == 404
    assert json.loads(res_unauth.body)["error"]["code"] == "not_authorized"

    # 3. Group caller redirects to DM for personal mailbox
    res_group = _signed_request(
        service_env.service,
        "POST",
        "/v1/attachment",
        {
            "caller": {
                "principal_id": "telegram:bot:alice",
                "platform": "telegram",
                "user_id": "alice",
                "chat_id": "-100group",
                "chat_type": "group",
            },
            "message_id": "m-1",
            "attachment_id": "att-1",
        },
    )
    assert res_group.status == 200
    assert json.loads(res_group.body)["result"]["delivery"] == "redirect_to_dm"

    # 4. Valid DM caller succeeds
    res_ok = _signed_request(
        service_env.service,
        "POST",
        "/v1/attachment",
        {"caller": caller, "message_id": "m-1", "attachment_id": "att-1"},
    )
    assert res_ok.status == 200
    res_data = json.loads(res_ok.body)["result"]
    assert res_data["delivery"] == "dm"
    assert res_data["message_id"] == "m-1"
    assert res_data["attachment_id"] == "att-1"
    assert res_data["size"] == len(b"mock-pdf-bytes")
    import base64
    assert base64.b64decode(res_data["data"]) == b"mock-pdf-bytes"

    last_audit = service_env.store.list_audit_events()[-1]
    assert last_audit.event_type == "attachment"
    assert last_audit.outcome == "ok"
    assert last_audit.connection_id == "conn-alice"


def test_attachment_refresh_error_transitions_status(service_env):
    def failing_attachment(token_data, message_id, attachment_id):
        raise RefreshError("invalid_grant: Bad Request")

    service_env.gmail.get_attachment = failing_attachment
    caller = {
        "principal_id": "telegram:bot:alice",
        "platform": "telegram",
        "user_id": "alice",
        "chat_id": "alice",
        "chat_type": "dm",
    }
    res = _signed_request(
        service_env.service,
        "POST",
        "/v1/attachment",
        {"caller": caller, "message_id": "m-1", "attachment_id": "att-1"},
    )
    assert res.status == 401
    data = json.loads(res.body)
    assert data["ok"] is False
    assert data["error"]["code"] == "reconnect_required"

    conns = service_env.store.list_connections("telegram:bot:alice")
    assert conns[0].status == ConnectionStatus.RECONNECT_REQUIRED

    last_audit = service_env.store.list_audit_events()[-1]
    assert last_audit.event_type == "token_refresh_failed"
    assert last_audit.outcome == "failed"
