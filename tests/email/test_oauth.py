import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    MailboxType,
    MailConnection,
    OAuthLinkRequest,
)
from tools.email.store import MailStore
from tools.email.oauth import GmailOAuthManager


class FakeSecretStore:
    def __init__(self):
        self.data = {}

    def put_json(self, name: str, value: dict) -> str:
        ref = f"keyvault://{name}"
        self.data[ref] = value
        return ref

    def get_json(self, secret_ref: str) -> dict:
        return self.data[secret_ref]

    def delete(self, secret_ref: str) -> None:
        self.data.pop(secret_ref, None)


@pytest.fixture
def oauth_manager(tmp_path):
    db_path = tmp_path / "mail_state.db"
    store = MailStore(db_path)
    secrets = FakeSecretStore()
    return GmailOAuthManager(
        client_id="fake-client-id.apps.googleusercontent.com",
        client_secret="fake-client-secret",
        redirect_uri="https://hermes.example/gmail/oauth/callback",
        store=store,
        secret_store=secrets,
    )


def test_create_authorization_url_contains_readonly_only(oauth_manager):
    auth_start = oauth_manager.create_authorization_start("telegram:bot:111")
    assert "https://accounts.google.com/o/oauth2" in auth_start.url
    assert "gmail.readonly" in auth_start.url
    assert "gmail.send" not in auth_start.url
    assert "gmail.compose" not in auth_start.url
    assert auth_start.state is not None


def test_callback_token_exchange_and_atomic_storage(oauth_manager):
    auth_start = oauth_manager.create_authorization_start("telegram:bot:111")

    # Fake exchange token implementation
    fake_token = {
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "scope": [GMAIL_READONLY_SCOPE],
    }

    def fake_exchange(code: str, verifier: str):
        return fake_token, "user@example.com", "google-sub-12345"

    oauth_manager._exchange_code = fake_exchange

    conn = oauth_manager.complete_authorization(
        state=auth_start.state,
        code="auth-code-123",
        principal_id="telegram:bot:111",
    )
    assert conn.owner_principal_id == "telegram:bot:111"
    assert conn.masked_address == "u***@example.com"
    assert conn.status == "connected"

    # Replay state must fail
    with pytest.raises(PermissionError):
        oauth_manager.complete_authorization(
            state=auth_start.state,
            code="auth-code-123",
            principal_id="telegram:bot:111",
        )
