from tools.tiktok.contracts import (
    TikTokCreatorInfo,
    TikTokPostDraft,
    TikTokPostDraftStatus,
    TikTokPostResult,
    TikTokPrivacyLevel,
    TikTokPublishStatus,
    compute_tiktok_draft_idempotency_key,
)


def test_compute_tiktok_draft_idempotency_key() -> None:
    key1 = compute_tiktok_draft_idempotency_key(
        principal_id="telegram:default:123",
        caption="New TikTok Video #ai #trending",
        video_file_path="C:/videos/tiktok1.mp4",
        privacy_level="PUBLIC_TO_EVERYONE",
    )
    key2 = compute_tiktok_draft_idempotency_key(
        principal_id="telegram:default:123",
        caption="New TikTok Video #ai #trending",
        video_file_path="C:/videos/tiktok1.mp4",
        privacy_level="PUBLIC_TO_EVERYONE",
    )
    assert key1 == key2
    assert len(key1) == 64


def test_tiktok_creator_info_structure() -> None:
    info = TikTokCreatorInfo(
        open_id="open-12345",
        creator_nickname="TITAN SMM",
        creator_username="titan_smm",
        creator_avatar_url="https://avatar.url",
        privacy_level_options=("PUBLIC_TO_EVERYONE", "SELF_ONLY"),
        comment_disabled=False,
        duet_disabled=False,
        stitch_disabled=False,
        max_video_post_duration_sec=600,
    )
    assert info.creator_username == "titan_smm"
    assert info.status == "connected"


def test_tiktok_post_draft_structure() -> None:
    draft = TikTokPostDraft(
        draft_id="drf-tt-001",
        idempotency_key="key-001",
        principal_id="telegram:default:123",
        open_id="open-12345",
        caption="Viral hook #viral",
        video_file_path="viral.mp4",
        privacy_level=TikTokPrivacyLevel.SELF_ONLY,
        disable_comment=False,
        disable_duet=False,
        disable_stitch=False,
        brand_content_toggle=False,
        created_at="2026-08-31T12:00:00Z",
        status=TikTokPostDraftStatus.DRAFT,
    )
    assert draft.status == TikTokPostDraftStatus.DRAFT
    assert draft.privacy_level == TikTokPrivacyLevel.SELF_ONLY
