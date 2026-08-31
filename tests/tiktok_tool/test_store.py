from pathlib import Path
import pytest

from tools.tiktok.contracts import (
    TikTokPostDraft,
    TikTokPostDraftStatus,
    TikTokPrivacyLevel,
)
from tools.tiktok.store import TikTokStore


@pytest.fixture
def store(tmp_path: Path) -> TikTokStore:
    return TikTokStore(tmp_path / "tiktok_test.sqlite3")


def test_upsert_and_get_connection(store: TikTokStore) -> None:
    store.upsert_connection(
        principal_id="telegram:default:7275339077",
        open_id="open-123",
        nickname="TITAN TikTok",
        username="titan_tt",
    )
    conn = store.get_connection("telegram:default:7275339077")
    assert conn is not None
    assert conn["open_id"] == "open-123"
    assert conn["creator_nickname"] == "TITAN TikTok"
    assert conn["status"] == "connected"


def test_create_and_get_draft(store: TikTokStore) -> None:
    draft = TikTokPostDraft(
        draft_id="drf-tt-101",
        idempotency_key="key-tt-101",
        principal_id="telegram:default:7275339077",
        open_id="open-123",
        caption="Check out our new AI Chief of Staff",
        video_file_path="video.mp4",
        privacy_level=TikTokPrivacyLevel.SELF_ONLY,
        disable_comment=False,
        disable_duet=False,
        disable_stitch=False,
        brand_content_toggle=False,
        created_at="2026-08-31T12:00:00Z",
    )
    persisted = store.create_or_get_draft(draft)
    assert persisted.draft_id == "drf-tt-101"
    assert persisted.status == TikTokPostDraftStatus.DRAFT

    # Duplicate call returns original
    duplicate = store.create_or_get_draft(draft)
    assert duplicate.draft_id == "drf-tt-101"


def test_transition_draft_status(store: TikTokStore) -> None:
    draft = TikTokPostDraft(
        draft_id="drf-tt-102",
        idempotency_key="key-tt-102",
        principal_id="telegram:default:7275339077",
        open_id="open-123",
        caption="Behind the scenes",
        video_file_path="bts.mp4",
        privacy_level=TikTokPrivacyLevel.PUBLIC_TO_EVERYONE,
        disable_comment=False,
        disable_duet=False,
        disable_stitch=False,
        brand_content_toggle=False,
        created_at="2026-08-31T12:00:00Z",
    )
    store.create_or_get_draft(draft)

    submitted = store.transition_draft_status(
        draft_id="drf-tt-102",
        from_status=TikTokPostDraftStatus.DRAFT,
        to_status=TikTokPostDraftStatus.SUBMITTED,
        publish_id="pub-tt-999",
    )
    assert submitted.status == TikTokPostDraftStatus.SUBMITTED
    assert submitted.publish_id == "pub-tt-999"
