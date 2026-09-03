from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.composio.mail_tools import (
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

    with patch("tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.get_composio_client", return_value=mock_client), \
         patch("tools.composio.mail_tools.resolve_account_target", return_value=(None, "test@gmail.com")), \
         patch("tools.composio.mail_tools.get_user_emails", return_value={"c1": "test@gmail.com"}):
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

    with patch("tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.get_composio_client", return_value=mock_client), \
         patch("tools.composio.mail_tools.resolve_account_target", return_value=(None, "test@gmail.com")):
        res = composio_mail_get_thread(7275339077, thread_id="th_123")
        assert res.get("status") == "success"
        assert res.get("data", {}).get("id") == "th_123"
def test_composio_mail_send_success():
    mock_session = MagicMock()
    mock_session.execute.return_value = {"id": "sent_msg_001"}
    mock_client = MagicMock()
    mock_client.create.return_value = mock_session

    with patch("tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.get_composio_client", return_value=mock_client), \
         patch("tools.composio.mail_tools.resolve_account_target", return_value=(None, "test@gmail.com")):
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

    with patch("tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.get_composio_client", return_value=mock_client), \
         patch("tools.composio.mail_tools.resolve_account_target", return_value=(None, "test@gmail.com")):
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

    with patch("tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("tools.composio.mail_tools.get_composio_client", return_value=mock_client), \
         patch("tools.composio.mail_tools.resolve_account_target", return_value=(None, "test@gmail.com")):
        res = composio_mail_reply(
            7275339077,
            thread_id="th_123",
            body="Đã xác nhận",
        )
        assert res.get("status") == "success"
