from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
import os
from pathlib import Path
import sys
from threading import Lock
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))


def _candidate_src_dirs() -> list[Path]:
    candidates: list[Path] = []
    for key in ("HERMES_PROJECT_SRC", "HERMES_SRC_DIR"):
        val = os.environ.get(key)
        if val and (Path(val) / "tools").is_dir():
            candidates.append(Path(val))
    if len(Path(__file__).resolve().parents) >= 3:
        parent_candidate = Path(__file__).resolve().parents[2]
        if (parent_candidate / "tools").is_dir():
            candidates.append(parent_candidate)
    for env_file in (
        Path.home() / ".hermes" / ".env",
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
        if os.name == "nt"
        else None,
    ):
        if env_file and env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("HERMES_PROJECT_SRC="):
                        val = (
                            line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        )
                        if val and (Path(val) / "tools").is_dir():
                            candidates.append(Path(val))
            except OSError:
                pass
    for cwd_cand in (Path.cwd() / "src", Path.cwd()):
        if (cwd_cand / "tools").is_dir():
            candidates.append(cwd_cand)
    return candidates


for candidate in _candidate_src_dirs():
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
    except Exception:  # noqa: BLE001 -- probe candidate dirs, keep searching
        continue
from tools.tiktok.cli import build_service  # noqa: E402 -- needs plugin path bootstrap
from tools.tiktok.service import (  # noqa: E402 -- plugin source path is bootstrapped above
    TikTokService,
)


class TikTokConnectorClient:
    def __init__(
        self, service_factory: Callable[[], TikTokService] = build_service
    ) -> None:
        self._service_factory = service_factory
        self._service: TikTokService | None = None
        self._lock = Lock()

    @property
    def service(self) -> TikTokService:
        with self._lock:
            if self._service is None:
                self._service = self._service_factory()
            return self._service

    def get_creator_info(self, caller: Any) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def publish_video(self, caller: Any, draft_id: str) -> dict[str, Any]:
        res = self.service.publish_draft_post(caller=caller, draft_id=draft_id)
        return {"ok": True, "result": res}

    def get_post_status(self, caller: Any, publish_id: str) -> dict[str, Any]:
        res = self.service.get_post_status(caller=caller, publish_id=publish_id)
        return {"ok": True, "result": asdict(res)}


_default_client: TikTokConnectorClient | None = None
_default_lock = Lock()


def get_default_client() -> TikTokConnectorClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = TikTokConnectorClient()
        return _default_client
