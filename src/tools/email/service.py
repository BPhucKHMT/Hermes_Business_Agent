from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

from tools.email.contracts import (
    Destination,
    MailConnection,
    MailboxType,
)
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


def make_signed_headers(method: str, path: str, body: bytes, secret: str) -> Dict[str, str]:
    now = str(int(time.time()))
    nonce = hashlib.sha256(f"{now}:{time.monotonic()}".encode("utf-8")).hexdigest()[:16]
    body_sha = hashlib.sha256(body).hexdigest()

    sig_payload = f"{method.upper()}\n{path}\n{now}\n{nonce}\n{body_sha}"
    signature = hmac.new(secret.encode("utf-8"), sig_payload.encode("utf-8"), hashlib.sha256).hexdigest()

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

    def _verify_hmac(self, method: str, path: str, body: bytes, headers: Dict[str, str]) -> bool:
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
                body=json.dumps({"ok": False, "error": {"code": "unauthorized"}}).encode("utf-8"),
            )

        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return ServiceResponse(
                status=400,
                body=json.dumps({"ok": False, "error": {"code": "malformed_json"}}).encode("utf-8"),
            )

        try:
            if path == "/v1/oauth/start" and method == "POST":
                return self._handle_oauth_start(data)
            if path == "/v1/search" and method == "POST":
                return self._handle_search(data)
            if path == "/v1/thread" and method == "POST":
                return self._handle_thread(data)
            if path == "/v1/connections" and method == "GET":
                return self._handle_list_connections(data)
            if path == "/v1/disconnect" and method == "POST":
                return self._handle_disconnect(data)
        except (FileNotFoundError, PermissionError, ValueError) as error:
            return self._error_response(403, str(error).split(":", 1)[0])
        except Exception:
            logger.exception("Email connector request failed for %s", path)
            return self._error_response(503, "connector_unavailable")

        return self._error_response(404, "not_found")

    @staticmethod
    def _error_response(status: int, code: str) -> ServiceResponse:
        return ServiceResponse(
            status=status,
            body=json.dumps({"ok": False, "error": {"code": code}}).encode("utf-8"),
        )

    def _handle_oauth_start(self, data: Dict[str, Any]) -> ServiceResponse:
        caller = data.get("caller", {})
        principal_id = caller.get("principal_id", "")
        if caller.get("chat_type") != "dm" or not principal_id:
            return self._error_response(403, "dm_required")
        if self.oauth_manager is None:
            return self._error_response(503, "oauth_not_configured")

        start = self.oauth_manager.create_authorization_start(principal_id)
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
        caller = data.get("caller", {})
        principal_id = caller.get("principal_id", "")
        connection_id = data.get("connection_id", "")
        if caller.get("chat_type") != "dm" or not principal_id:
            return self._error_response(403, "dm_required")
        if not connection_id:
            return self._error_response(400, "connection_id_required")

        connection = self.store.revoke_connection(principal_id, connection_id)
        self.secret_store.delete(connection.secret_ref)
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

    def _handle_search(self, data: Dict[str, Any]) -> ServiceResponse:
        caller_data = data.get("caller", {})
        caller = PolicyCaller(
            principal_id=caller_data.get("principal_id", ""),
            platform=caller_data.get("platform", "telegram"),
            user_id=caller_data.get("user_id", ""),
            chat_id=caller_data.get("chat_id", ""),
            thread_id=caller_data.get("thread_id"),
            chat_type=caller_data.get("chat_type", "dm"),
        )
        query = data.get("query", "")
        limit = data.get("limit", 10)

        connections = self.policy.readable_connections(caller)
        if not connections:
            return ServiceResponse(
                status=200,
                body=json.dumps({"ok": True, "result": {"hits": []}}).encode("utf-8"),
            )

        # Use primary readable connection
        conn = connections[0]
        delivery = self.policy.decide_delivery(caller, conn)
        if delivery.mode == "redirect_to_dm":
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

        token_data = self.secret_store.get_json(conn.secret_ref)
        hits = self.gmail_reader.search_threads(token_data, query, limit=limit)

        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "delivery": delivery.mode,
                        "hits": [asdict(h) for h in hits],
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_thread(self, data: Dict[str, Any]) -> ServiceResponse:
        caller_data = data.get("caller", {})
        caller = PolicyCaller(
            principal_id=caller_data.get("principal_id", ""),
            platform=caller_data.get("platform", "telegram"),
            user_id=caller_data.get("user_id", ""),
            chat_id=caller_data.get("chat_id", ""),
            thread_id=caller_data.get("thread_id"),
            chat_type=caller_data.get("chat_type", "dm"),
        )
        thread_id = data.get("thread_id", "")
        text_bytes_max = data.get("text_bytes_max", 65536)

        connections = self.policy.readable_connections(caller)
        if not connections:
            return ServiceResponse(
                status=404,
                body=json.dumps({"ok": False, "error": {"code": "not_authorized"}}).encode("utf-8"),
            )

        conn = connections[0]
        delivery = self.policy.decide_delivery(caller, conn)
        if delivery.mode == "redirect_to_dm":
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

        token_data = self.secret_store.get_json(conn.secret_ref)
        res = self.gmail_reader.get_thread(token_data, thread_id, text_bytes_max=text_bytes_max)
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "delivery": delivery.mode,
                        "thread": asdict(res),
                    },
                }
            ).encode("utf-8"),
        )

    def _handle_list_connections(self, data: Dict[str, Any]) -> ServiceResponse:
        principal_id = data.get("principal_id", "")
        caller = PolicyCaller(principal_id=principal_id, platform="telegram", user_id="", chat_id="", chat_type="dm")
        conns = self.policy.readable_connections(caller)
        return ServiceResponse(
            status=200,
            body=json.dumps(
                {
                    "ok": True,
                    "result": {
                        "connections": [
                            {
                                "connection_id": c.connection_id,
                                "masked_address": c.masked_address,
                                "mailbox_type": str(c.mailbox_type),
                                "status": str(c.status),
                            }
                            for c in conns
                        ]
                    },
                }
            ).encode("utf-8"),
        )
