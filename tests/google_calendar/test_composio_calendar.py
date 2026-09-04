from unittest.mock import MagicMock, patch
import pytest
from tools.composio.calendar_tools import (
    composio_calendar_list_events,
    composio_calendar_create_event,
    composio_calendar_find_free_slots,
)


@pytest.fixture
def mock_composio():
    with patch("tools.composio.calendar_tools.check_connection_status", return_value=True), \
         patch("tools.composio.calendar_tools.get_composio_client") as mock_get_client, \
         patch("tools.composio.calendar_tools.resolve_account_target") as mock_resolve, \
         patch("tools.composio.calendar_tools.get_user_emails") as mock_get_emails:

        mock_get_emails.return_value = {
            "ca_acc1": "nguyenlam.baophuc@gmail.com",
            "ca_acc2": "baophuc1204vn@gmail.com",
        }
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_client.create.return_value = mock_session
        mock_get_client.return_value = mock_client

        yield {
            "client": mock_client,
            "session": mock_session,
            "resolve": mock_resolve,
            "get_emails": mock_get_emails,
        }


def test_calendar_list_events_with_target_account(mock_composio):
    mock_composio["resolve"].return_value = ("ca_acc2", "baophuc1204vn@gmail.com")
    mock_composio["session"].execute.return_value = MagicMock(data={"summary": "baophuc1204vn@gmail.com", "items": []})

    res = composio_calendar_list_events(
        telegram_user_id=7275339077,
        calendar_id="primary",
        account_email="baophuc1204vn@gmail.com",
        time_min="2026-09-01T00:00:00Z",
        time_max="2026-09-10T23:59:59Z",
        query="Project",
        limit=10,
    )

    assert res["status"] == "success"
    assert res["active_account"] == "baophuc1204vn@gmail.com"
    mock_composio["client"].create.assert_called_with(user_id="telegram_7275339077", multi_account={"enable": True})
    mock_composio["resolve"].assert_called_with(7275339077, "baophuc1204vn@gmail.com")

    # Verify session.execute received account='ca_acc2'
    call_kwargs = mock_composio["session"].execute.call_args.kwargs
    assert call_kwargs.get("account") == "ca_acc2"
    assert "timeMin" in call_kwargs["arguments"]
    assert "timeMax" in call_kwargs["arguments"]
    assert call_kwargs["arguments"]["q"] == "Project"
    assert call_kwargs["arguments"]["maxResults"] == 10


def test_calendar_list_events_default_account_when_omitted(mock_composio):
    mock_composio["resolve"].return_value = ("ca_acc1", "nguyenlam.baophuc@gmail.com")
    mock_composio["session"].execute.return_value = MagicMock(data={"summary": "nguyenlam.baophuc@gmail.com", "items": []})

    res = composio_calendar_list_events(
        telegram_user_id=7275339077,
        calendar_id="primary",
        account_email=None,
    )

    assert res["status"] == "success"
    assert res["active_account"] == "nguyenlam.baophuc@gmail.com"
    call_kwargs = mock_composio["session"].execute.call_args.kwargs
    assert call_kwargs.get("account") == "ca_acc1"


def test_calendar_create_event_with_target_account(mock_composio):
    mock_composio["resolve"].return_value = ("ca_acc2", "baophuc1204vn@gmail.com")
    mock_composio["session"].execute.return_value = MagicMock(data={"id": "evt_123", "status": "confirmed"})

    res = composio_calendar_create_event(
        telegram_user_id=7275339077,
        summary="Team Meeting",
        start_datetime="2026-09-05T10:00:00+07:00",
        duration_minutes=45,
        description="Project discussion",
        location="Ho Chi Minh City",
        attendees=["colleague@example.com"],
        calendar_id="primary",
        account_email="baophuc1204vn@gmail.com",
    )

    assert res["status"] == "success"
    assert res["active_account"] == "baophuc1204vn@gmail.com"
    mock_composio["client"].create.assert_called_with(user_id="telegram_7275339077", multi_account={"enable": True})
    call_kwargs = mock_composio["session"].execute.call_args.kwargs
    assert call_kwargs.get("account") == "ca_acc2"
    assert call_kwargs["arguments"]["summary"] == "Team Meeting"
    assert call_kwargs["arguments"]["location"] == "Ho Chi Minh City"


def test_calendar_find_free_slots_with_target_account(mock_composio):
    mock_composio["resolve"].return_value = ("ca_acc2", "baophuc1204vn@gmail.com")
    mock_composio["session"].execute.return_value = MagicMock(data={"free_slots": []})

    res = composio_calendar_find_free_slots(
        telegram_user_id=7275339077,
        date_str="2026-09-05",
        duration_minutes=30,
        calendar_id="primary",
        account_email="baophuc1204vn@gmail.com",
    )

    assert res["status"] == "success"
    assert res["active_account"] == "baophuc1204vn@gmail.com"
    mock_composio["client"].create.assert_called_with(user_id="telegram_7275339077", multi_account={"enable": True})
    call_kwargs = mock_composio["session"].execute.call_args.kwargs
    assert call_kwargs.get("account") == "ca_acc2"
