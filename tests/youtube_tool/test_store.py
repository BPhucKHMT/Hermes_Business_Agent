from pathlib import Path
import pytest

from tools.youtube.contracts import VideoDraft, VideoDraftStatus, VideoPrivacyStatus
from tools.youtube.store import YouTubeStore


@pytest.fixture
def store(tmp_path: Path) -> YouTubeStore:
    return YouTubeStore(tmp_path / "youtube_test.sqlite3")


def test_upsert_and_get_connection(store: YouTubeStore) -> None:
    store.upsert_connection(
        principal_id="telegram:default:7275339077",
        channel_id="UC-12345",
        channel_title="TITAN AI Lab",
    )
    conn = store.get_connection("telegram:default:7275339077")
    assert conn is not None
    assert conn["channel_id"] == "UC-12345"
    assert conn["channel_title"] == "TITAN AI Lab"
    assert conn["status"] == "connected"


def test_create_and_get_video_draft(store: YouTubeStore) -> None:
    draft = VideoDraft(
        draft_id="drf-yt-101",
        idempotency_key="key-yt-101",
        principal_id="telegram:default:7275339077",
        channel_id="UC-12345",
        title="Agent Tutorial 1",
        description="Build an autonomous agent",
        tags=("agent", "ai"),
        privacy_status=VideoPrivacyStatus.UNLISTED,
        video_file_path="video.mp4",
        thumbnail_file_path="",
        created_at="2026-08-31T12:00:00Z",
    )
    persisted = store.create_or_get_draft(draft)
    assert persisted.draft_id == "drf-yt-101"
    assert persisted.status == VideoDraftStatus.DRAFT

    # Duplicate call returns original
    duplicate = store.create_or_get_draft(draft)
    assert duplicate.draft_id == "drf-yt-101"


def test_transition_video_draft_status(store: YouTubeStore) -> None:
    draft = VideoDraft(
        draft_id="drf-yt-102",
        idempotency_key="key-yt-102",
        principal_id="telegram:default:7275339077",
        channel_id="UC-12345",
        title="Podcast Ep 4",
        description="Interview with founder",
        tags=("podcast",),
        privacy_status=VideoPrivacyStatus.PUBLIC,
        video_file_path="podcast.mp4",
        thumbnail_file_path="",
        created_at="2026-08-31T12:00:00Z",
    )
    store.create_or_get_draft(draft)

    uploaded = store.transition_draft_status(
        draft_id="drf-yt-102",
        from_status=VideoDraftStatus.DRAFT,
        to_status=VideoDraftStatus.UPLOADED,
        uploaded_video_id="yt-video-999",
        video_url="https://www.youtube.com/watch?v=yt-video-999",
    )
    assert uploaded.status == VideoDraftStatus.UPLOADED
    assert uploaded.uploaded_video_id == "yt-video-999"
    assert uploaded.video_url == "https://www.youtube.com/watch?v=yt-video-999"
