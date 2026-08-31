from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, List, Optional

from tools.tiktok.contracts import TikTokPrivacyLevel


@dataclass(frozen=True)
class TikTokPolicy:
    schema_version: int
    default_privacy_level: TikTokPrivacyLevel
    allowed_privacy_levels: tuple[TikTokPrivacyLevel, ...]
    max_caption_chars: int
    max_video_size_bytes: int
    allowed_video_extensions: tuple[str, ...]
    scopes: tuple[str, ...]

    def validate_post_metadata(
        self,
        caption: str,
        privacy_level: Optional[TikTokPrivacyLevel] = None,
    ) -> None:
        if len(caption) > self.max_caption_chars:
            raise ValueError(f"caption_exceeds_max_chars_{self.max_caption_chars}")
        if privacy_level is not None and privacy_level not in self.allowed_privacy_levels:
            raise ValueError(f"invalid_privacy_level_{privacy_level.value}")

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


def load_tiktok_policy(path: Path | str) -> TikTokPolicy:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_tiktok_policy")
    if data.get("schema_version") != 1:
        raise ValueError("unsupported_policy_schema_version")

    default_priv = TikTokPrivacyLevel(data.get("default_privacy_level", "SELF_ONLY"))
    allowed_priv = tuple(TikTokPrivacyLevel(s) for s in data.get("allowed_privacy_levels", ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY", "FOLLOWER_OF_CREATOR"]))
    return TikTokPolicy(
        schema_version=int(data["schema_version"]),
        default_privacy_level=default_priv,
        allowed_privacy_levels=allowed_priv,
        max_caption_chars=int(data.get("max_caption_chars", 2200)),
        max_video_size_bytes=int(data.get("max_video_size_bytes", 1073741824)),
        allowed_video_extensions=tuple(ext.lower() for ext in data.get("allowed_video_extensions", [".mp4", ".mov", ".webm"])),
        scopes=tuple(data.get("scopes", ())),
    )
