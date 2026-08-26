import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
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

from tools.email.service import EmailConnectorService, make_signed_headers
from tools.email.store import MailStore
from tools.email.policy import MailPolicy
from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    MailboxType,
    MailConnection,
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
        return ThreadResult(thread_id=thread_id, subject="Báo giá", text="Nội dung báo giá 50tr")



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

    policy = MailPolicy(store=store, operator_allowlist=("telegram:bot:999",))
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
    return SimpleNamespace(service=service, store=store, secrets=secrets, oauth=oauth, gmail=gmail)


def test_unsigned_request_rejected(service_env):
    payload = {"caller": {"principal_id": "telegram:bot:alice", "chat_type": "dm"}}
    res = service_env.service.handle_internal_request("POST", "/v1/search", json.dumps(payload).encode("utf-8"), headers={})
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
    res = service_env.service.handle_internal_request("POST", "/v1/search", body, headers=headers)
    assert res.status == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["ok"] is True
    assert len(data["result"]["hits"]) == 1
    assert data["result"]["hits"][0]["thread_id"] == "t-123"
    assert service_env.gmail.calls == [
        ("search", {"token": "fake-token"}, "newer_than:7d", 10)
    ]


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
    res = service_env.service.handle_internal_request("POST", "/v1/search", body, headers=headers)
    assert res.status == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["ok"] is True
    assert data["result"]["delivery"] == "redirect_to_dm"
    assert "Mở chat riêng" in data["result"]["public_text"]


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
        make_signed_headers("POST", "/v1/oauth/start", start_body, "test-hmac-secret-123"),
    )
    start_data = json.loads(start.body)

    disconnect_body = json.dumps(
        {"caller": caller, "connection_id": "conn-alice"}
    ).encode("utf-8")
    disconnect = service_env.service.handle_internal_request(
        "POST",
        "/v1/disconnect",
        disconnect_body,
        make_signed_headers("POST", "/v1/disconnect", disconnect_body, "test-hmac-secret-123"),
    )
    disconnect_data = json.loads(disconnect.body)

    assert start_data["result"]["authorization_url"].startswith("https://accounts.google.com/")
    assert service_env.oauth.calls == ["telegram:bot:alice"]
    assert disconnect_data["result"]["status"] == "revoked"
    assert service_env.store.list_connections("telegram:bot:alice") == ()
    assert "keyvault://conn-alice" not in service_env.secrets.data


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
