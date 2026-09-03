import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/.hermes/plugins/email-connector"))

from plugin_tools import (
    handle_email_send,
    handle_email_create_draft,
    handle_email_reply,
    handle_email_search,
    handle_email_get_thread,
)
from schemas import (
    EMAIL_SEND_SCHEMA,
    EMAIL_CREATE_DRAFT_SCHEMA,
    EMAIL_REPLY_SCHEMA,
)


class FakeCaller:
    def __init__(self, user_id="7275339077"):
        self.principal_id = f"telegram:default:{user_id}"
        self.user_id = str(user_id)
        self.chat_id = str(user_id)
        self.chat_type = "dm"


class FakeRegistry:
    def __init__(self, caller):
        self.caller = caller

    def resolve_dm_tool(self, task_id: str, session_id: str):
        return self.caller


def test_outbound_schemas_valid():
    assert EMAIL_SEND_SCHEMA["name"] == "email_send"
    assert "recipient" in EMAIL_SEND_SCHEMA["parameters"]["required"]
    assert "subject" in EMAIL_SEND_SCHEMA["parameters"]["required"]
    assert "body" in EMAIL_SEND_SCHEMA["parameters"]["required"]

    assert EMAIL_CREATE_DRAFT_SCHEMA["name"] == "email_create_draft"
    assert "recipient" in EMAIL_CREATE_DRAFT_SCHEMA["parameters"]["required"]

    assert EMAIL_REPLY_SCHEMA["name"] == "email_reply"
    assert "thread_id" in EMAIL_REPLY_SCHEMA["parameters"]["required"]
    assert "body" in EMAIL_REPLY_SCHEMA["parameters"]["required"]


def test_handle_email_send_success():
    caller = FakeCaller()
    registry = FakeRegistry(caller)

    with patch("tools.composio.mail_tools.composio_mail_send") as mock_send:
        mock_send.return_value = {"status": "success", "data": {"id": "sent_123"}}
        res_raw = handle_email_send(
            {"recipient": "partner@example.com", "subject": "Báo giá", "body": "Nội dung"},
            registry=registry,
        )
        res = json.loads(res_raw)
        assert res["ok"] is True
        assert res["result"]["id"] == "sent_123"
        mock_send.assert_called_once_with("7275339077", recipient="partner@example.com", subject="Báo giá", body="Nội dung")


def test_handle_email_create_draft_success():
    caller = FakeCaller()
    registry = FakeRegistry(caller)

    with patch("tools.composio.mail_tools.composio_mail_create_draft") as mock_draft:
        mock_draft.return_value = {"status": "success", "data": {"id": "draft_456"}}
        res_raw = handle_email_create_draft(
            {"recipient": "boss@example.com", "subject": "Dự thảo", "body": "Chi tiết dự thảo"},
            registry=registry,
        )
        res = json.loads(res_raw)
        assert res["ok"] is True
        assert res["result"]["id"] == "draft_456"
        mock_draft.assert_called_once_with("7275339077", recipient="boss@example.com", subject="Dự thảo", body="Chi tiết dự thảo")


def test_handle_email_reply_success():
    caller = FakeCaller()
    registry = FakeRegistry(caller)

    with patch("tools.composio.mail_tools.composio_mail_reply") as mock_reply:
        mock_reply.return_value = {"status": "success", "data": {"id": "reply_789"}}
        res_raw = handle_email_reply(
            {"thread_id": "thread_abc123", "body": "Đồng ý với điều khoản"},
            registry=registry,
        )
        res = json.loads(res_raw)
        assert res["ok"] is True
        assert res["result"]["id"] == "reply_789"
        mock_reply.assert_called_once_with("7275339077", thread_id="thread_abc123", body="Đồng ý với điều khoản")
def test_handle_email_search_with_account_email():
    caller = FakeCaller()
    registry = FakeRegistry(caller)

    with patch("tools.composio.auth.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.composio_mail_search") as mock_search:
        mock_search.return_value = {"status": "success", "data": {"messages": [{"id": "m1"}]}}
        res_raw = handle_email_search(
            {"query": "in:inbox", "account_email": "baophuc1204vn@gmail.com"},
            client=object(),
            registry=registry,
        )
        res = json.loads(res_raw)
        assert res["ok"] is True
        mock_search.assert_called_once_with(
            "7275339077",
            query="in:inbox",
            max_results=10,
            account_email="baophuc1204vn@gmail.com",
        )


def test_handle_email_search_auto_detects_account_email():
    caller = FakeCaller()
    registry = FakeRegistry(caller)

    with patch("tools.composio.auth.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.composio_mail_search") as mock_search:
        mock_search.return_value = {"status": "success", "data": {"messages": []}}
        res_raw = handle_email_search(
            {"query": "in:inbox to:nguyenlam.baophuc@gmail.com"},
            client=object(),
            registry=registry,
        )
        res = json.loads(res_raw)
        assert res["ok"] is True
        mock_search.assert_called_once_with(
            "7275339077",
            query="in:inbox to:nguyenlam.baophuc@gmail.com",
            max_results=10,
            account_email="nguyenlam.baophuc@gmail.com",
        )


def test_handle_email_get_thread_success():
    caller = FakeCaller()
    registry = FakeRegistry(caller)

    with patch("tools.composio.auth.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.composio_mail_get_thread") as mock_th:
        mock_th.return_value = {"status": "success", "data": {"threadId": "th_123", "messages": []}}
        res_raw = handle_email_get_thread(
            {"thread_id": "th_123", "account_email": "baophuc1204vn@gmail.com"},
            client=object(),
            registry=registry,
        )
        res = json.loads(res_raw)
        assert res["ok"] is True
        assert res["result"]["threadId"] == "th_123"
        mock_th.assert_called_once_with(
            "7275339077",
            thread_id="th_123",
            account_email="baophuc1204vn@gmail.com",
        )
