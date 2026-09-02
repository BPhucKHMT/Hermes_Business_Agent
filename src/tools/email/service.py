from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

try:
    from google.auth.exceptions import RefreshError
except ImportError:
    class RefreshError(Exception):
        pass

from tools.email.contracts import (
    AuditEvent,
    ConnectionStatus,
    Destination,
    MailConnection,
)
from tools.email.env import load_project_email_env
from tools.email.gmail import GmailReader
from tools.email.policy import MailPolicy, PolicyCaller
from tools.email.secrets import SecretStore
from tools.email.store import MailStore

logger = logging.getLogger(__name__)


@dataclass
class ServiceResponse:
    status: int
    body: bytes
    content_type: str = "application/json"


def make_signed_headers(
    method: str, path: str, body: bytes, secret: str
) -> Dict[str, str]:
    now = str(int(time.time()))
    nonce = hashlib.sha256(f"{now}:{time.monotonic()}".encode("utf-8")).hexdigest()[:16]
    body_sha = hashlib.sha256(body).hexdigest()

    sig_payload = f"{method.upper()}\n{path}\n{now}\n{nonce}\n{body_sha}"
    signature = hmac.new(
        secret.encode("utf-8"), sig_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return {
        "X-Email-Timestamp": now,
        "X-Email-Nonce": nonce,
        "X-Email-Signature": signature,
    }


class EmailConnectorService:
    def __init__(
        self,
        store: MailStore,
        secret_store: SecretStore,
        policy: MailPolicy,
        gmail_reader: Optional[GmailReader] = None,
        oauth_manager: Optional[Any] = None,
        shared_secret: str = "dev-shared-secret",
    ) -> None:
        self.store = store
        self.secret_store = secret_store
        self.policy = policy
        self.gmail_reader = gmail_reader or GmailReader()
        self.oauth_manager = oauth_manager
        self.shared_secret = shared_secret

    def _verify_hmac(
        self, method: str, path: str, body: bytes, headers: Dict[str, str]
    ) -> bool:
        ts = headers.get("X-Email-Timestamp") or headers.get("x-email-timestamp")
        nonce = headers.get("X-Email-Nonce") or headers.get("x-email-nonce")
        signature = headers.get("X-Email-Signature") or headers.get("x-email-signature")

        if not ts or not nonce or not signature:
            return False

        try:
            ts_int = int(ts)
            if abs(time.time() - ts_int) > 60:
                return False
        except ValueError:
            return False

        body_sha = hashlib.sha256(body).hexdigest()
        sig_payload = f"{method.upper()}\n{path}\n{ts}\n{nonce}\n{body_sha}"
        expected = hmac.new(
            self.shared_secret.encode("utf-8"),
            sig_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_internal_request(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Dict[str, str],
    ) -> ServiceResponse:
        if not self._verify_hmac(method, path, body, headers):
            return ServiceResponse(
                status=401,
                body=json.dumps(
                    {"ok": False, "error": {"code": "unauthorized"}}
                ).encode("utf-8"),
            )

        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return ServiceResponse(
                status=400,
                body=json.dumps(
                    {"ok": False, "error": {"code": "malformed_json"}}
                ).encode("utf-8"),
            )

        try:
            if path == "/v1/oauth/start" and method == "POST":
                return self._handle_oauth_start(data)
            if path == "/v1/search" and method == "POST":
                return self._handle_search(data)
            if path == "/v1/thread" and method == "POST":
                return self._handle_thread(data)
            if path == "/v1/attachment" and method == "POST":
                return self._handle_attachment(data)
            if path == "/v1/connections" and method == "GET":
                return self._handle_list_connections(data)
            if path == "/v1/disconnect" and method == "POST":
                return self._handle_disconnect(data)
            if path == "/v1/grants/propose" and method == "POST":
                return self._handle_grant_propose(data)
            if path == "/v1/grants/decide" and method == "POST":
                return self._handle_grant_decide(data)
        except (FileNotFoundError, PermissionError, ValueError) as error:
            return self._error_response(403, str(error).split(":", 1)[0])
        except RefreshError:
            return ServiceResponse(
                status=401,
                body=json.dumps(
                    {"ok": False, "error": {"code": "reconnect_required"}}
                ).encode("utf-8"),
            )
        except Exception:
            logger.error("Email connector request failed for %s", path)
            return self._error_response(503, "connector_unavailable")

        return self._error_response(404, "not_found")

    @staticmethod
    def _error_response(status: int, code: str) -> ServiceResponse:
        return ServiceResponse(
            status=status,
            body=json.dumps({"ok": False, "error": {"code": code}}).encode("utf-8"),
        )

    @staticmethod
    def _caller(data: Dict[str, Any]) -> PolicyCaller:
        return PolicyCaller(
            principal_id=data.get("principal_id", ""),
            platform=data.get("platform", "telegram"),
            user_id=data.get("user_id", ""),
            chat_id=data.get("chat_id", ""),
            thread_id=data.get("thread_id"),
            chat_type=data.get("chat_type", "dm"),
            profile=data.get("profile", "default"),
            session_key=data.get("session_key", ""),
        )

    def _audit(
        self,
        event_type: str,
        caller: PolicyCaller,
        outcome: str,
        connection_id: Optional[str] = None,
        destination: Optional[Destination] = None,
        query: Optional[str] = None,
    ) -> None:
        destination_hash = None
        if destination is not None:
            destination_hash = hashlib.sha256(
                (
                    f"{destination.platform}:{destination.chat_id}:"
                    f"{destination.thread_id or ''}"
                ).encode("utf-8")
            ).hexdigest()
        query_hash = (
            hashlib.sha256(query.encode("utf-8")).hexdigest()
            if query is not None
            else None
        )
        self.store.append_audit(
            AuditEvent(
                event_id=f"audit-{secrets.token_hex(16)}",
                event_type=event_type,
                principal_id=caller.principal_id,
                connection_id=connection_id,
                destination_hash=destination_hash,
                query_hash=query_hash,
                occurred_at=datetime.now(timezone.utc).isoformat(),
                outcome=outcome,
            )
        )

    def handle_oauth_callback(self, state: str, code: str) -> ServiceResponse:
        if self.oauth_manager is None:
            return ServiceResponse(
                status=503,
                body=b"Gmail connector unavailable.",
                content_type="text/plain; charset=utf-8",
            )
        if not state or not code:
            return ServiceResponse(
                status=400,
                body=b"Invalid OAuth callback.",
                content_type="text/plain; charset=utf-8",
            )
        try:
            connection = self.oauth_manager.complete_callback(state, code)
            caller = PolicyCaller(
                principal_id=connection.owner_principal_id,
                platform="telegram",
                user_id="",
                chat_id="",
                chat_type="dm",
            )
            self._audit(
                "connect",
                caller,
                "connected",
                connection_id=connection.connection_id,
            )
        except Exception as exc:
            logger.exception("Gmail OAuth callback failed")
            err_str = str(exc)
            if (
                "accessNotConfigured" in err_str
                or "Gmail API has not been used" in err_str
            ):
                body_msg = (
                    b"Gmail API is disabled on your Google Cloud project. "
                    b"Please enable Gmail API in Google Cloud Console and try again."
                )
            else:
                body_msg = f"Gmail connection failed: {exc}".encode("utf-8")
            return ServiceResponse(
                status=400,
                body=body_msg,
                content_type="text/plain; charset=utf-8",
            )
        return ServiceResponse(
            status=200,
            body=b"Gmail connected. Google Workspace active (Gmail, Google Calendar, YouTube). Return to Hermes.",
            content_type="text/plain; charset=utf-8",
        )

    def _handle_grant_propose(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        destination_data = data.get("destination", {})
        if caller.chat_type != "dm":
            return self._error_response(403, "dm_required")
        destination = Destination(
            platform=destination_data.get("platform", ""),
            chat_id=destination_data.get("chat_id", ""),
            thread_id=destination_data.get("thread_id"),
        )
        if destination.platform != "telegram" or not destination.chat_id:
            return self._error_response(400, "invalid_destination")
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        request = self.policy.propose_shared_grant(
            caller,
            data.get("connection_id", ""),
            destination,
            expires_at,
        )
        self._audit(
            "grant",
            caller,
            "pending",
            connection_id=request.connection_id,
            destination=destination,
        )
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "request_id": request.request_id,
                        "status": "pending",
                        "expires_at": request.expires_at,
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_grant_decide(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        decision = data.get("decision", "")
        if caller.chat_type != "dm":
            return self._error_response(403, "dm_required")
        if decision not in ("approve", "deny"):
            return self._error_response(400, "invalid_grant_decision")
        request = self.policy.decide_shared_grant(
            caller,
            data.get("request_id", ""),
            approve=decision == "approve",
        )
        outcome = "approved" if decision == "approve" else "denied"
        self._audit(
            "grant",
            caller,
            outcome,
            connection_id=request.connection_id,
            destination=request.destination,
        )
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "request_id": request.request_id,
                        "status": outcome,
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_oauth_start(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        if caller.chat_type != "dm" or not caller.principal_id:
            return self._error_response(403, "dm_required")
        if self.oauth_manager is None:
            return self._error_response(503, "oauth_not_configured")

        start = self.oauth_manager.create_authorization_start(caller.principal_id)
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "authorization_url": start.url,
                        "request_id": start.request_id,
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_disconnect(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        connection_id = data.get("connection_id", "")
        if caller.chat_type != "dm" or not caller.principal_id:
            return self._error_response(403, "dm_required")
        if not connection_id:
            return self._error_response(400, "connection_id_required")

        connection = self.store.revoke_connection(
            caller.principal_id,
            connection_id,
        )
        self.secret_store.delete(connection.secret_ref)
        self._audit(
            "revoke",
            caller,
            "revoked",
            connection_id=connection.connection_id,
        )
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "connection_id": connection.connection_id,
                        "status": "revoked",
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_token_refresh_failed(
        self,
        caller: PolicyCaller,
        connection: MailConnection,
        destination: Optional[Destination] = None,
        query: Optional[str] = None,
    ) -> ServiceResponse:
        self.store.update_connection_status(
            connection.connection_id,
            ConnectionStatus.RECONNECT_REQUIRED,
        )
        self._audit(
            "token_refresh_failed",
            caller,
            "failed",
            connection_id=connection.connection_id,
            destination=destination,
            query=query,
        )
        return ServiceResponse(
            status=401,
            body=json.dumps(
                {"ok": False, "error": {"code": "reconnect_required"}}
            ).encode("utf-8"),
        )

    def _handle_search(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        query = data.get("query", "")
        limit = data.get("limit", 10)
        destination = Destination(
            caller.platform,
            caller.chat_id,
            caller.thread_id,
        )
        connections = self.policy.readable_connections(caller)
        if not connections:
            self._audit(
                "search",
                caller,
                "empty",
                destination=destination,
                query=query,
            )
            return ServiceResponse(
                status=200,
                body=json.dumps({"ok": True, "result": {"hits": []}}).encode("utf-8"),
            )

        connection = connections[0]
        delivery = self.policy.decide_delivery(caller, connection)
        if delivery.mode == "redirect_to_dm":
            self._audit(
                "search",
                caller,
                "redirect_to_dm",
                connection_id=connection.connection_id,
                destination=destination,
                query=query,
            )
            return ServiceResponse(
                status=200,
                body=json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "delivery": "redirect_to_dm",
                            "public_text": delivery.public_text,
                        },
                    }
                ).encode("utf-8"),
            )

        token_data = self.secret_store.get_json(connection.secret_ref)
        try:
            hits = self.gmail_reader.search_threads(token_data, query, limit=limit)
        except (RefreshError, Exception) as exc:
            if isinstance(exc, RefreshError) or "invalid_grant" in str(exc).lower():
                return self._handle_token_refresh_failed(
                    caller, connection, destination=destination, query=query
                )
            raise

        self._audit(
            "search",
            caller,
            "ok",
            connection_id=connection.connection_id,
            destination=destination,
            query=query,
        )
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "delivery": delivery.mode,
                        "hits": [asdict(hit) for hit in hits],
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_thread(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        thread_id = data.get("thread_id", "")
        text_bytes_max = data.get("text_bytes_max", 65536)
        destination = Destination(
            caller.platform,
            caller.chat_id,
            caller.thread_id,
        )
        connections = self.policy.readable_connections(caller)
        if not connections:
            self._audit(
                "thread",
                caller,
                "not_authorized",
                destination=destination,
            )
            return self._error_response(404, "not_authorized")

        connection = connections[0]
        delivery = self.policy.decide_delivery(caller, connection)
        if delivery.mode == "redirect_to_dm":
            self._audit(
                "thread",
                caller,
                "redirect_to_dm",
                connection_id=connection.connection_id,
                destination=destination,
            )
            return ServiceResponse(
                status=200,
                body=json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "delivery": "redirect_to_dm",
                            "public_text": delivery.public_text,
                        },
                    }
                ).encode("utf-8"),
            )

        token_data = self.secret_store.get_json(connection.secret_ref)
        try:
            result = self.gmail_reader.get_thread(
                token_data,
                thread_id,
                text_bytes_max=text_bytes_max,
            )
        except (RefreshError, Exception) as exc:
            if isinstance(exc, RefreshError) or "invalid_grant" in str(exc).lower():
                return self._handle_token_refresh_failed(
                    caller, connection, destination=destination
                )
            raise

        self._audit(
            "thread",
            caller,
            "ok",
            connection_id=connection.connection_id,
            destination=destination,
        )
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "delivery": delivery.mode,
                        "thread": asdict(result),
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_attachment(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = self._caller(data.get("caller", {}))
        message_id = data.get("message_id", "")
        attachment_id = data.get("attachment_id", "")
        destination = Destination(
            caller.platform,
            caller.chat_id,
            caller.thread_id,
        )

        if not message_id or not attachment_id:
            return self._error_response(400, "missing_attachment_params")

        connection_id = data.get("connection_id")
        if connection_id:
            try:
                connection = self.policy.authorize_source(caller, connection_id)
            except Exception:
                self._audit(
                    "attachment",
                    caller,
                    "not_authorized",
                    destination=destination,
                )
                return self._error_response(403, "not_authorized")
        else:
            connections = self.policy.readable_connections(caller)
            if not connections:
                self._audit(
                    "attachment",
                    caller,
                    "not_authorized",
                    destination=destination,
                )
                return self._error_response(404, "not_authorized")
            connection = connections[0]

        delivery = self.policy.decide_delivery(caller, connection)
        if delivery.mode == "redirect_to_dm":
            self._audit(
                "attachment",
                caller,
                "redirect_to_dm",
                connection_id=connection.connection_id,
                destination=destination,
            )
            return ServiceResponse(
                status=200,
                body=json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "delivery": "redirect_to_dm",
                            "public_text": delivery.public_text,
                        },
                    }
                ).encode("utf-8"),
            )

        token_data = self.secret_store.get_json(connection.secret_ref)
        try:
            raw_bytes = self.gmail_reader.get_attachment(
                token_data,
                message_id=message_id,
                attachment_id=attachment_id,
            )
        except (RefreshError, Exception) as exc:
            if isinstance(exc, RefreshError) or "invalid_grant" in str(exc).lower():
                return self._handle_token_refresh_failed(
                    caller, connection, destination=destination
                )
            raise

        self._audit(
            "attachment",
            caller,
            "ok",
            connection_id=connection.connection_id,
            destination=destination,
        )
        b64_data = base64.b64encode(raw_bytes).decode("utf-8")
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "delivery": delivery.mode,
                        "message_id": message_id,
                        "attachment_id": attachment_id,
                        "data": b64_data,
                        "size": len(raw_bytes),
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_list_connections(self, data: Dict[str, Any]) -> ServiceResponse:
        caller_data = data.get("caller") or {
            "principal_id": data.get("principal_id", ""),
            "chat_type": "dm",
        }
        caller = self._caller(caller_data)
        connections = self.policy.readable_connections(caller)
        self._audit("status", caller, "ok")
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "connections": [
                            {
                                "connection_id": connection.connection_id,
                                "masked_address": connection.masked_address,
                                "mailbox_type": str(connection.mailbox_type),
                                "status": str(connection.status),
                            }
                            for connection in connections
                        ]
                    },
                }
            ).encode("utf-8"),
        )


def create_http_server(
    service: EmailConnectorService,
    host: str = "127.0.0.1",
    port: int = 8766,
) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("email_connector_must_bind_loopback")

    class Handler(BaseHTTPRequestHandler):
        def _write(self, response: ServiceResponse) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def _internal(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_048_576:
                self._write(
                    EmailConnectorService._error_response(413, "request_too_large")
                )
                return
            body = self.rfile.read(length) if length else b""
            headers = {key: value for key, value in self.headers.items()}
            self._write(
                service.handle_internal_request(
                    method,
                    urllib.parse.urlsplit(self.path).path,
                    body,
                    headers,
                )
            )

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/health":
                self._write(
                    ServiceResponse(
                        status=200,
                        body=b'{"ok":true}',
                    )
                )
                return
            if parsed.path in (
                "/gmail/oauth/callback",
                "/calendar/oauth/callback",
                "/google/oauth/callback",
            ):
                query = urllib.parse.parse_qs(parsed.query)
                self._write(
                    service.handle_oauth_callback(
                        query.get("state", [""])[0],
                        query.get("code", [""])[0],
                    )
                )
                return
            self._internal("GET")

        def do_POST(self) -> None:
            self._internal("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def build_service_from_env() -> EmailConnectorService:
    import os
    from pathlib import Path

    from tools.email.oauth import GmailOAuthManager
    from tools.email.secrets import AzureKeyVaultSecretStore, LocalEncryptedSecretStore

    load_project_email_env()

    client_id = os.environ.get("EMAIL_GOOGLE_CLIENT_ID", "").strip()
    redirect_uri = os.environ.get("EMAIL_OAUTH_REDIRECT_URI", "").strip()
    shared_secret = os.environ.get("EMAIL_CONNECTOR_SHARED_SECRET", "").strip()

    if not client_id or not redirect_uri or not shared_secret:
        raise RuntimeError("connector_unavailable")

    # Resolve SecretStore: try Key Vault when configured, then fall back locally.
    vault_url = os.environ.get("AZURE_KEY_VAULT_URL", "").strip()
    prefer_local = os.environ.get("EMAIL_SECRET_STORE", "").strip().lower() == "local"
    secret_store = None

    if vault_url and not prefer_local:
        try:
            kv_store = AzureKeyVaultSecretStore(vault_url)
            # Active probe / verify if client can authenticate
            if hasattr(kv_store, "_client") and hasattr(kv_store._client, "get_secret"):
                kv_store._client.get_secret("probe-auth-check")
            secret_store = kv_store
        except Exception:
            logger.info(
                "Azure Key Vault unauthenticated or unavailable. Using LocalEncryptedSecretStore."
            )
            secret_store = LocalEncryptedSecretStore()
    else:
        secret_store = LocalEncryptedSecretStore()

    # 2. Resolve Google Client Secret: prefer direct environment variable, fallback to Key Vault
    client_secret = os.environ.get("EMAIL_GOOGLE_CLIENT_SECRET", "").strip()
    if not client_secret and secret_store is not None:
        client_secret_ref = os.environ.get(
            "EMAIL_GOOGLE_CLIENT_SECRET_REF",
            "keyvault://email-google-client-secret",
        )
        try:
            client_secret = secret_store.get_json(client_secret_ref).get(
                "client_secret", ""
            )
        except Exception as exc:
            logger.debug("Failed to load client_secret from secret store ref: %s", exc)
    if not client_secret:
        raise RuntimeError("oauth_client_secret_not_configured")

    state_path = os.environ.get("EMAIL_STATE_DB_PATH", "").strip()
    if not state_path:
        if os.environ.get("HERMES_HOME"):
            hermes_home = Path(os.environ["HERMES_HOME"])
        elif sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
            base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
            hermes_home = base / "hermes"
        else:
            hermes_home = Path.home() / ".hermes"
        state_path = str(hermes_home / "email" / "mail_state.db")
    store = MailStore(state_path)
    operator_ids = tuple(
        user_id.strip()
        for user_id in os.environ.get("EMAIL_OPERATOR_USER_IDS", "").split(",")
        if user_id.strip()
    )
    policy = MailPolicy(store, operator_allowlist=operator_ids)
    oauth = GmailOAuthManager(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        store=store,
        secret_store=secret_store,
    )
    return EmailConnectorService(
        store=store,
        secret_store=secret_store,
        policy=policy,
        gmail_reader=GmailReader(),
        oauth_manager=oauth,
        shared_secret=shared_secret,
    )
