import pytest
from unittest.mock import MagicMock, patch
from composio import Action

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
    mock_entity = MagicMock()
    mock_entity.execute.return_value = {
        "messages": [
            {"id": "msg_1", "subject": "Báo giá tháng 9", "sender": "supplier@proteinbar.vn"}
        ]
    }
    mock_client.get_entity.return_value = mock_entity

    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.mail_tools.get_composio_client", return_value=mock_client):
        res = composio_mail_search(7275339077, query="Báo giá", max_results=3)
        assert res["status"] == "success"
        assert len(res["data"]["messages"]) == 1
        mock_client.get_entity.assert_called_once_with(id="telegram_7275339077")
        mock_entity.execute.assert_called_once_with(
            action=Action.GMAIL_FETCH_EMAILS,
            params={"query": "Báo giá", "max_results": 3},
        )


def test_mail_send_success():
    mock_client = MagicMock()
    mock_entity = MagicMock()
    mock_entity.execute.return_value = {"message_id": "sent_123", "status": "SENT"}
    mock_client.get_entity.return_value = mock_entity

    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.mail_tools.get_composio_client", return_value=mock_client):
        res = composio_mail_send(
            telegram_user_id="7275339077",
            recipient="client@example.com",
            subject="Chào bạn",
            body="Nội dung email test",
        )
        assert res["status"] == "success"
        mock_client.get_entity.assert_called_once_with(id="telegram_7275339077")
        mock_entity.execute.assert_called_once_with(
            action=Action.GMAIL_SEND_EMAIL,
            params={
                "recipient_email": "client@example.com",
                "subject": "Chào bạn",
                "body": "Nội dung email test",
            },
        )


def test_mail_create_draft():
    mock_client = MagicMock()
    mock_entity = MagicMock()
    mock_entity.execute.return_value = {"draft_id": "draft_456"}
    mock_client.get_entity.return_value = mock_entity

    with patch("src.tools.composio.mail_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.mail_tools.get_composio_client", return_value=mock_client):
        res = composio_mail_create_draft(
            telegram_user_id=7275339077,
            recipient="boss@example.com",
            subject="Kế hoạch tuần",
            body="Bản nháp kế hoạch",
        )
        assert res["status"] == "success"
        mock_client.get_entity.assert_called_once_with(id="telegram_7275339077")
        mock_entity.execute.assert_called_once_with(
            action=Action.GMAIL_CREATE_EMAIL_DRAFT,
            params={
                "recipient_email": "boss@example.com",
                "subject": "Kế hoạch tuần",
                "body": "Bản nháp kế hoạch",
            },
        )
