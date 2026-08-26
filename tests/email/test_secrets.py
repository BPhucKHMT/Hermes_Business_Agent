import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.email.secrets import AzureKeyVaultSecretStore


class FakeSecretClient:
    def __init__(self):
        self.secrets = {}

    def set_secret(self, name: str, value: str):
        self.secrets[name] = value
        return SimpleNamespace(name=name, value=value)

    def get_secret(self, name: str):
        if name not in self.secrets:
            raise KeyError(name)
        return SimpleNamespace(name=name, value=self.secrets[name])

    def begin_delete_secret(self, name: str):
        self.secrets.pop(name, None)
        return SimpleNamespace(result=lambda: None)


def test_key_vault_store_json_put_and_get():
    client = FakeSecretClient()
    store = AzureKeyVaultSecretStore("https://fake.vault.azure.net/", client=client)
    ref = store.put_json("gmail-conn-1", {"refresh_token": "SECRET_REFRESH_TOKEN_123"})
    assert ref == "keyvault://gmail-conn-1"
    assert "SECRET" not in ref

    retrieved = store.get_json(ref)
    assert retrieved == {"refresh_token": "SECRET_REFRESH_TOKEN_123"}


def test_secret_value_never_appears_in_exception_on_error():
    client = FakeSecretClient()
    def failing_set(*args, **kwargs):
        raise RuntimeError("failed with internal secret_token_xyz")
    client.set_secret = failing_set

    store = AzureKeyVaultSecretStore("https://fake.vault.azure.net/", client=client)
    with pytest.raises(RuntimeError) as exc_info:
        store.put_json("gmail-conn-1", {"token": "secret_token_xyz"})
    # Verify our wrapped exception suppresses secret exposure
    assert "secret_token_xyz" not in str(exc_info.value)
