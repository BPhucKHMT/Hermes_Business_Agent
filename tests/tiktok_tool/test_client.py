from tools.tiktok.contracts import (
    TikTokPostDraft,
    TikTokPrivacyLevel,
    TikTokPublishStatus,
)
from tools.tiktok.tiktok_client import TikTokClient


def test_tiktok_client_get_creator_info_mock() -> None:
    client = TikTokClient()
    token_data = {
        "mock_mode": True,
        "mock_creator": {
            "open_id": "open-tt-999",
            "creator_nickname": "TITAN Official",
            "creator_username": "titan_official",
            "creator_avatar_url": "https://avatar.url/1.jpg",
            "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
            "max_video_post_duration_sec": 600,
        },
    }
    info = client.get_creator_info(token_data)
    assert info.open_id == "open-tt-999"
    assert info.creator_username == "titan_official"


def test_tiktok_client_init_and_fetch_status_mock() -> None:
    client = TikTokClient()
    draft = TikTokPostDraft(
        draft_id="drf-tt-1",
        idempotency_key="key-tt-1",
        principal_id="telegram:default:123",
        open_id="open-tt-999",
        caption="Launch Video",
        video_file_path="launch.mp4",
        privacy_level=TikTokPrivacyLevel.SELF_ONLY,
        disable_comment=False,
        disable_duet=False,
        disable_stitch=False,
        brand_content_toggle=False,
        created_at="2026-08-31T12:00:00Z",
    )
    publish_id = client.init_video_publish({"mock_mode": True}, draft)
    assert publish_id.startswith("pub-tt-")

    status_res = client.fetch_publish_status({"mock_mode": True}, publish_id)
    assert status_res.status == TikTokPublishStatus.SUCCESS
    assert status_res.post_id is not None
