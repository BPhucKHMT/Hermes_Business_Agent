from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import sys
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

for candidate in (
    Path(os.environ.get("HERMES_PROJECT_SRC", "")),
    Path(os.environ.get("HERMES_SRC_DIR", "")),
    _PLUGIN_DIR.parents[2],
    Path("C:/Hermes-Business-Agent/src"),
    Path.cwd() / "src",
    Path.cwd(),
):
    try:
        if (
            candidate
            and candidate.is_dir()
            and (candidate / "tools" / "tiktok").is_dir()
        ):
            cand_str = str(candidate.resolve())
            if cand_str not in sys.path:
                sys.path.insert(0, cand_str)
            import tools

            tools_path_str = str((candidate / "tools").resolve())
            if tools_path_str not in tools.__path__:
                tools.__path__.insert(0, tools_path_str)
            break
    except Exception:
        continue
from tools.tiktok.cli import build_service
from tools.tiktok.service import TikTokService

class TikTokConnectorClient:
    def __init__(self, service_factory: Callable[[], TikTokService] = build_service) -> None:
        self._service_factory = service_factory
        self._service: Optional[TikTokService] = None
        self._lock = Lock()

    @property
    def service(self) -> TikTokService:
        with self._lock:
            if self._service is None:
                self._service = self._service_factory()
            return self._service

    def get_creator_info(self, caller: Any) -> Dict[str, Any]:
        return self.service.get_creator_status(caller)

    def create_draft_post(
        self,
        caller: Any,
        caption: str,
        video_file_path: str,
        privacy_level: str = "SELF_ONLY",
        disable_comment: bool = False,
        disable_duet: bool = False,
        disable_stitch: bool = False,
        brand_content_toggle: bool = False,
    ) -> Dict[str, Any]:
        draft = self.service.create_draft_post(
            caller=caller,
            caption=caption,
            video_file_path=video_file_path,
            privacy_level=privacy_level,
            disable_comment=disable_comment,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            brand_content_toggle=brand_content_toggle,
        )
        return {
            "ok": True,
            "result": {
                "draft": asdict(draft),
                "action_required": "Please review post settings and invoke tiktok_publish_video with draft_id to publish.",
            },
        }

    def publish_video(self, caller: Any, draft_id: str) -> Dict[str, Any]:
        res = self.service.publish_draft_post(caller=caller, draft_id=draft_id)
        return {"ok": True, "result": res}

    def get_post_status(self, caller: Any, publish_id: str) -> Dict[str, Any]:
        res = self.service.get_post_status(caller=caller, publish_id=publish_id)
        return {"ok": True, "result": asdict(res)}


_default_client: Optional[TikTokConnectorClient] = None
_default_lock = Lock()


def get_default_client() -> TikTokConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = TikTokConnectorClient()
        return _default_client
