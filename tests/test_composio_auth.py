import pytest
from unittest.mock import MagicMock, patch

from src.tools.composio.client import format_user_id, get_composio_client
from src.tools.composio.auth import (
    initiate_google_connection,
    check_connection_status,
    disconnect_user,
)


def test_format_user_id():
    assert format_user_id(123456789) == "telegram_123456789"
    assert format_user_id("7275339077") == "telegram_7275339077"
    with pytest.raises(ValueError):
        format_user_id("")
    with pytest.raises(ValueError):
        format_user_id(None)


def test_client_missing_api_key(monkeypatch):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    with patch("os.path.isfile", return_value=False):
        with pytest.raises(RuntimeError, match="COMPOSIO_API_KEY"):
            get_composio_client(force_refresh=True)


def test_client_with_api_key(monkeypatch):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test_key_123")
    with patch("src.tools.composio.client.Composio") as mock_cls:
        client = get_composio_client(force_refresh=True)
        assert client is not None
        mock_cls.assert_called_once_with(api_key="test_key_123")


def test_initiate_google_connection(monkeypatch):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test_key_123")
    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_req = MagicMock()
    mock_req.redirect_url = "https://connect.composio.dev/auth/test_auth_link"
    mock_session.authorize.return_value = mock_req
    mock_client.create.return_value = mock_session

    with patch("src.tools.composio.auth.get_composio_client", return_value=mock_client):
        url = initiate_google_connection(7275339077, toolkit="gmail")
        assert url == "https://connect.composio.dev/auth/test_auth_link"
        mock_client.create.assert_called_once_with(user_id="telegram_7275339077")
        mock_session.authorize.assert_called_once_with("gmail")


def test_check_connection_status(monkeypatch):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test_key_123")
    mock_client = MagicMock()
    mock_item = MagicMock()
    mock_item.status = "ACTIVE"
    mock_toolkit = MagicMock()
    mock_toolkit.slug = "gmail"
    mock_item.toolkit = mock_toolkit

    mock_resp = MagicMock()
    mock_resp.items = [mock_item]
    mock_client.connected_accounts.list.return_value = mock_resp

    with patch("src.tools.composio.auth.get_composio_client", return_value=mock_client):
        status = check_connection_status(7275339077, app="gmail")
        assert status is True
        mock_client.connected_accounts.list.assert_called_once_with(
            user_ids=["telegram_7275339077"]
        )
