from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, List, Optional

from tools.youtube.contracts import VideoPrivacyStatus


@dataclass(frozen=True)
class YouTubePolicy:
    schema_version: int
    default_privacy_status: VideoPrivacyStatus
    allowed_privacy_statuses: tuple[VideoPrivacyStatus, ...]
    max_video_size_bytes: int
    allowed_video_extensions: tuple[str, ...]
    max_title_chars: int
    max_description_chars: int
    max_tags_count: int
    scopes: tuple[str, ...]

    def validate_metadata(
        self,
        title: str,
        description: str = "",
        tags: tuple[str, ...] = (),
        privacy_status: Optional[VideoPrivacyStatus] = None,
    ) -> None:
        if not title or not title.strip():
            raise ValueError("title_required")
        if len(title.strip()) > self.max_title_chars:
            raise ValueError(f"title_exceeds_max_chars_{self.max_title_chars}")
        if len(description) > self.max_description_chars:
            raise ValueError(f"description_exceeds_max_chars_{self.max_description_chars}")
        if len(tags) > self.max_tags_count:
            raise ValueError(f"tags_count_exceeds_max_{self.max_tags_count}")
        if privacy_status is not None and privacy_status not in self.allowed_privacy_statuses:
            raise ValueError(f"invalid_privacy_status_{privacy_status.value}")

    def validate_video_file(self, file_path: Path | str, skip_existence_check: bool = False) -> None:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in self.allowed_video_extensions:
            raise ValueError(f"unsupported_video_extension_{ext}")
        if not skip_existence_check:
            if not path.is_file():
                raise FileNotFoundError(f"video_file_not_found_{path}")
            size = path.stat().st_size
            if size > self.max_video_size_bytes:
                raise ValueError(f"video_file_too_large_{size}_max_{self.max_video_size_bytes}")


def load_youtube_policy(path: Path | str) -> YouTubePolicy:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_youtube_policy")
    if data.get("schema_version") != 1:
        raise ValueError("unsupported_policy_schema_version")

    default_priv = VideoPrivacyStatus(data.get("default_privacy_status", "unlisted"))
    allowed_priv = tuple(VideoPrivacyStatus(s) for s in data.get("allowed_privacy_statuses", ["private", "unlisted", "public"]))
    return YouTubePolicy(
        schema_version=int(data["schema_version"]),
        default_privacy_status=default_priv,
        allowed_privacy_statuses=allowed_priv,
        max_video_size_bytes=int(data.get("max_video_size_bytes", 1073741824)),
        allowed_video_extensions=tuple(ext.lower() for ext in data.get("allowed_video_extensions", [".mp4", ".mov", ".webm"])),
        max_title_chars=int(data.get("max_title_chars", 100)),
        max_description_chars=int(data.get("max_description_chars", 5000)),
        max_tags_count=int(data.get("max_tags_count", 30)),
        scopes=tuple(data.get("scopes", ())),
    )
