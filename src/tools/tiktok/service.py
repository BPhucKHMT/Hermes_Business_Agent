from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)
from tools.tiktok.contracts import (
    TikTokCreatorInfo,
    TikTokPostDraft,
    TikTokPostDraftStatus,
    TikTokPostResult,
    TikTokPrivacyLevel,
    TikTokPublishStatus,
    compute_tiktok_draft_idempotency_key,
)
from tools.tiktok.policy import TikTokPolicy, load_tiktok_policy
from tools.tiktok.store import TikTokStore
from tools.tiktok.tiktok_client import TikTokClient


class TikTokService:
    def __init__(
        self,
        policy: TikTokPolicy,
        store: TikTokStore,
        tiktok_client: TikTokClient,
        token_resolver: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self.policy = policy
        self.store = store
        self.tiktok_client = tiktok_client
        self.token_resolver = token_resolver or self._default_token_resolver

    def _default_token_resolver(self, principal_id: str) -> Dict[str, Any]:
        conn = self.store.get_connection(principal_id)
        if not conn:
            return {"mock_mode": True}
        return {"access_token": "mock_tt_token", "mock_mode": True}

    def get_creator_status(self, caller: Any) -> Dict[str, Any]:
        token_data = self.token_resolver(caller.principal_id)
        info = self.tiktok_client.get_creator_info(token_data)
        self.store.upsert_connection(caller.principal_id, info.open_id, info.creator_nickname, info.creator_username)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="get_creator_status",
            target_id=info.open_id,
            details={"username": info.creator_username, "nickname": info.creator_nickname},
        )
        return {"ok": True, "result": asdict(info)}

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
        open_id: str = "mine",
    ) -> TikTokPostDraft:
        priv_enum = TikTokPrivacyLevel(privacy_level)
        self.policy.validate_post_metadata(caption=caption, privacy_level=priv_enum)
        self.policy.validate_video_file(video_file_path, skip_existence_check=True)

        idempotency_key = compute_tiktok_draft_idempotency_key(
            principal_id=caller.principal_id,
            caption=caption,
            video_file_path=video_file_path,
            privacy_level=privacy_level,
        )

        draft = TikTokPostDraft(
            draft_id=f"drf-tt-{uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            principal_id=caller.principal_id,
            open_id=open_id,
            caption=caption.strip(),
            video_file_path=video_file_path.strip(),
            privacy_level=priv_enum,
            disable_comment=disable_comment,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            brand_content_toggle=brand_content_toggle,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            status=TikTokPostDraftStatus.DRAFT,
        )

        persisted = self.store.create_or_get_draft(draft)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="create_draft_post",
            target_id=persisted.draft_id,
            details={"caption": caption, "video_file": video_file_path},
        )
        return persisted

    def publish_draft_post(self, caller: Any, draft_id: str) -> Dict[str, Any]:
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise KeyError("tiktok_draft_not_found")
        if draft.principal_id != caller.principal_id:
            raise PermissionError("principal_not_authorized_for_tiktok_draft")
        if draft.status == TikTokPostDraftStatus.SUBMITTED and draft.publish_id:
            return {"publish_id": draft.publish_id, "status": "submitted"}
        if draft.status != TikTokPostDraftStatus.DRAFT:
            raise ValueError(f"cannot_publish_draft_in_status_{draft.status.value}")

        token_data = self.token_resolver(caller.principal_id)
        publish_id = self.tiktok_client.init_video_publish(token_data=token_data, draft=draft)

        self.store.transition_draft_status(
            draft_id=draft_id,
            from_status=TikTokPostDraftStatus.DRAFT,
            to_status=TikTokPostDraftStatus.SUBMITTED,
            publish_id=publish_id,
        )

        self.store.record_audit(
            principal_id=caller.principal_id,
            action="publish_draft_post",
            target_id=publish_id,
            details={"draft_id": draft_id},
        )
        return {"publish_id": publish_id, "status": "submitted"}

    def get_post_status(self, caller: Any, publish_id: str) -> TikTokPostResult:
        token_data = self.token_resolver(caller.principal_id)
        result = self.tiktok_client.fetch_publish_status(token_data=token_data, publish_id=publish_id)
        self.store.record_audit(
            principal_id=caller.principal_id,
            action="get_post_status",
            target_id=publish_id,
            details={"status": result.status.value, "post_id": result.post_id},
        )
        return result
