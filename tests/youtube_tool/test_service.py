from pathlib import Path
from types import SimpleNamespace
import pytest

from tools.youtube.contracts import VideoDraftStatus, VideoPrivacyStatus
from tools.youtube.policy import load_youtube_policy
from tools.youtube.service import YouTubeService
from tools.youtube.store import YouTubeStore
from tools.youtube.youtube_client import YouTubeClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def service(tmp_path: Path) -> YouTubeService:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    store = YouTubeStore(tmp_path / "test_youtube.sqlite3")
    client = YouTubeClient()
    return YouTubeService(policy=policy, store=store, youtube_client=client)


def test_youtube_service_channel_status(service: YouTubeService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    res = service.get_channel_status(caller)
    assert res["ok"] is True
    assert res["result"]["channel_id"] == "UC-mock-channel-123"


def test_youtube_service_create_and_upload_draft(service: YouTubeService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    draft = service.create_draft_video(
        caller=caller,
        title="AI Marketing Masterclass",
        video_file_path="masterclass.mp4",
        description="Learn how to deploy marketing agents",
        tags=("marketing", "ai"),
        privacy_status="unlisted",
    )
    assert draft.status == VideoDraftStatus.DRAFT
    assert draft.title == "AI Marketing Masterclass"

    uploaded = service.upload_draft_video(caller=caller, draft_id=draft.draft_id)
    assert uploaded.title == "AI Marketing Masterclass"
    assert uploaded.url.startswith("https://www.youtube.com/watch?v=")

    persisted = service.store.get_draft(draft.draft_id)
    assert persisted is not None
    assert persisted.status == VideoDraftStatus.UPLOADED
    assert persisted.uploaded_video_id == uploaded.video_id
