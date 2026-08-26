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
    def search_threads(self, token_data, query, limit):
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
        return ThreadResult(thread_id=thread_id, subject="Báo giá", text="Nội dung báo giá 50tr")


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
    service = EmailConnectorService(
        store=store,
        secret_store=secrets,
        policy=policy,
        gmail_reader=FakeGmailReader(),
        shared_secret="test-hmac-secret-123",
    )
    return service


def test_unsigned_request_rejected(service_env):
    payload = {"caller": {"principal_id": "telegram:bot:alice", "chat_type": "dm"}}
    res = service_env.handle_internal_request("POST", "/v1/search", json.dumps(payload).encode("utf-8"), headers={})
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
    res = service_env.handle_internal_request("POST", "/v1/search", body, headers=headers)
    assert res.status == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["ok"] is True
    assert len(data["result"]["hits"]) == 1
    assert data["result"]["hits"][0]["thread_id"] == "t-123"


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
    res = service_env.handle_internal_request("POST", "/v1/search", body, headers=headers)
    assert res.status == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["ok"] is True
    assert data["result"]["delivery"] == "redirect_to_dm"
    assert "Mở chat riêng" in data["result"]["public_text"]
