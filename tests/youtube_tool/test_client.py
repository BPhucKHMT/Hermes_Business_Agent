from tools.youtube.contracts import VideoDraft, VideoPrivacyStatus
from tools.youtube.youtube_client import YouTubeClient


def test_youtube_client_get_channel_info_mock() -> None:
    client = YouTubeClient()
    token_data = {
        "mock_mode": True,
        "mock_channel": {
            "id": "UC-sample-123",
            "title": "TITAN AI Official",
            "description": "Enterprise AI systems",
            "customUrl": "@titan_official",
            "subscriberCount": 85000,
            "videoCount": 92,
        },
    }
    info = client.get_channel_info(token_data)
    assert info.channel_id == "UC-sample-123"
    assert info.title == "TITAN AI Official"
    assert info.subscriber_count == 85000


def test_youtube_client_upload_video_mock() -> None:
    client = YouTubeClient()
    draft = VideoDraft(
        draft_id="drf-123",
        idempotency_key="key-123",
        principal_id="telegram:default:123",
        channel_id="UC-sample-123",
        title="Automated Video",
        description="Demo video",
        tags=("demo",),
        privacy_status=VideoPrivacyStatus.UNLISTED,
        video_file_path="sample.mp4",
        thumbnail_file_path="",
        created_at="2026-08-31T12:00:00Z",
    )
    uploaded = client.upload_video({"mock_mode": True}, draft)
    assert uploaded.title == "Automated Video"
    assert uploaded.url.startswith("https://www.youtube.com/watch?v=")
    assert "yt-" in uploaded.video_id
