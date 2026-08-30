import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tools

if str(SRC / "tools") not in tools.__path__:
    tools.__path__.insert(0, str(SRC / "tools"))

from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    AuditEvent,
    ConnectionStatus,
    Destination,
    GrantRequestStatus,
    MailboxType,
    MailConnection,
    OAuthLinkRequest,
    SharedGrantRequest,
)
from tools.email.store import MailStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "mail_state.db"
    return MailStore(db_path)


def connection_factory(
    connection_id: str, owner: str = "telegram:bot:111"
) -> MailConnection:
    return MailConnection(
        connection_id=connection_id,
        owner_principal_id=owner,
        mailbox_type=MailboxType.PERSONAL,
        masked_address=f"{connection_id}***@gmail.com",
        provider_subject_hash=f"sub-hash-{connection_id}",
        secret_ref=f"keyvault://{connection_id}",
        granted_scopes=(GMAIL_READONLY_SCOPE,),
        status="connected",
    )


def test_add_and_list_connections(store):
    store.add_connection(connection_factory("conn-1", "telegram:bot:111"))
    store.add_connection(connection_factory("conn-2", "telegram:bot:111"))
    store.add_connection(connection_factory("conn-3", "telegram:bot:222"))

    c111 = store.list_connections("telegram:bot:111")
    assert len(c111) == 2
    assert {c.connection_id for c in c111} == {"conn-1", "conn-2"}


def test_fourth_connection_is_rejected(store):
    for i in range(3):
        store.add_connection(connection_factory(f"conn-{i}", "telegram:bot:111"))
    with pytest.raises(ValueError, match="connection_limit_exceeded"):
        store.add_connection(connection_factory("conn-4", "telegram:bot:111"))


def test_oauth_link_request_consumption_is_atomic(store):
    req = OAuthLinkRequest(
        request_id="req-1",
        principal_id="telegram:bot:111",
        nonce_hash="nonce-123",
        pkce_secret_ref="keyvault://pkce-1",
        expires_at="2099-01-01T00:00:00Z",
    )
    store.create_link_request(req)
    consumed = store.consume_link_request("req-1", "nonce-123", "telegram:bot:111")
    assert consumed.request_id == "req-1"

    with pytest.raises(PermissionError, match="oauth_request_already_used"):
        store.consume_link_request("req-1", "nonce-123", "telegram:bot:111")


def test_shared_grant_request_lifecycle_and_operator_approval(store):
    conn = connection_factory("conn-shared", "telegram:bot:111")
    store.add_connection(conn)

    dest = Destination(platform="telegram", chat_id="-1003835812097", thread_id="11")
    grant_req = SharedGrantRequest(
        request_id="grant-req-1",
        connection_id="conn-shared",
        requested_by="telegram:bot:111",
        destination=dest,
        status=GrantRequestStatus.PENDING,
        expires_at="2099-01-01T00:00:00Z",
    )
    store.create_grant_request(grant_req)

    # Owner cannot self-approve
    with pytest.raises(PermissionError, match="operator_required"):
        store.decide_grant_request(
            request_id="grant-req-1",
            operator_principal_id="telegram:bot:111",
            operator_allowlist=("telegram:bot:999",),
            approve=True,
        )

    # Legitimate operator approval
    decided = store.decide_grant_request(
        request_id="grant-req-1",
        operator_principal_id="telegram:bot:999",
        operator_allowlist=("telegram:bot:999",),
        approve=True,
    )
    assert decided.status == GrantRequestStatus.APPROVED

    # Check destination grant active
    grant = store.destination_grant("conn-shared", dest)
    assert grant is not None
    assert grant.connection_id == "conn-shared"

    # Changed destination has no grant
    wrong_dest = Destination(
        platform="telegram", chat_id="-1003835812097", thread_id="12"
    )
    assert store.destination_grant("conn-shared", wrong_dest) is None


def test_expired_oauth_request_is_rejected(store):
    req = OAuthLinkRequest(
        request_id="expired-oauth",
        principal_id="telegram:bot:111",
        nonce_hash="nonce-expired",
        pkce_secret_ref="keyvault://pkce-expired",
        expires_at="2000-01-01T00:00:00+00:00",
    )
    store.create_link_request(req)

    with pytest.raises(PermissionError, match="oauth_request_expired"):
        store.consume_link_request(
            "expired-oauth",
            "nonce-expired",
            "telegram:bot:111",
        )


def test_expired_grant_request_cannot_be_approved(store):
    store.add_connection(connection_factory("conn-expired", "telegram:bot:111"))
    store.create_grant_request(
        SharedGrantRequest(
            request_id="grant-expired",
            connection_id="conn-expired",
            requested_by="telegram:bot:111",
            destination=Destination("telegram", "-1001", None),
            status=GrantRequestStatus.PENDING,
            expires_at="2000-01-01T00:00:00+00:00",
        )
    )

    with pytest.raises(ValueError, match="grant_request_expired"):
        store.decide_grant_request(
            "grant-expired",
            "telegram:bot:999",
            ("telegram:bot:999",),
            approve=True,
        )

    assert (
        store.destination_grant(
            "conn-expired",
            Destination("telegram", "-1001", None),
        )
        is None
    )


def test_audit_store_contains_only_opaque_metadata(store):
    event = AuditEvent(
        event_id="audit-1",
        event_type="search",
        principal_id="telegram:bot:111",
        connection_id="conn-1",
        destination_hash="dest-sha256",
        query_hash="query-sha256",
        occurred_at="2026-08-26T00:00:00+00:00",
        outcome="ok",
    )

    store.append_audit(event)

    assert store.list_audit_events() == (event,)
    schema = store.db_path.read_bytes()
    for forbidden in (
        b"raw@example.com",
        b"refresh_token",
        b"message body",
    ):
        assert forbidden not in schema


def test_update_connection_status(store):
    conn = connection_factory("conn-status-test", "telegram:bot:111")
    store.add_connection(conn)

    conns = store.list_connections("telegram:bot:111")
    assert conns[0].status == ConnectionStatus.CONNECTED

    store.update_connection_status("conn-status-test", ConnectionStatus.RECONNECT_REQUIRED)
    conns = store.list_connections("telegram:bot:111")
    assert conns[0].status == ConnectionStatus.RECONNECT_REQUIRED
