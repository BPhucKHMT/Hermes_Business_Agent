import os
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

from tools.email import env as email_env
from tools.email.service import build_service_from_env


REQUIRED = (
    "AZURE_KEY_VAULT_URL",
    "EMAIL_GOOGLE_CLIENT_ID",
    "EMAIL_OAUTH_REDIRECT_URI",
    "EMAIL_CONNECTOR_SHARED_SECRET",
)


def test_project_email_env_is_loaded_without_overriding_process_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# H009\n"
        "AZURE_KEY_VAULT_URL='vault-value' # comment\n"
        'EMAIL_GOOGLE_CLIENT_ID="client value"\n'
        "EMAIL_OAUTH_REDIRECT_URI=https://callback.invalid/path\n"
        "EMAIL_CONNECTOR_SHARED_SECRET=file-secret\n"
        "UNRELATED_PROJECT_SECRET=must-not-load\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(email_env, "_PROJECT_ENV", env_file)
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMAIL_CONNECTOR_SHARED_SECRET", "process-secret")
    monkeypatch.delenv("UNRELATED_PROJECT_SECRET", raising=False)

    loaded = email_env.load_project_email_env()

    assert loaded == frozenset(REQUIRED)
    assert all(name in os.environ for name in REQUIRED)
    assert os.environ["EMAIL_CONNECTOR_SHARED_SECRET"] == "process-secret"
    assert "UNRELATED_PROJECT_SECRET" not in os.environ


def test_malformed_project_env_fails_atomically(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AZURE_KEY_VAULT_URL=vault-value\n"
        'EMAIL_GOOGLE_CLIENT_ID="unterminated\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(email_env, "_PROJECT_ENV", env_file)
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(email_env.EmailEnvError, match="malformed_project_email_env"):
        email_env.load_project_email_env()

    assert all(name not in os.environ for name in REQUIRED)


def test_loader_never_searches_parent_env(tmp_path, monkeypatch):
    deployed_src = tmp_path / "src"
    deployed_src.mkdir()
    project_env = deployed_src / ".env"
    parent_env = tmp_path / ".env"
    parent_env.write_text("EMAIL_GOOGLE_CLIENT_ID=parent-only\n", encoding="utf-8")
    monkeypatch.setattr(email_env, "_PROJECT_ENV", project_env)
    monkeypatch.delenv("EMAIL_GOOGLE_CLIENT_ID", raising=False)

    assert email_env.load_project_email_env() == frozenset()
    assert "EMAIL_GOOGLE_CLIENT_ID" not in os.environ


def test_service_factory_sees_project_env_names(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    state_path = tmp_path / "mail.db"
    env_file.write_text(
        "AZURE_KEY_VAULT_URL=https://vault.invalid\n"
        "EMAIL_GOOGLE_CLIENT_ID=client-id\n"
        "EMAIL_OAUTH_REDIRECT_URI=https://callback.invalid\n"
        "EMAIL_CONNECTOR_SHARED_SECRET=shared-secret\n"
        f"EMAIL_STATE_DB_PATH={state_path.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(email_env, "_PROJECT_ENV", env_file)
    for name in (*REQUIRED, "EMAIL_STATE_DB_PATH"):
        monkeypatch.delenv(name, raising=False)

    import tools.email.secrets as secret_module

    class FakeSecretStore:
        def __init__(self, vault_url):
            self.vault_url = vault_url

        def get_json(self, secret_ref):
            return {"client_secret": "configured"}

        def put_json(self, name, value):
            return f"keyvault://{name}"

        def delete(self, secret_ref):
            return None

    monkeypatch.setattr(
        secret_module,
        "AzureKeyVaultSecretStore",
        FakeSecretStore,
    )

    service = build_service_from_env()

    assert service.shared_secret
    assert all(name in os.environ for name in REQUIRED)
