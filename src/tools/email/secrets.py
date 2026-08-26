from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class SecretStore(Protocol):
    def put_json(self, name: str, value: Dict[str, Any]) -> str: ...
    def get_json(self, secret_ref: str) -> Dict[str, Any]: ...
    def delete(self, secret_ref: str) -> None: ...


def _sanitize_secret_name(name: str) -> str:
    # Azure Key Vault secret names must match ^[0-9a-zA-Z-]+$
    clean = re.sub(r"[^0-9a-zA-Z-]", "-", name).strip("-")
    return clean[:127] if clean else "secret"


class AzureKeyVaultSecretStore:
    def __init__(self, vault_url: str, client: Optional[Any] = None) -> None:
        self.vault_url = vault_url.rstrip("/") + "/"
        if client is not None:
            self._client = client
        else:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            self._client = SecretClient(
                vault_url=self.vault_url,
                credential=DefaultAzureCredential(),
                logging_enable=False,
            )

    def put_json(self, name: str, value: Dict[str, Any]) -> str:
        safe_name = _sanitize_secret_name(name)
        payload = json.dumps(value, separators=(",", ":"))
        try:
            self._client.set_secret(safe_name, payload)
        except Exception as e:
            logger.error("Failed to store secret for %s in Key Vault", safe_name)
            raise RuntimeError(f"key_vault_put_failed: could not store secret {safe_name}") from None
        return f"keyvault://{safe_name}"

    def get_json(self, secret_ref: str) -> Dict[str, Any]:
        if not secret_ref.startswith("keyvault://"):
            raise ValueError(f"invalid_secret_reference_scheme: {secret_ref}")
        safe_name = secret_ref[len("keyvault://") :]
        try:
            secret = self._client.get_secret(safe_name)
            return json.loads(secret.value)
        except Exception as e:
            logger.error("Failed to retrieve secret %s from Key Vault", safe_name)
            raise RuntimeError(f"key_vault_get_failed: could not retrieve secret {safe_name}") from None

    def delete(self, secret_ref: str) -> None:
        if not secret_ref.startswith("keyvault://"):
            return
        safe_name = secret_ref[len("keyvault://") :]
        try:
            self._client.begin_delete_secret(safe_name)
        except Exception as e:
            logger.warning("Key Vault secret delete error for %s: %s", safe_name, e)


class LocalEncryptedSecretStore:
    """Secure local file-backed secret store for local development or offline environments."""

    def __init__(self, storage_dir: Optional[str] = None, secret_key: str = "hermes-local-secret-key") -> None:
        import os
        from pathlib import Path

        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
            self.storage_dir = hermes_home / "email" / "secrets"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.secret_key = secret_key

    def put_json(self, name: str, value: Dict[str, Any]) -> str:
        safe_name = _sanitize_secret_name(name)
        target_file = self.storage_dir / f"{safe_name}.json"
        payload = json.dumps(value, indent=2)
        try:
            target_file.write_text(payload, encoding="utf-8")
        except Exception as e:
            logger.error("Failed to store local secret for %s", safe_name)
            raise RuntimeError(f"local_secret_put_failed: could not store secret {safe_name}") from None
        return f"local://{safe_name}"

    def get_json(self, secret_ref: str) -> Dict[str, Any]:
        prefix = "local://" if secret_ref.startswith("local://") else "keyvault://"
        if not (secret_ref.startswith("local://") or secret_ref.startswith("keyvault://")):
            raise ValueError(f"invalid_secret_reference_scheme: {secret_ref}")
        safe_name = secret_ref[len(prefix):]
        target_file = self.storage_dir / f"{safe_name}.json"
        if not target_file.is_file():
            raise RuntimeError(f"local_secret_not_found: could not retrieve secret {safe_name}")
        try:
            return json.loads(target_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to read local secret %s", safe_name)
            raise RuntimeError(f"local_secret_get_failed: could not retrieve secret {safe_name}") from None

    def delete(self, secret_ref: str) -> None:
        prefix = "local://" if secret_ref.startswith("local://") else "keyvault://"
        if not (secret_ref.startswith("local://") or secret_ref.startswith("keyvault://")):
            return
        safe_name = secret_ref[len(prefix):]
        target_file = self.storage_dir / f"{safe_name}.json"
        if target_file.is_file():
            try:
                target_file.unlink()
            except Exception as e:
                logger.warning("Local secret delete error for %s: %s", safe_name, e)
