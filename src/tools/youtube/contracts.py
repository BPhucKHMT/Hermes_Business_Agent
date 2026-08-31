from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Optional
from uuid import uuid4


class VideoPrivacyStatus(str, Enum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class VideoDraftStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    UPLOADED = "uploaded"
    FAILED = "failed"


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    channel_id: str
    title: str
    description: str
    tags: tuple[str, ...]
    privacy_status: VideoPrivacyStatus
    published_at: str
    view_count: int
    like_count: int
    url: str
    thumbnail_url: str


@dataclass(frozen=True)
class VideoDraft:
    draft_id: str
    idempotency_key: str
    principal_id: str
    channel_id: str
    title: str
    description: str
    tags: tuple[str, ...]
    privacy_status: VideoPrivacyStatus
    video_file_path: str
    thumbnail_file_path: str
    created_at: str
    status: VideoDraftStatus = VideoDraftStatus.DRAFT
    uploaded_video_id: Optional[str] = None
    video_url: Optional[str] = None


@dataclass(frozen=True)
class ChannelInfo:
    channel_id: str
    title: str
    description: str
    custom_url: str
    subscriber_count: int
    video_count: int
    status: str = "connected"


@dataclass(frozen=True)
class VideoVerification:
    verified: bool
    video_id: str
    url: str
    observed_at: str


def compute_video_draft_idempotency_key(
    principal_id: str,
    channel_id: str,
    title: str,
    video_file_path: str,
) -> str:
    payload = {
        "channel_id": channel_id.strip(),
        "principal_id": principal_id.strip(),
        "title": title.strip().lower(),
        "video_file_path": video_file_path.strip(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
