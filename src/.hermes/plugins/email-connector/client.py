from __future__ import annotations

import json
from threading import Lock
from typing import Any

from tools.email.service import (
    EmailConnectorService,
    build_service_from_env,
    make_signed_headers,
)


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
            {"caller": _caller_payload(caller)},
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

    def propose_grant(
        self,
        caller: Any,
        connection_id: str,
        chat_id: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/grants/propose",
            {
                "caller": _caller_payload(caller),
                "connection_id": connection_id,
                "destination": {
                    "platform": "telegram",
                    "chat_id": chat_id,
                    "thread_id": thread_id,
                },
            },
        )

    def decide_grant(
        self,
        caller: Any,
        request_id: str,
        decision: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/grants/decide",
            {
                "caller": _caller_payload(caller),
                "request_id": request_id,
                "decision": decision,
            },
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

    def propose_grant(
        self,
        caller: Any,
        connection_id: str,
        chat_id: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        return self._response

    def decide_grant(
        self,
        caller: Any,
        request_id: str,
        decision: str,
    ) -> dict[str, Any]:
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
    try:
        service = build_service_from_env()
        return EmailConnectorClient(service, service.shared_secret)
    except RuntimeError as error:
        code = str(error)
        if code in (
            "connector_unavailable",
            "oauth_client_secret_not_configured",
        ):
            return UnavailableConnectorClient(code)
        return UnavailableConnectorClient("connector_initialization_failed")
    except Exception:
        return UnavailableConnectorClient("connector_initialization_failed")
