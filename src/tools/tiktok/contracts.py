from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Optional
from uuid import uuid4


class TikTokPrivacyLevel(str, Enum):
    PUBLIC_TO_EVERYONE = "PUBLIC_TO_EVERYONE"
    MUTUAL_FOLLOW_FRIENDS = "MUTUAL_FOLLOW_FRIENDS"
    SELF_ONLY = "SELF_ONLY"
    FOLLOWER_OF_CREATOR = "FOLLOWER_OF_CREATOR"


class TikTokPostDraftStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


class TikTokPublishStatus(str, Enum):
    PROCESSING_DOWNLOAD = "PROCESSING_DOWNLOAD"
    PROCESSING_UPLOAD = "PROCESSING_UPLOAD"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TikTokCreatorInfo:
    open_id: str
    creator_nickname: str
    creator_username: str
    creator_avatar_url: str
    privacy_level_options: tuple[str, ...]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: int
    status: str = "connected"


@dataclass(frozen=True)
class TikTokPostDraft:
    draft_id: str
    idempotency_key: str
    principal_id: str
    open_id: str
    caption: str
    video_file_path: str
    privacy_level: TikTokPrivacyLevel
    disable_comment: bool
    disable_duet: bool
    disable_stitch: bool
    brand_content_toggle: bool
    created_at: str
    status: TikTokPostDraftStatus = TikTokPostDraftStatus.DRAFT
    publish_id: Optional[str] = None
    published_post_id: Optional[str] = None


@dataclass(frozen=True)
class TikTokPostResult:
    publish_id: str
    status: TikTokPublishStatus
    post_id: Optional[str] = None
    fail_reason: Optional[str] = None


def compute_tiktok_draft_idempotency_key(
    principal_id: str,
    caption: str,
    video_file_path: str,
    privacy_level: str,
) -> str:
    payload = {
        "caption": caption.strip(),
        "principal_id": principal_id.strip(),
        "privacy_level": privacy_level.strip(),
        "video_file_path": video_file_path.strip(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
