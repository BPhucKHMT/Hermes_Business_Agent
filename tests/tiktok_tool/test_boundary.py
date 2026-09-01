from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pytest

from tools.tiktok.policy import load_tiktok_policy
from tools.tiktok.service import TikTokService
from tools.tiktok.store import TikTokStore
from tools.tiktok.tiktok_client import TikTokClient

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def service(tmp_path: Path) -> TikTokService:
    policy_path = ROOT / "src" / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    store = TikTokStore(tmp_path / "test_tiktok_boundary.sqlite3")
    client = TikTokClient()

    def mock_token_resolver(principal_id: str):
        return {"mock_mode": True}

    return TikTokService(policy=policy, store=store, tiktok_client=client, token_resolver=mock_token_resolver)


def test_unsupported_video_extension_raises(service: TikTokService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    with pytest.raises(ValueError, match="unsupported_video_extension"):
        service.create_draft_post(
            caller=caller,
            caption="Test Caption #fyp",
            video_file_path="malicious_file.exe",
        )


def test_oversized_caption_raises(service: TikTokService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:12345")
    with pytest.raises(ValueError, match="caption_exceeds_max_chars"):
        service.create_draft_post(
            caller=caller,
            caption="A" * 3000,
            video_file_path="video.mp4",
        )
