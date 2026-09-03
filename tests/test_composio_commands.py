import pytest
from unittest.mock import patch

from src.tools.composio.commands import (
    handle_connect_google,
    handle_google_status,
    handle_disconnect_google,
)


def test_handle_connect_google():
    with patch("src.tools.composio.commands.initiate_google_connection", return_value="https://connect.composio.dev/link_123"):
        msg = handle_connect_google(7275339077)
        assert "https://connect.composio.dev/link_123" in msg
        assert "Google" in msg or "Gmail" in msg


def test_handle_google_status_connected():
    with patch("src.tools.composio.commands.check_connection_status", return_value=True):
        msg = handle_google_status(7275339077)
        assert "đã kết nối" in msg.lower() or "active" in msg.lower()


def test_handle_google_status_disconnected():
    with patch("src.tools.composio.commands.check_connection_status", return_value=False):
        msg = handle_google_status(7275339077)
        assert "chưa kết nối" in msg.lower() or "not connected" in msg.lower()
        assert "/connect-google" in msg


def test_handle_disconnect_google():
    with patch("src.tools.composio.commands.disconnect_user", return_value=True):
        msg = handle_disconnect_google(7275339077)
        assert "hủy kết nối" in msg.lower() or "ngắt kết nối" in msg.lower() or "thành công" in msg.lower()
