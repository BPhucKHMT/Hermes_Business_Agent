from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"

for p in (SRC, PLUGIN):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from plugin_tools import (
    handle_email_connection_status,
    handle_email_create_draft,
    handle_email_get_thread,
    handle_email_reply,
    handle_email_search,
    handle_email_send,
)
from schemas import (
    EMAIL_CONNECTION_STATUS_SCHEMA,
    EMAIL_CREATE_DRAFT_SCHEMA,
    EMAIL_GET_THREAD_SCHEMA,
    EMAIL_REPLY_SCHEMA,
    EMAIL_SEARCH_SCHEMA,
    EMAIL_SEND_SCHEMA,
)


class FakeCaller:
    def __init__(self, user_id=7275339077):
        self.user_id = user_id
        self.chat_id = str(user_id)
        self.principal_id = f"telegram:hermes-business:{user_id}"


class FakeRegistry:
    def __init__(self, caller):
        self.caller = caller

    def resolve_dm_tool(self, **kwargs):
        return self.caller


def test_email_schemas_are_valid():
    assert EMAIL_SEARCH_SCHEMA["name"] == "email_search"
    assert EMAIL_GET_THREAD_SCHEMA["name"] == "email_get_thread"
    assert EMAIL_SEND_SCHEMA["name"] == "email_send"
    assert EMAIL_CREATE_DRAFT_SCHEMA["name"] == "email_create_draft"
    assert EMAIL_REPLY_SCHEMA["name"] == "email_reply"
    assert EMAIL_CONNECTION_STATUS_SCHEMA["name"] == "email_connection_status"


def test_handle_email_search_tool():
    caller = FakeCaller(7275339077)
    registry = FakeRegistry(caller)
    client = object()

    with patch("tools.composio.auth.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.composio_mail_search", return_value={"status": "success", "data": {"messages": [{"subject": "Hợp đồng"}]}}):
        raw = handle_email_search({"query": "Hợp đồng"}, client=client, registry=registry)
        data = json.loads(raw)
        assert data.get("ok") is True
        assert "result" in data


def test_handle_email_send_tool():
    caller = FakeCaller(7275339077)
    registry = FakeRegistry(caller)
    client = object()
    with patch("tools.composio.auth.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.composio_mail_send", return_value={"status": "success", "data": {"message_id": "sent_123"}}):
        raw = handle_email_send(
            {"recipient": "partner@example.com", "subject": "Test", "body": "Hello"},
            client=client,
            registry=registry,
        )
        data = json.loads(raw)
        assert data.get("ok") is True
        assert data.get("result", {}).get("message_id") == "sent_123"


def test_handle_email_connection_status_tool():
    caller = FakeCaller(7275339077)
    registry = FakeRegistry(caller)
    client = object()

    with patch("tools.composio.auth.list_user_connections", return_value=[{"id": "conn_1", "email": "test@gmail.com", "status": "ACTIVE"}]):
        raw = handle_email_connection_status({}, client=client, registry=registry)
        data = json.loads(raw)
        assert data.get("ok") is True
        assert data.get("result", {}).get("status") == "connected"
