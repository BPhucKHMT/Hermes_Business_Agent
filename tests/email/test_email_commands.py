from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"

for p in (SRC, PLUGIN):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from commands import handle_connect_gmail, handle_disconnect_gmail, handle_mail_status


class FakeCaller:
    def __init__(self, user_id=7275339077):
        self.user_id = user_id
        self.chat_id = str(user_id)
        self.principal_id = f"telegram:hermes-business:{user_id}"


class FakeRegistry:
    def __init__(self, caller):
        self.caller = caller

    def resolve_command(self):
        return self.caller


def test_handle_connect_gmail_delegates_to_composio():
    caller = FakeCaller(7275339077)
    registry = FakeRegistry(caller)
    client = object()

    with patch("tools.composio.commands.handle_connect_google", return_value="https://connect.composio.dev/link/test"):
        res = handle_connect_gmail(client=client, registry=registry)
        assert "connect.composio.dev" in res


def test_handle_mail_status_delegates_to_composio():
    caller = FakeCaller(7275339077)
    registry = FakeRegistry(caller)
    client = object()

    with patch("tools.composio.commands.handle_google_status", return_value="Trạng thái: ĐÃ KẾT NỐI"):
        res = handle_mail_status(client=client, registry=registry)
        assert "ĐÃ KẾT NỐI" in res


def test_handle_disconnect_gmail_delegates_to_composio():
    caller = FakeCaller(7275339077)
    registry = FakeRegistry(caller)
    client = object()

    with patch("tools.composio.commands.handle_disconnect_google", return_value="Đã ngắt kết nối thành công!"):
        res = handle_disconnect_gmail(raw_args="", client=client, registry=registry)
        assert "ngắt kết nối" in res.lower()
