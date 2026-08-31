from pathlib import Path
from types import SimpleNamespace
import pytest

from tools.tiktok.contracts import TikTokPostDraftStatus, TikTokPublishStatus
from tools.tiktok.policy import load_tiktok_policy
from tools.tiktok.service import TikTokService
from tools.tiktok.store import TikTokStore
from tools.tiktok.tiktok_client import TikTokClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def service(tmp_path: Path) -> TikTokService:
    policy_path = ROOT / "src" / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    store = TikTokStore(tmp_path / "test_tiktok.sqlite3")
    client = TikTokClient()
    return TikTokService(policy=policy, store=store, tiktok_client=client)


def test_tiktok_service_creator_status(service: TikTokService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    res = service.get_creator_status(caller)
    assert res["ok"] is True
    assert res["result"]["creator_username"] == "titan_ai_shorts"


def test_tiktok_service_create_and_publish_draft(service: TikTokService) -> None:
    caller = SimpleNamespace(principal_id="telegram:default:7275339077")
    draft = service.create_draft_post(
        caller=caller,
        caption="Behind the scenes with our AI agents #tech #ai",
        video_file_path="bts.mp4",
        privacy_level="SELF_ONLY",
    )
    assert draft.status == TikTokPostDraftStatus.DRAFT
    assert "Behind the scenes" in draft.caption

    pub_res = service.publish_draft_post(caller=caller, draft_id=draft.draft_id)
    assert pub_res["status"] == "submitted"
    assert "publish_id" in pub_res

    status_res = service.get_post_status(caller=caller, publish_id=pub_res["publish_id"])
    assert status_res.status == TikTokPublishStatus.SUCCESS
