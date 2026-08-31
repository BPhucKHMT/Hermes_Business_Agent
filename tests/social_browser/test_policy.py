from pathlib import Path

import pytest

from tools.social_browser.policy import load_policy


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "src" / "config" / "social_browser_policy.json"


def test_policy_denies_terminal_and_raw_operations() -> None:
    policy = load_policy(POLICY_PATH)

    for action in (
        "publish",
        "post",
        "schedule",
        "send",
        "raw_cdp",
        "javascript",
        "coordinate_click",
        "shell",
    ):
        assert not policy.allows_operation("facebook-personal", action)


def test_policy_accepts_only_facebook_origin() -> None:
    policy = load_policy(POLICY_PATH)

    policy.require_origin("facebook-personal", "https://www.facebook.com/")
    with pytest.raises(PermissionError, match="origin_not_allowed"):
        policy.require_origin("facebook-personal", "https://example.com/")


def test_policy_disables_telemetry_and_cloud() -> None:
    policy = load_policy(POLICY_PATH)

    assert not policy.telemetry
    assert not policy.cloud
