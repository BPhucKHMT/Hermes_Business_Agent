from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.composio import (  # noqa: E402 -- source path bootstrap above
    mail_tools,
)
from tools.composio.mail_tools import (  # noqa: E402 -- imports follow source path bootstrap
    composio_mail_create_draft,
    composio_mail_get_thread,
    composio_mail_reply,
    composio_mail_search,
    composio_mail_send,
)


def test_composio_mail_search_success():
    mock_session = MagicMock()
    mock_session.execute.return_value = {
        "messages": [{"id": "m1", "subject": "Báo giá tháng 9"}],
        "total": 1,
    }
    mock_client = MagicMock()
    mock_client.create.return_value = mock_session

    with (
        patch("tools.composio.mail_tools.check_connection_status", return_value=True),
        patch(
            "tools.composio.mail_tools.get_composio_client", return_value=mock_client
        ),
        patch(
            "tools.composio.mail_tools.resolve_account_target",
            return_value=(None, "test@gmail.com"),
        ),
        patch(
            "tools.composio.mail_tools.get_user_emails",
            return_value={"c1": "test@gmail.com"},
        ),
    ):
        res = composio_mail_search(7275339077, query="báo giá")
        assert res.get("status") == "success"
        assert res.get("active_mailbox") == "test@gmail.com"
        assert "messages" in res.get("data", {})


def test_composio_mail_search_disconnected():
    with patch("tools.composio.mail_tools.check_connection_status", return_value=False):
        res = composio_mail_search(7275339077, query="báo giá")
        assert res.get("status") == "error"
        assert res.get("error_code") == "NOT_CONNECTED"


def test_composio_mail_get_thread_success():
    mock_session = MagicMock()
    mock_session.execute.return_value = {
        "id": "th_123",
        "messages": [{"id": "m1", "subject": "Họp tuần"}],
    }
    mock_client = MagicMock()
    mock_client.create.return_value = mock_session

    with (
        patch("tools.composio.mail_tools.check_connection_status", return_value=True),
        patch(
            "tools.composio.mail_tools.get_composio_client", return_value=mock_client
        ),
        patch(
            "tools.composio.mail_tools.resolve_account_target",
            return_value=(None, "test@gmail.com"),
        ),
        patch(
            "tools.composio.mail_tools.get_user_emails",
            return_value={"c1": "test@gmail.com"},
        ),
    ):
        res = composio_mail_get_thread(7275339077, thread_id="th_123")
        assert res.get("status") == "success"
        assert res.get("data", {}).get("id") == "th_123"


def test_composio_mail_send_success():
    mock_session = MagicMock()
    mock_session.execute.return_value = {"id": "sent_msg_001"}
    mock_client = MagicMock()
    mock_client.create.return_value = mock_session

    with (
        patch("tools.composio.mail_tools.check_connection_status", return_value=True),
        patch(
            "tools.composio.mail_tools.get_composio_client", return_value=mock_client
        ),
        patch(
            "tools.composio.mail_tools.resolve_account_target",
            return_value=(None, "test@gmail.com"),
        ),
        patch(
            "tools.composio.mail_tools.get_user_emails",
            return_value={"c1": "test@gmail.com"},
        ),
    ):
        res = composio_mail_send(
            7275339077,
            recipient="client@example.com",
            subject="Chào đối tác",
            body="Nội dung hợp đồng",
        )
        assert res.get("status") == "success"
        assert res.get("data", {}).get("id") == "sent_msg_001"


def test_composio_mail_create_draft_success():
    mock_session = MagicMock()
    mock_session.execute.return_value = {"id": "draft_001"}
    mock_client = MagicMock()
    mock_client.create.return_value = mock_session

    with (
        patch("tools.composio.mail_tools.check_connection_status", return_value=True),
        patch(
            "tools.composio.mail_tools.get_composio_client", return_value=mock_client
        ),
        patch(
            "tools.composio.mail_tools.resolve_account_target",
            return_value=(None, "test@gmail.com"),
        ),
        patch(
            "tools.composio.mail_tools.get_user_emails",
            return_value={"c1": "test@gmail.com"},
        ),
    ):
        res = composio_mail_create_draft(
            7275339077,
            recipient="client@example.com",
            subject="Nháp",
            body="Bản thảo",
        )
        assert res.get("status") == "success"


def test_composio_mail_reply_success():
    mock_session = MagicMock()
    mock_session.execute.return_value = {"id": "reply_001"}
    mock_client = MagicMock()
    mock_client.create.return_value = mock_session

    with (
        patch("tools.composio.mail_tools.check_connection_status", return_value=True),
        patch(
            "tools.composio.mail_tools.get_composio_client", return_value=mock_client
        ),
        patch(
            "tools.composio.mail_tools.resolve_account_target",
            return_value=(None, "test@gmail.com"),
        ),
        patch(
            "tools.composio.mail_tools.get_user_emails",
            return_value={"c1": "test@gmail.com"},
        ),
    ):
        res = composio_mail_reply(
            7275339077,
            thread_id="th_123",
            body="Đã xác nhận",
        )
        assert res.get("status") == "success"


@pytest.mark.parametrize("toolkit", ["googlesuper", "gmail"])
@pytest.mark.parametrize("operation", ["search", "thread"])
def test_mail_reads_use_selected_accounts_toolkit(monkeypatch, toolkit, operation):
    def execute(*, tool_slug, account, arguments):
        if account != "selected-account":
            raise RuntimeError("Wrong account")
        expected_slug = {
            ("googlesuper", "search"): "GOOGLESUPER_FETCH_EMAILS",
            ("googlesuper", "thread"): "GOOGLESUPER_FETCH_MESSAGE_BY_THREAD_ID",
            ("gmail", "search"): "GMAIL_FETCH_EMAILS",
            ("gmail", "thread"): "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
        }[toolkit, operation]
        if tool_slug != expected_slug:
            raise RuntimeError("No active connection for requested toolkit")
        return {"messages": [{"messageId": "message-1", "threadId": "thread-1"}]}

    client = SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(execute=execute),
        connected_accounts=SimpleNamespace(
            get=lambda account_id: SimpleNamespace(
                id=account_id, toolkit=SimpleNamespace(slug=toolkit)
            )
        ),
    )
    monkeypatch.setattr(mail_tools, "get_composio_client", lambda: client)
    monkeypatch.setattr(mail_tools, "check_connection_status", lambda *a, **k: True)
    monkeypatch.setattr(
        mail_tools,
        "resolve_account_target",
        lambda *a: ("selected-account", "reader@example.invalid"),
    )
    monkeypatch.setattr(
        mail_tools,
        "get_user_emails",
        lambda *a: {"selected-account": "reader@example.invalid"},
    )
    if operation == "search":
        result = composio_mail_search("local:owner:test", query="is:unread")
    else:
        result = composio_mail_get_thread("local:owner:test", thread_id="thread-1")
    assert result["status"] == "success", result
    assert result["data"]["messages"][0]["messageId"] == "message-1"
