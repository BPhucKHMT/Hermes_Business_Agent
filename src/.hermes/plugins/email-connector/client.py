from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from tools.email.gmail import GmailReader
from tools.email.oauth import GmailOAuthManager
from tools.email.policy import MailPolicy
from tools.email.secrets import AzureKeyVaultSecretStore
from tools.email.service import EmailConnectorService, make_signed_headers
from tools.email.store import MailStore


def _caller_payload(caller: Any) -> dict[str, Any]:
    return {
        "principal_id": caller.principal_id,
        "platform": caller.platform,
        "user_id": caller.user_id,
        "chat_id": caller.chat_id,
        "thread_id": caller.thread_id,
        "chat_type": caller.chat_type,
        "profile": caller.profile,
        "session_key": caller.session_key,
    }


class EmailConnectorClient:
    def __init__(self, service: EmailConnectorService, shared_secret: str) -> None:
        self._service = service
        self._shared_secret = shared_secret

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        response = self._service.handle_internal_request(
            method,
            path,
            body,
            make_signed_headers(method, path, body, self._shared_secret),
        )
        try:
            data = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": False, "error": {"code": "invalid_connector_response"}}
        if response.status >= 400 and data.get("ok") is not False:
            return {"ok": False, "error": {"code": "connector_request_failed"}}
        return data

    def search(self, caller: Any, query: str, limit: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/search",
            {"caller": _caller_payload(caller), "query": query, "limit": limit},
        )

    def get_thread(self, caller: Any, thread_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/thread",
            {"caller": _caller_payload(caller), "thread_id": thread_id},
        )

    def connections(self, caller: Any) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/connections",
            {"principal_id": caller.principal_id},
        )

    def start_oauth(self, caller: Any) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/oauth/start",
            {"caller": _caller_payload(caller)},
        )

    def disconnect(self, caller: Any, connection_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/disconnect",
            {"caller": _caller_payload(caller), "connection_id": connection_id},
        )

class UnavailableConnectorClient:
    def __init__(self, code: str = "connector_unavailable") -> None:
        self._response = {"ok": False, "error": {"code": code}}

    def search(self, caller: Any, query: str, limit: int) -> dict[str, Any]:
        return self._response

    def get_thread(self, caller: Any, thread_id: str) -> dict[str, Any]:
        return self._response

    def connections(self, caller: Any) -> dict[str, Any]:
        return self._response

    def start_oauth(self, caller: Any) -> dict[str, Any]:
        return self._response

    def disconnect(self, caller: Any, connection_id: str) -> dict[str, Any]:
        return self._response


_default_client: EmailConnectorClient | UnavailableConnectorClient | None = None
_default_lock = Lock()


def get_default_client() -> EmailConnectorClient | UnavailableConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = _build_default_client()
        return _default_client


def _build_default_client() -> EmailConnectorClient | UnavailableConnectorClient:
    required = {
        "AZURE_KEY_VAULT_URL": os.environ.get("AZURE_KEY_VAULT_URL", "").strip(),
        "EMAIL_GOOGLE_CLIENT_ID": os.environ.get("EMAIL_GOOGLE_CLIENT_ID", "").strip(),
        "EMAIL_OAUTH_REDIRECT_URI": os.environ.get("EMAIL_OAUTH_REDIRECT_URI", "").strip(),
        "EMAIL_CONNECTOR_SHARED_SECRET": os.environ.get("EMAIL_CONNECTOR_SHARED_SECRET", "").strip(),
    }
    if not all(required.values()):
        return UnavailableConnectorClient()

    try:
        secret_store = AzureKeyVaultSecretStore(required["AZURE_KEY_VAULT_URL"])
        secret_ref = os.environ.get(
            "EMAIL_GOOGLE_CLIENT_SECRET_REF",
            "keyvault://email-google-client-secret",
        )
        client_secret = secret_store.get_json(secret_ref).get("client_secret", "")
        if not client_secret:
            return UnavailableConnectorClient("oauth_client_secret_not_configured")

        state_path = os.environ.get("EMAIL_STATE_DB_PATH", "").strip()
        if not state_path:
            hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
            state_path = str(hermes_home / "email" / "mail_state.db")
        store = MailStore(state_path)
        policy = MailPolicy(store)
        oauth = GmailOAuthManager(
            client_id=required["EMAIL_GOOGLE_CLIENT_ID"],
            client_secret=client_secret,
            redirect_uri=required["EMAIL_OAUTH_REDIRECT_URI"],
            store=store,
            secret_store=secret_store,
        )
        service = EmailConnectorService(
            store=store,
            secret_store=secret_store,
            policy=policy,
            gmail_reader=GmailReader(),
            oauth_manager=oauth,
            shared_secret=required["EMAIL_CONNECTOR_SHARED_SECRET"],
        )
        return EmailConnectorClient(service, required["EMAIL_CONNECTOR_SHARED_SECRET"])
    except Exception:
        return UnavailableConnectorClient("connector_initialization_failed")
