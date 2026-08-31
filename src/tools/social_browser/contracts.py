from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import hmac
import json
from pathlib import Path
import unicodedata
from uuid import uuid4


class RunStatus(str, Enum):
    REQUESTED = "requested"
    PREPARING = "preparing"
    READY_FOR_HUMAN = "ready_for_human"
    PUBLISHED = "published"
    BLOCKED_LOGIN = "blocked_login"
    BLOCKED_ACCOUNT_MISMATCH = "blocked_account_mismatch"
    BLOCKED_CHALLENGE = "blocked_challenge"
    FAILED_UI_DRIFT = "failed_ui_drift"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BrowserOperation(str, Enum):
    OPEN = "open"
    OBSERVE = "observe"
    ACTIVATE_CONTROL = "activate_control"
    FILL = "fill"
    UPLOAD = "upload"
    CLOSE = "close"


@dataclass(frozen=True)
class MediaItem:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class AccessibleNode:
    backend_node_id: int
    role: str
    name: str


@dataclass(frozen=True)
class SocialActionManifest:
    run_id: str
    idempotency_key: str
    platform: str
    account_label: str
    text: str
    media: tuple[MediaItem, ...]
    audience: str
    created_at: str
    expires_at: str
    status: RunStatus = RunStatus.REQUESTED

    def verify_media(self) -> None:
        for item in self.media:
            path = Path(item.path)
            if not path.is_file():
                raise ValueError("media_not_found")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if not hmac.compare_digest(digest, item.sha256):
                raise ValueError("media_digest_mismatch")


@dataclass(frozen=True)
class BrowserObservation:
    url: str
    title: str
    account_label: str
    accessible_nodes: tuple[AccessibleNode, ...]
    warning_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparationResult:
    run_id: str
    status: RunStatus
    account_label: str
    text_digest: str
    media_digests: tuple[str, ...]
    audience: str
    evidence_paths: tuple[str, ...]
    verified_post_id: str | None = None
    failure_code: str | None = None


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", str(value or ""))
    return normalized.replace("\r\n", "\n").replace("\r", "\n").strip()


def _media_item(path: Path) -> MediaItem:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("media_not_found")
    data = resolved.read_bytes()
    return MediaItem(str(resolved), hashlib.sha256(data).hexdigest(), len(data))


def _idempotency_key(
    platform: str,
    account_label: str,
    text: str,
    media: tuple[MediaItem, ...],
    audience: str,
) -> str:
    payload = {
        "account_label": account_label,
        "audience": audience,
        "media": [item.sha256 for item in media],
        "platform": platform,
        "text": text,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_manifest(
    platform: str,
    account_label: str,
    text: str,
    media_paths: list[Path],
    audience: str,
) -> SocialActionManifest:
    normalized_platform = normalize_text(platform).casefold()
    normalized_account = normalize_text(account_label)
    normalized_text = normalize_text(text)
    normalized_audience = normalize_text(audience).casefold()
    media = tuple(_media_item(Path(path)) for path in media_paths)
    if not normalized_text and not media:
        raise ValueError("content_required")
    if not normalized_platform or not normalized_account or not normalized_audience:
        raise ValueError("manifest_field_required")
    key = _idempotency_key(
        normalized_platform,
        normalized_account,
        normalized_text,
        media,
        normalized_audience,
    )
    now = datetime.now(timezone.utc)
    return SocialActionManifest(
        run_id=f"social-{key[:24]}-{uuid4().hex[:8]}",
        idempotency_key=key,
        platform=normalized_platform,
        account_label=normalized_account,
        text=normalized_text,
        media=media,
        audience=normalized_audience,
        created_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    )
