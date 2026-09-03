import pytest
from unittest.mock import MagicMock, patch

from src.tools.composio.mail_tools import (
    composio_mail_search,
    composio_mail_send,
    composio_mail_create_draft,
)


def test_mail_search_unauthenticated():
    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=False):
        res = composio_mail_search(7275339077, query="invoice")
        assert res["status"] == "error"
        assert "chưa kết nối" in res["message"].lower() or "not connected" in res["message"].lower()


def test_mail_search_authenticated():
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {
        "messages": [
            {"id": "msg_1", "subject": "Báo giá tháng 9", "sender": "supplier@proteinbar.vn"}
        ]
    }
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.mail_tools.get_composio_client", return_value=mock_client):
        res = composio_mail_search(7275339077, query="Báo giá", max_results=3)
        assert res["status"] == "success"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077")
        mock_session.execute.assert_called_once_with(
            tool_slug="GMAIL_FETCH_EMAILS",
            arguments={"query": "Báo giá", "max_results": 3},
        )


def test_mail_send_success():
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {"message_id": "sent_123", "status": "SENT"}
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.mail_tools.get_composio_client", return_value=mock_client):
        res = composio_mail_send(
            telegram_user_id="7275339077",
            recipient="client@example.com",
            subject="Chào bạn",
            body="Nội dung email test",
        )
        assert res["status"] == "success"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077")
        mock_session.execute.assert_called_once_with(
            tool_slug="GMAIL_SEND_EMAIL",
            arguments={
                "recipient_email": "client@example.com",
                "subject": "Chào bạn",
                "body": "Nội dung email test",
            },
        )


def test_mail_create_draft():
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {"draft_id": "draft_456"}
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.mail_tools.get_composio_client", return_value=mock_client):
        res = composio_mail_create_draft(
            telegram_user_id=7275339077,
            recipient="boss@example.com",
            subject="Kế hoạch tuần",
            body="Bản nháp kế hoạch",
        )
        assert res["status"] == "success"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077")
        mock_session.execute.assert_called_once_with(
            tool_slug="GMAIL_CREATE_EMAIL_DRAFT",
            arguments={
                "recipient_email": "boss@example.com",
                "subject": "Kế hoạch tuần",
                "body": "Bản nháp kế hoạch",
            },
        )
