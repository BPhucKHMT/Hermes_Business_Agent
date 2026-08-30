import os
import sys
from pathlib import Path

# Add src and plugin directly
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_PLUGIN = _SRC / ".hermes/plugins/email-connector"
_UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"

for _p in (_SRC, _PLUGIN, _UPSTREAM):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pytest
from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    MailboxType,
    MailConnection,
    Destination,
    GrantRequestStatus,
    SharedGrantRequest,
)
from tools.email.store import MailStore
from tools.email.policy import MailPolicy, PolicyCaller, DM_REDIRECT_TEXT


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "mail_state.db"
    return MailStore(db_path)


@pytest.fixture
def policy(store):
    return MailPolicy(store=store, operator_allowlist=("telegram:bot:999",))


def connection_factory(
    connection_id: str,
    owner: str = "telegram:bot:111",
    mailbox_type=MailboxType.PERSONAL,
) -> MailConnection:
    return MailConnection(
        connection_id=connection_id,
        owner_principal_id=owner,
        mailbox_type=mailbox_type,
        masked_address=f"{connection_id}***@gmail.com",
        provider_subject_hash=f"sub-hash-{connection_id}",
        secret_ref=f"keyvault://{connection_id}",
        granted_scopes=(GMAIL_READONLY_SCOPE,),
        status="connected",
    )


def test_workspace_tag_never_grants_personal_mail(store, policy):
    conn = connection_factory("conn-alice", owner="telegram:bot:alice")
    store.add_connection(conn)

    caller_bob = PolicyCaller(
        principal_id="telegram:bot:bob",
        platform="telegram",
        user_id="bob",
        chat_id="bob",
        thread_id=None,
        chat_type="dm",
        profile="protein-bar",
        session_key="agent:protein-bar:telegram:dm:bob",
    )

    with pytest.raises(PermissionError):
        policy.authorize_source(caller_bob, "conn-alice")


def test_personal_group_request_redirects_to_dm(store, policy):
    conn = connection_factory("conn-alice", owner="telegram:bot:alice")
    store.add_connection(conn)

    caller_alice_group = PolicyCaller(
        principal_id="telegram:bot:alice",
        platform="telegram",
        user_id="alice",
        chat_id="-1003835812097",
        thread_id="11",
        chat_type="group",
        profile="protein-bar",
        session_key="agent:protein-bar:telegram:group:-1003835812097:11",
    )

    decision = policy.decide_delivery(caller_alice_group, conn)
    assert decision.mode == "redirect_to_dm"
    assert decision.public_text == DM_REDIRECT_TEXT


def test_shared_result_requires_exact_destination(store, policy):
    conn = connection_factory(
        "conn-shared", owner="telegram:bot:alice", mailbox_type=MailboxType.SHARED
    )
    store.add_connection(conn)

    dest = Destination(platform="telegram", chat_id="-1003835812097", thread_id="11")
    req = SharedGrantRequest(
        request_id="grant-1",
        connection_id="conn-shared",
        requested_by="telegram:bot:alice",
        destination=dest,
        status=GrantRequestStatus.PENDING,
        expires_at="2099-01-01T00:00:00Z",
    )
    store.create_grant_request(req)
    store.decide_grant_request(
        "grant-1", "telegram:bot:999", ("telegram:bot:999",), approve=True
    )

    caller_group_topic_11 = PolicyCaller(
        principal_id="telegram:bot:anyone",
        platform="telegram",
        user_id="anyone",
        chat_id="-1003835812097",
        thread_id="11",
        chat_type="group",
        profile="protein-bar",
        session_key="agent:protein-bar:telegram:group:-1003835812097:11",
    )
    decision = policy.decide_delivery(caller_group_topic_11, conn)
    assert decision.mode == "group"

    # Wrong topic fails
    caller_group_topic_12 = PolicyCaller(
        principal_id="telegram:bot:anyone",
        platform="telegram",
        user_id="anyone",
        chat_id="-1003835812097",
        thread_id="12",
        chat_type="group",
        profile="protein-bar",
        session_key="agent:protein-bar:telegram:group:-1003835812097:12",
    )
    with pytest.raises(PermissionError):
        policy.decide_delivery(caller_group_topic_12, conn)
