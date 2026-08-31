from pathlib import Path
import pytest

from tools.tiktok.contracts import TikTokPrivacyLevel
from tools.tiktok.policy import TikTokPolicy, load_tiktok_policy

ROOT = Path(__file__).resolve().parents[2]


def test_load_tiktok_policy() -> None:
    policy_path = ROOT / "src" / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    assert policy.schema_version == 1
    assert policy.default_privacy_level == TikTokPrivacyLevel.SELF_ONLY
    assert policy.max_caption_chars == 2200
    assert ".mp4" in policy.allowed_video_extensions


def test_validate_post_metadata_success() -> None:
    policy_path = ROOT / "src" / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    policy.validate_post_metadata(
        caption="Sample TikTok Post #fyp",
        privacy_level=TikTokPrivacyLevel.PUBLIC_TO_EVERYONE,
    )


def test_validate_post_metadata_caption_too_long() -> None:
    policy_path = ROOT / "src" / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    with pytest.raises(ValueError, match="caption_exceeds_max_chars"):
        policy.validate_post_metadata(caption="A" * 2250)


def test_validate_video_file_extension() -> None:
    policy_path = ROOT / "src" / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    policy.validate_video_file("video.mp4", skip_existence_check=True)

    with pytest.raises(ValueError, match="unsupported_video_extension"):
        policy.validate_video_file("video.avi", skip_existence_check=True)
