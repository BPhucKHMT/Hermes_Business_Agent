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
    Path.home() / "Hermes-Business-Agent" / "src",
    Path("/home/azureuser/Hermes-Business-Agent/src"),
    _PLUGIN_DIR.parents[2] / "Hermes-Business-Agent" / "src",
    _PLUGIN_DIR.parents[2],
    Path("C:/Hermes-Business-Agent/src"),
    Path.cwd() / "src",
    Path.cwd(),
):
    try:
        if (
            candidate
            and candidate.is_dir()
            and (candidate / "tools" / "youtube").is_dir()
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
from tools.youtube.cli import build_service
from tools.youtube.service import YouTubeService

class YouTubeConnectorClient:
    def __init__(self, service_factory: Callable[[], YouTubeService] = build_service) -> None:
        self._service_factory = service_factory
        self._service: Optional[YouTubeService] = None
        self._lock = Lock()

    @property
    def service(self) -> YouTubeService:
        with self._lock:
            if self._service is None:
                self._service = self._service_factory()
            return self._service

    def get_channel_status(self, caller: Any) -> Dict[str, Any]:
        return self.service.get_channel_status(caller)

    def list_videos(self, caller: Any, limit: int = 10) -> Dict[str, Any]:
        videos = self.service.list_videos(caller=caller, limit=limit)
        return {"ok": True, "result": {"videos": [asdict(v) for v in videos], "count": len(videos)}}

    def create_draft_video(
        self,
        caller: Any,
        title: str,
        video_file_path: str,
        description: str = "",
        tags: tuple[str, ...] = (),
        privacy_status: str = "unlisted",
        thumbnail_file_path: str = "",
    ) -> Dict[str, Any]:
        draft = self.service.create_draft_video(
            caller=caller,
            title=title,
            video_file_path=video_file_path,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            thumbnail_file_path=thumbnail_file_path,
        )
        return {
            "ok": True,
            "result": {
                "draft": asdict(draft),
                "action_required": "Please review video metadata and invoke youtube_upload_video with draft_id to upload.",
            },
        }

    def upload_video(self, caller: Any, draft_id: str) -> Dict[str, Any]:
        video = self.service.upload_draft_video(caller=caller, draft_id=draft_id)
        return {"ok": True, "result": {"video": asdict(video), "uploaded": True}}

    def update_metadata(
        self,
        caller: Any,
        video_id: str,
        title: str,
        description: str = "",
        tags: tuple[str, ...] = (),
        privacy_status: str = "unlisted",
    ) -> Dict[str, Any]:
        video = self.service.update_metadata(
            caller=caller,
            video_id=video_id,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
        )
        return {"ok": True, "result": {"video": asdict(video), "updated": True}}


_default_client: Optional[YouTubeConnectorClient] = None
_default_lock = Lock()


def get_default_client() -> YouTubeConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = YouTubeConnectorClient()
        return _default_client
