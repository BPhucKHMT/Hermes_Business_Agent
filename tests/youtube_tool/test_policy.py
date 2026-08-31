from pathlib import Path
import pytest

from tools.youtube.contracts import VideoPrivacyStatus
from tools.youtube.policy import YouTubePolicy, load_youtube_policy

ROOT = Path(__file__).resolve().parents[2]


def test_load_youtube_policy() -> None:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    assert policy.schema_version == 1
    assert policy.default_privacy_status == VideoPrivacyStatus.UNLISTED
    assert policy.max_title_chars == 100
    assert policy.max_description_chars == 5000
    assert policy.max_tags_count == 30
    assert ".mp4" in policy.allowed_video_extensions


def test_validate_metadata_success() -> None:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    policy.validate_metadata(
        title="Weekly Sprint Demo",
        description="Demoing new AI tools",
        tags=("demo", "sprint"),
        privacy_status=VideoPrivacyStatus.PRIVATE,
    )


def test_validate_metadata_missing_title() -> None:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    with pytest.raises(ValueError, match="title_required"):
        policy.validate_metadata(title="")


def test_validate_metadata_title_too_long() -> None:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    with pytest.raises(ValueError, match="title_exceeds_max_chars"):
        policy.validate_metadata(title="A" * 105)


def test_validate_video_extension() -> None:
    policy_path = ROOT / "src" / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    policy.validate_video_file("test.mp4", skip_existence_check=True)

    with pytest.raises(ValueError, match="unsupported_video_extension"):
        policy.validate_video_file("test.exe", skip_existence_check=True)
