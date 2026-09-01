from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
import urllib.parse
import urllib.request
from uuid import uuid4

from tools.youtube.contracts import (
    ChannelInfo,
    VideoDraft,
    VideoPrivacyStatus,
    YouTubeVideo,
)


class YouTubeClient:
    def __init__(self, http_client: Any = None) -> None:
        self.http_client = http_client

    def _get_headers(self, token_data: Dict[str, Any]) -> Dict[str, str]:
        token = token_data.get("access_token") or token_data.get("token") or ""
        if not token and not token_data.get("mock_mode"):
            raise ValueError("missing_access_token")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _refresh_access_token(self, token_data: Dict[str, Any]) -> str:
        import os
        refresh_token = token_data.get("refresh_token")
        client_id = token_data.get("client_id") or os.environ.get("EMAIL_GOOGLE_CLIENT_ID")
        client_secret = token_data.get("client_secret") or os.environ.get("EMAIL_GOOGLE_CLIENT_SECRET")
        token_uri = token_data.get("token_uri", "https://oauth2.googleapis.com/token")

        if not refresh_token or not client_id or not client_secret:
            return token_data.get("access_token") or token_data.get("token") or ""

        body = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")
        req = urllib.request.Request(token_uri, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                new_tok = data.get("access_token")
                if new_tok:
                    token_data["access_token"] = new_tok
                    token_data["token"] = new_tok
                    return new_tok
        except Exception:
            pass
        return token_data.get("access_token") or token_data.get("token") or ""

    def _request_json(
        self,
        token_data: Dict[str, Any],
        url: str,
        method: str = "GET",
        body_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        headers = self._get_headers(token_data)
        if self.http_client is not None:
            if method == "GET":
                return self.http_client.get(url, headers=headers)
            elif method == "POST":
                return self.http_client.post(url, headers=headers, body=body_bytes)
            elif method == "DELETE":
                return self.http_client.delete(url, headers=headers)

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 204 or not resp.length:
                    return {"status": resp.status}
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as err:
            if err.code == 401:
                new_tok = self._refresh_access_token(token_data)
                if new_tok and new_tok != headers.get("Authorization", "").replace("Bearer ", ""):
                    headers = self._get_headers(token_data)
                    retry_req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
                    with urllib.request.urlopen(retry_req, timeout=15) as resp:
                        if resp.status == 204 or not resp.length:
                            return {"status": resp.status}
                        return json.loads(resp.read().decode("utf-8"))
            raise RuntimeError(f"youtube_api_error_{err.code}") from err
    def get_channel_info(self, token_data: Dict[str, Any], channel_id: str = "mine") -> ChannelInfo:
        if token_data.get("mock_mode") or "mock_channel" in token_data:
            mock = token_data.get("mock_channel", {})
            return ChannelInfo(
                channel_id=mock.get("id", "UC-mock-channel-123"),
                title=mock.get("title", "TITAN AI Studio"),
                description=mock.get("description", "Official TITAN AI Channel"),
                custom_url=mock.get("customUrl", "@titanai"),
                subscriber_count=int(mock.get("subscriberCount", 12500)),
                video_count=int(mock.get("videoCount", 48)),
                status="connected",
            )

        url = "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true"
        res_data = self._request_json(token_data, url, method="GET")
        items = res_data.get("items", [])
        if not items:
            raise RuntimeError("no_youtube_channel_found")
        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        return ChannelInfo(
            channel_id=str(item.get("id", "")),
            title=str(snippet.get("title", "")),
            description=str(snippet.get("description", "")),
            custom_url=str(snippet.get("customUrl", "")),
            subscriber_count=int(stats.get("subscriberCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
            status="connected",
        )

    def list_channel_videos(self, token_data: Dict[str, Any], max_results: int = 10) -> List[YouTubeVideo]:
        if token_data.get("mock_mode") or "mock_videos" in token_data:
            mock_list = token_data.get("mock_videos", [])
            return [self._mock_item_to_video(item) for item in mock_list]

        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&forMine=true&type=video&maxResults={max_results}"
        res_data = self._request_json(token_data, url, method="GET")
        items = res_data.get("items", [])
        videos = []
        for item in items:
            v_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            videos.append(
                YouTubeVideo(
                    video_id=v_id,
                    channel_id=str(snippet.get("channelId", "")),
                    title=str(snippet.get("title", "")),
                    description=str(snippet.get("description", "")),
                    tags=(),
                    privacy_status=VideoPrivacyStatus.PUBLIC,
                    published_at=str(snippet.get("publishedAt", "")),
                    view_count=0,
                    like_count=0,
                    url=f"https://www.youtube.com/watch?v={v_id}",
                    thumbnail_url=str(snippet.get("thumbnails", {}).get("default", {}).get("url", "")),
                )
            )
        return videos

    def upload_video(self, token_data: Dict[str, Any], draft: VideoDraft) -> YouTubeVideo:
        if token_data.get("mock_mode") or "mock_mode" in token_data:
            v_id = f"yt-{uuid4().hex[:11]}"
            return YouTubeVideo(
                video_id=v_id,
                channel_id=draft.channel_id or "UC-mock-channel-123",
                title=draft.title,
                description=draft.description,
                tags=draft.tags,
                privacy_status=draft.privacy_status,
                published_at=draft.created_at,
                view_count=0,
                like_count=0,
                url=f"https://www.youtube.com/watch?v={v_id}",
                thumbnail_url=f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg",
            )

        url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = self._get_headers(token_data)

        payload = {
            "snippet": {
                "title": draft.title,
                "description": draft.description,
                "tags": list(draft.tags),
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": draft.privacy_status.value,
                "selfDeclaredMadeForKids": False,
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
                raise RuntimeError(f"youtube_upload_api_error_{err.code}") from err

        v_id = str(res_data.get("id", ""))
        return YouTubeVideo(
            video_id=v_id,
            channel_id=draft.channel_id,
            title=draft.title,
            description=draft.description,
            tags=draft.tags,
            privacy_status=draft.privacy_status,
            published_at=draft.created_at,
            view_count=0,
            like_count=0,
            url=f"https://www.youtube.com/watch?v={v_id}",
            thumbnail_url=f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg",
        )

    def update_video_metadata(
        self,
        token_data: Dict[str, Any],
        video_id: str,
        title: str,
        description: str,
        tags: tuple[str, ...],
        privacy_status: VideoPrivacyStatus,
    ) -> YouTubeVideo:
        if token_data.get("mock_mode"):
            return YouTubeVideo(
                video_id=video_id,
                channel_id="UC-mock-channel-123",
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy_status,
                published_at="2026-08-31T12:00:00Z",
                view_count=100,
                like_count=10,
                url=f"https://www.youtube.com/watch?v={video_id}",
                thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            )

        url = "https://www.googleapis.com/youtube/v3/videos?part=snippet,status"
        headers = self._get_headers(token_data)
        payload = {
            "id": video_id,
            "snippet": {
                "title": title,
                "description": description,
                "tags": list(tags),
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy_status.value,
            },
        }
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if self.http_client is not None:
            res_data = self.http_client.put(url, headers=headers, body=body_bytes)
        else:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="PUT")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as err:
                raise RuntimeError(f"youtube_update_api_error_{err.code}") from err

        return self._mock_item_to_video(res_data)

    def _mock_item_to_video(self, item: Dict[str, Any]) -> YouTubeVideo:
        v_id = str(item.get("id", "yt-mock-123"))
        return YouTubeVideo(
            video_id=v_id,
            channel_id=str(item.get("channelId", "UC-mock-channel-123")),
            title=str(item.get("title", "Sample Video")),
            description=str(item.get("description", "")),
            tags=tuple(item.get("tags", ())),
            privacy_status=VideoPrivacyStatus(item.get("privacyStatus", "unlisted")),
            published_at=str(item.get("publishedAt", "2026-08-31T12:00:00Z")),
            view_count=int(item.get("viewCount", 0)),
            like_count=int(item.get("likeCount", 0)),
            url=f"https://www.youtube.com/watch?v={v_id}",
            thumbnail_url=str(item.get("thumbnailUrl", f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg")),
        )
