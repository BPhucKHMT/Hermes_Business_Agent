import pytest
from unittest.mock import MagicMock, patch

from src.tools.composio.calendar_tools import (
    composio_calendar_list_events,
    composio_calendar_create_event,
    composio_calendar_find_free_slots,
)


def test_calendar_list_unauthenticated():
    with patch("src.tools.composio.calendar_tools.check_connection_status", return_value=False):
        res = composio_calendar_list_events(7275339077)
        assert res["status"] == "error"
        assert "chưa kết nối" in res["message"].lower() or "not connected" in res["message"].lower()


def test_calendar_list_events_success():
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {
        "items": [
            {"id": "ev_1", "summary": "Họp chiến lược Protein Bar", "start": "2026-09-04T10:00:00"}
        ]
    }
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.calendar_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.calendar_tools.get_composio_client", return_value=mock_client):
        res = composio_calendar_list_events(7275339077, calendar_id="primary")
        assert res["status"] == "success"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077", multi_account={"enable": True})
        assert mock_session.execute.called


def test_calendar_create_event_success():
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {
        "id": "new_ev_123",
        "htmlLink": "https://calendar.google.com/event?id=new_ev_123",
        "status": "confirmed",
    }
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.calendar_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.calendar_tools.get_composio_client", return_value=mock_client):
        res = composio_calendar_create_event(
            telegram_user_id="7275339077",
            summary="Gặp gỡ đối tác Whey Protein",
            start_datetime="2026-09-05T14:00:00+07:00",
            duration_minutes=45,
            description="Thảo luận nhập hàng đạm thực vật",
            attendees=["partner@supplier.com"],
        )
        assert res["status"] == "success"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077", multi_account={"enable": True})
        assert mock_session.execute.called


def test_calendar_find_free_slots_success():
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {
        "free_slots": [{"start": "2026-09-05T09:00:00", "end": "2026-09-05T11:00:00"}]
    }
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.calendar_tools.check_connection_status", return_value=True), \
         patch("src.tools.composio.calendar_tools.get_composio_client", return_value=mock_client):
        res = composio_calendar_find_free_slots(7275339077, date_str="2026-09-05")
        assert res["status"] == "success"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077", multi_account={"enable": True})
        assert mock_session.execute.called
