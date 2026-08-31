from tools.youtube.contracts import (
    ChannelInfo,
    VideoDraft,
    VideoDraftStatus,
    VideoPrivacyStatus,
    YouTubeVideo,
    compute_video_draft_idempotency_key,
)


def test_compute_video_draft_idempotency_key() -> None:
    key1 = compute_video_draft_idempotency_key(
        principal_id="telegram:default:123",
        channel_id="mine",
        title="TITAN AI Episode 1",
        video_file_path="C:/videos/ep1.mp4",
    )
    key2 = compute_video_draft_idempotency_key(
        principal_id="telegram:default:123",
        channel_id="mine",
        title="titan ai episode 1",
        video_file_path="C:/videos/ep1.mp4",
    )
    assert key1 == key2
    assert len(key1) == 64


def test_video_draft_structure() -> None:
    draft = VideoDraft(
        draft_id="drf-yt-001",
        idempotency_key="key-001",
        principal_id="telegram:default:123",
        channel_id="UC-123",
        title="Product Launch",
        description="Launch details",
        tags=("startup", "ai"),
        privacy_status=VideoPrivacyStatus.UNLISTED,
        video_file_path="video.mp4",
        thumbnail_file_path="thumb.png",
        created_at="2026-08-31T12:00:00Z",
        status=VideoDraftStatus.DRAFT,
    )
    assert draft.status == VideoDraftStatus.DRAFT
    assert len(draft.tags) == 2


def test_channel_info_structure() -> None:
    info = ChannelInfo(
        channel_id="UC-999",
        title="TITAN AI",
        description="AI Automation agency",
        custom_url="@titanai",
        subscriber_count=50000,
        video_count=120,
    )
    assert info.subscriber_count == 50000
    assert info.status == "connected"
