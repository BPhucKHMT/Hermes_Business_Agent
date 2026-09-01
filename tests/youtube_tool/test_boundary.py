from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pytest

from tools.youtube.contracts import VideoPrivacyStatus
from tools.youtube.policy import load_youtube_policy
from tools.youtube.service import YouTubeService
from tools.youtube.store import YouTubeStore
from tools.youtube.youtube_client import YouTubeClient

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def service(tmp_path: Path) -> YouTubeService:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    store = YouTubeStore(tmp_path / "test_youtube_boundary.sqlite3")
    client = YouTubeClient()

    def mock_token_resolver(principal_id: str):
        return {"mock_mode": True}

    return YouTubeService(policy=policy, store=store, youtube_client=client, token_resolver=mock_token_resolver)


def test_empty_title_raises(service: YouTubeService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    with pytest.raises(ValueError, match="title_required"):
        service.create_draft_video(
            caller=caller,
            title="   ",
            description="Test Description",
            video_file_path=str(ROOT / "README.md"),
        )


def test_limit_clamping(service: YouTubeService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    videos = service.list_videos(caller, limit=9999)
    assert isinstance(videos, list)
