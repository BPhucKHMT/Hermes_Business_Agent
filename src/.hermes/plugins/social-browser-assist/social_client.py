from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import sys
from threading import Lock
from typing import Any, Callable


_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC = _PLUGIN_DIR.parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tools.social_browser.cli import build_service
from tools.social_browser.service import PrepareFacebookRequest, SocialBrowserService


def _allowed_users() -> frozenset[str]:
    raw = os.environ.get("SOCIAL_BROWSER_ALLOWED_TELEGRAM_USERS", "")
    return frozenset(value.strip() for value in raw.split(",") if value.strip())


def _result_payload(result) -> dict[str, Any]:
    data = asdict(result)
    data["status"] = result.status.value
    return data


class SocialBrowserClient:
    def __init__(
        self, service_factory: Callable[[], SocialBrowserService] = build_service
    ) -> None:
        self._service_factory = service_factory
        self._service: SocialBrowserService | None = None
        self._lock = Lock()

    @property
    def service(self) -> SocialBrowserService:
        with self._lock:
            if self._service is None:
                self._service = self._service_factory()
            return self._service

    def prepare(self, caller: Any, params: dict[str, Any]) -> dict[str, Any]:
        self._require_allowed_caller(caller)
        request = PrepareFacebookRequest(
            account_label=str(params.get("account_label", "")),
            text=str(params.get("text", "")),
            media_paths=tuple(Path(value) for value in params.get("media_paths", [])),
            audience=str(params.get("audience", "")),
        )
        return {"ok": True, "result": _result_payload(self.service.prepare(request))}

    def status(self, caller: Any, run_id: str) -> dict[str, Any]:
        self._require_allowed_caller(caller)
        return {
            "ok": True,
            "result": _result_payload(self.service.status(run_id)),
        }

    def verify(self, caller: Any, run_id: str) -> dict[str, Any]:
        self._require_allowed_caller(caller)
        return {
            "ok": True,
            "result": _result_payload(self.service.verify_after_human(run_id)),
        }

    def _require_allowed_caller(self, caller: Any) -> None:
        users = _allowed_users()
        if not users:
            raise PermissionError("social_browser_caller_allowlist_required")
        if str(caller.user_id) not in users:
            raise PermissionError("social_browser_caller_not_allowed")


_default_client: SocialBrowserClient | None = None
_default_lock = Lock()


def get_default_client() -> SocialBrowserClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = SocialBrowserClient()
        return _default_client
