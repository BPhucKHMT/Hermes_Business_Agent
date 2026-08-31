from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
import urllib.parse
import urllib.request
from uuid import uuid4

from tools.tiktok.contracts import (
    TikTokCreatorInfo,
    TikTokPostDraft,
    TikTokPostResult,
    TikTokPublishStatus,
)


class TikTokClient:
    def __init__(self, http_client: Any = None) -> None:
        self.http_client = http_client

    def _get_headers(self, token_data: Dict[str, Any]) -> Dict[str, str]:
        token = token_data.get("access_token", "")
        if not token and not token_data.get("mock_mode"):
            raise ValueError("missing_access_token")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def get_creator_info(self, token_data: Dict[str, Any]) -> TikTokCreatorInfo:
        if token_data.get("mock_mode") or "mock_creator" in token_data:
            mock = token_data.get("mock_creator", {})
            return TikTokCreatorInfo(
                open_id=mock.get("open_id", "open-id-tiktok-123"),
                creator_nickname=mock.get("creator_nickname", "TITAN AI Shorts"),
                creator_username=mock.get("creator_username", "titan_ai_shorts"),
                creator_avatar_url=mock.get("creator_avatar_url", "https://p16-tiktokcdn.com/avatar.jpg"),
                privacy_level_options=tuple(mock.get("privacy_level_options", ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"))),
                comment_disabled=mock.get("comment_disabled", False),
                duet_disabled=mock.get("duet_disabled", False),
                stitch_disabled=mock.get("stitch_disabled", False),
                max_video_post_duration_sec=int(mock.get("max_video_post_duration_sec", 600)),
                status="connected",
            )

        url = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
        headers = self._get_headers(token_data)

        if self.http_client is not None:
            res_data = self.http_client.post(url, headers=headers, body=b"{}")
        else:
            req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as err:
                raise RuntimeError(f"tiktok_api_error_{err.code}") from err

        data = res_data.get("data", {})
        error = res_data.get("error", {})
        if error.get("code") != "ok" and data is None:
            raise RuntimeError(f"tiktok_api_error_{error.get('code')}")

        return TikTokCreatorInfo(
            open_id=str(data.get("open_id", "")),
            creator_nickname=str(data.get("creator_nickname", "")),
            creator_username=str(data.get("creator_username", "")),
            creator_avatar_url=str(data.get("creator_avatar_url", "")),
            privacy_level_options=tuple(data.get("privacy_level_options", ())),
            comment_disabled=bool(data.get("comment_disabled", False)),
            duet_disabled=bool(data.get("duet_disabled", False)),
            stitch_disabled=bool(data.get("stitch_disabled", False)),
            max_video_post_duration_sec=int(data.get("max_video_post_duration_sec", 600)),
            status="connected",
        )

    def init_video_publish(self, token_data: Dict[str, Any], draft: TikTokPostDraft) -> str:
        if token_data.get("mock_mode") or "mock_mode" in token_data:
            return f"pub-tt-{uuid4().hex[:16]}"

        url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = self._get_headers(token_data)

        payload = {
            "post_info": {
                "title": draft.caption,
                "privacy_level": draft.privacy_level.value,
                "disable_duet": draft.disable_duet,
                "disable_comment": draft.disable_comment,
                "disable_stitch": draft.disable_stitch,
                "video_cover_timestamp_ms": 1000,
                "brand_content_toggle": draft.brand_content_toggle,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": Path(draft.video_file_path).stat().st_size if Path(draft.video_file_path).is_file() else 10000,
                "chunk_size": Path(draft.video_file_path).stat().st_size if Path(draft.video_file_path).is_file() else 10000,
                "total_chunk_count": 1,
            },
        }

        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if self.http_client is not None:
            res_data = self.http_client.post(url, headers=headers, body=body_bytes)
        else:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as err:
                raise RuntimeError(f"tiktok_publish_init_api_error_{err.code}") from err

        publish_id = res_data.get("data", {}).get("publish_id", "")
        if not publish_id:
            raise RuntimeError("tiktok_missing_publish_id_in_response")
        return str(publish_id)

    def fetch_publish_status(self, token_data: Dict[str, Any], publish_id: str) -> TikTokPostResult:
        if token_data.get("mock_mode") or "mock_mode" in token_data:
            return TikTokPostResult(
                publish_id=publish_id,
                status=TikTokPublishStatus.SUCCESS,
                post_id=f"item-tt-{uuid4().hex[:16]}",
                fail_reason=None,
            )

        url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
        headers = self._get_headers(token_data)
        payload = {"publish_id": publish_id}
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if self.http_client is not None:
            res_data = self.http_client.post(url, headers=headers, body=body_bytes)
        else:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as err:
                raise RuntimeError(f"tiktok_status_api_error_{err.code}") from err

        data = res_data.get("data", {})
        status_str = data.get("status", "PROCESSING_UPLOAD")
        return TikTokPostResult(
            publish_id=publish_id,
            status=TikTokPublishStatus(status_str),
            post_id=data.get("publically_available_post_id"),
            fail_reason=data.get("fail_reason"),
        )
