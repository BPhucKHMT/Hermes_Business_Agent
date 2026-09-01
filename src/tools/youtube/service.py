from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from tools.youtube.contracts import (
    ChannelInfo,
    VideoDraft,
    VideoDraftStatus,
    VideoPrivacyStatus,
    VideoVerification,
    YouTubeVideo,
    compute_video_draft_idempotency_key,
)
from tools.youtube.policy import YouTubePolicy, load_youtube_policy
from tools.youtube.store import YouTubeStore
from tools.youtube.youtube_client import YouTubeClient


class YouTubeService:
    def __init__(
        self,
        policy: YouTubePolicy,
        store: YouTubeStore,
        youtube_client: YouTubeClient,
        token_resolver: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self.policy = policy
        self.store = store
        self.youtube_client = youtube_client
        self.token_resolver = token_resolver or self._default_token_resolver

    def _default_token_resolver(self, principal_id: str) -> Dict[str, Any]:
        conn = self.store.get_connection(principal_id)
        if not conn:
            return {"mock_mode": True}
        try:
            from tools.email.service import build_service_from_env
            email_svc = build_service_from_env()
            for c in email_svc.store.list_connections(principal_id):
                if c.secret_ref:
                    token_data = email_svc.secret_store.get_json(c.secret_ref)
                    if token_data and ("token" in token_data or "access_token" in token_data):
                        return {
                            "access_token": token_data.get("token") or token_data.get("access_token"),
                            "refresh_token": token_data.get("refresh_token"),
                            "token_uri": token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                            "client_id": token_data.get("client_id"),
                            "client_secret": token_data.get("client_secret"),
                        }
        except Exception:
            pass
        return {"access_token": "mock_yt_token", "mock_mode": True}

    def get_channel_status(self, caller: Any) -> Dict[str, Any]:
        token_data = self.token_resolver(caller.principal_id)
        info = self.youtube_client.get_channel_info(token_data)
        self.store.upsert_connection(caller.principal_id, info.channel_id, info.title)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="get_channel_status",
            target_id=info.channel_id,
            details={"title": info.title, "subscribers": info.subscriber_count},
        )
        return {"ok": True, "result": asdict(info)}

    def list_videos(self, caller: Any, limit: int = 10) -> List[YouTubeVideo]:
        token_data = self.token_resolver(caller.principal_id)
        limit = min(max(1, limit), 50)
        videos = self.youtube_client.list_channel_videos(token_data, max_results=limit)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="list_videos",
            target_id="channel_videos",
            details={"count": len(videos), "limit": limit},
        )
        return videos

    def create_draft_video(
        self,
        caller: Any,
        title: str,
        video_file_path: str,
        description: str = "",
        tags: tuple[str, ...] = (),
        privacy_status: str = "unlisted",
        thumbnail_file_path: str = "",
        channel_id: str = "mine",
    ) -> VideoDraft:
        priv_enum = VideoPrivacyStatus(privacy_status.lower())
        self.policy.validate_metadata(title=title, description=description, tags=tags, privacy_status=priv_enum)
        self.policy.validate_video_file(video_file_path, skip_existence_check=True)

        idempotency_key = compute_video_draft_idempotency_key(
            principal_id=caller.principal_id,
            channel_id=channel_id,
            title=title,
            video_file_path=video_file_path,
        )

        draft = VideoDraft(
            draft_id=f"drf-yt-{uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            principal_id=caller.principal_id,
            channel_id=channel_id,
            title=title.strip(),
            description=description.strip(),
            tags=tags,
            privacy_status=priv_enum,
            video_file_path=video_file_path.strip(),
            thumbnail_file_path=thumbnail_file_path.strip(),
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            status=VideoDraftStatus.DRAFT,
        )

        persisted = self.store.create_or_get_draft(draft)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="create_draft_video",
            target_id=persisted.draft_id,
            details={"title": title, "video_file": video_file_path},
        )
        return persisted

    def upload_draft_video(self, caller: Any, draft_id: str) -> YouTubeVideo:
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise KeyError("video_draft_not_found")
        if draft.principal_id != caller.principal_id:
            raise PermissionError("principal_not_authorized_for_video_draft")
        if draft.status == VideoDraftStatus.UPLOADED and draft.uploaded_video_id:
            token_data = self.token_resolver(caller.principal_id)
            return self.youtube_client._mock_item_to_video({"id": draft.uploaded_video_id, "title": draft.title})
        if draft.status != VideoDraftStatus.DRAFT:
            raise ValueError(f"cannot_upload_draft_in_status_{draft.status.value}")

        token_data = self.token_resolver(caller.principal_id)
        uploaded_video = self.youtube_client.upload_video(token_data=token_data, draft=draft)

        self.store.transition_draft_status(
            draft_id=draft_id,
            from_status=VideoDraftStatus.DRAFT,
            to_status=VideoDraftStatus.UPLOADED,
            uploaded_video_id=uploaded_video.video_id,
            video_url=uploaded_video.url,
        )

        self.store.record_audit(
            principal_id=caller.principal_id,
            action="upload_video",
            target_id=uploaded_video.video_id,
            details={"video_url": uploaded_video.url, "draft_id": draft_id},
        )
        return uploaded_video

    def update_metadata(
        self,
        caller: Any,
        video_id: str,
        title: str,
        description: str = "",
        tags: tuple[str, ...] = (),
        privacy_status: str = "unlisted",
    ) -> YouTubeVideo:
        priv_enum = VideoPrivacyStatus(privacy_status.lower())
        self.policy.validate_metadata(title=title, description=description, tags=tags, privacy_status=priv_enum)
        token_data = self.token_resolver(caller.principal_id)

        updated = self.youtube_client.update_video_metadata(
            token_data=token_data,
            video_id=video_id,
            title=title,
            description=description,
            tags=tags,
            privacy_status=priv_enum,
        )
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="update_metadata",
            target_id=video_id,
            details={"title": title, "privacy": privacy_status},
        )
        return updated
