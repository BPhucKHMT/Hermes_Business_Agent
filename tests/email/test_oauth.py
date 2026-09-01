import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tools

if str(SRC / "tools") not in tools.__path__:
    tools.__path__.insert(0, str(SRC / "tools"))

from tools.email.contracts import GMAIL_READONLY_SCOPE
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


def test_public_callback_resolves_principal_from_oauth_state(oauth_manager):
    auth_start = oauth_manager.create_authorization_start("telegram:bot:111")
    oauth_manager._exchange_code = lambda code, verifier: (
        {
            "token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "scopes": [GMAIL_READONLY_SCOPE],
        },
        "user@example.com",
        "google-sub-12345",
    )

    connection = oauth_manager.complete_callback(
        state=auth_start.state,
        code="auth-code-123",
    )

    assert connection.owner_principal_id == "telegram:bot:111"
    assert oauth_manager.store.list_connections("telegram:bot:111") == (connection,)


def test_exchange_code_sets_relax_token_scope(oauth_manager, monkeypatch):
    from types import SimpleNamespace

    class FakeCredentials:
        token = "test-token"
        refresh_token = "test-refresh"
        token_uri = "https://oauth2.googleapis.com/token"
        client_id = "test-client"
        client_secret = "test-secret"
        scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

    class FakeFlow:
        credentials = FakeCredentials()

        @classmethod
        def from_client_config(cls, *args, **kwargs):
            return cls()

        def fetch_token(self, code):
            pass

    class FakeUsers:
        def getProfile(self, userId):
            return self

        def execute(self):
            return {"emailAddress": "testuser@gmail.com"}

    class FakeService:
        def users(self):
            return FakeUsers()

    monkeypatch.setattr("google_auth_oauthlib.flow.Flow", FakeFlow)
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *args, **kwargs: FakeService())

    token_data, email, sub_id = oauth_manager._exchange_code("code123", "verifier123")
    assert email == "testuser@gmail.com"
    assert token_data["token"] == "test-token"
    import os
    assert os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE") == "1"
