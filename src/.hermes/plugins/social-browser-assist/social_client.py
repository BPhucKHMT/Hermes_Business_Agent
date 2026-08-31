from __future__ import annotations

from pathlib import Path
import sys
from threading import Lock
from typing import Any


_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC = _PLUGIN_DIR.parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tools.social_connections import SocialConnectionStore


class SocialBrowserClient:
    def __init__(self, store: SocialConnectionStore | None = None) -> None:
        path = _SRC / ".runtime" / "social-browser" / "social_browser.sqlite3"
        self.store = store or SocialConnectionStore(path)

    def connection_status(self, caller: Any) -> dict[str, Any]:
        status, connection_id = self.store.status(str(caller.principal_id))
        return {
            "ok": True,
            "result": {
                "platform": "facebook-personal",
                "principal_id": str(caller.principal_id),
                "status": status,
                "connection_id": connection_id,
                "authorization_url": None,
                "reason": (
                    "Official Meta publishing authorization for personal profiles "
                    "is unavailable; eligible Page/Business OAuth is future scope."
                ),
            },
        }

_default_client: SocialBrowserClient | None = None
_default_lock = Lock()


def get_default_client() -> SocialBrowserClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = SocialBrowserClient()
        return _default_client
