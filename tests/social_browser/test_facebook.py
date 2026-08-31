from pathlib import Path

import pytest

from tools.social_browser.contracts import (
    AccessibleNode,
    BrowserObservation,
    RunStatus,
    create_manifest,
)
from tools.social_browser.facebook import FacebookPersonalAdapter
from tools.social_browser.policy import load_policy


ROOT = Path(__file__).resolve().parents[2]


class FakeGateway:
    def __init__(self, account_label: str = "test-account") -> None:
        self.policy = load_policy(ROOT / "src/config/social_browser_policy.json")
        self.platform = "facebook-personal"
        self.account_label = account_label
        self.activated_names = []
        self.filled_text = None
        self.uploaded_path = None
        self.observation_count = 0
        self.fail_observations = 0
        self.published_url = None

    def open(self, url: str):
        return {"url": url}

    def observe(self) -> BrowserObservation:
        self.observation_count += 1
        if self.fail_observations:
            self.fail_observations -= 1
            nodes = ()
        else:
            names = [self.account_label, "Bạn đang nghĩ gì?", "Friends", "Post"]
            if self.filled_text:
                names.append(self.filled_text)
            node_list = [
                AccessibleNode(index + 1, "button", name)
                for index, name in enumerate(names)
            ]
            if self.published_url and self.filled_text:
                node_list.append(
                    AccessibleNode(
                        100,
                        "link",
                        self.filled_text,
                        url=self.published_url,
                    )
                )
            nodes = tuple(node_list)
        return BrowserObservation(
            url="https://www.facebook.com/",
            title="Facebook",
            account_label=self.account_label,
            accessible_nodes=nodes,
        )

    def activate_control(self, node: AccessibleNode):
        self.activated_names.append(node.name)
        return {"activated": True}

    def fill(self, selector: str, text: str):
        self.filled_text = text
        return {"filled": True}

    def upload(self, selector: str, path: Path):
        self.uploaded_path = Path(path)
        return {"uploaded": True}


def manifest(tmp_path: Path, with_media: bool = False):
    media_paths = []
    if with_media:
        media = tmp_path / "post.png"
        media.write_bytes(b"image")
        media_paths.append(media)
    return create_manifest(
        "facebook-personal",
        "test-account",
        "Hermes social browser fixture",
        media_paths,
        "friends",
    )


def test_prepare_stops_before_post(tmp_path: Path) -> None:
    gateway = FakeGateway()
    result = FacebookPersonalAdapter(gateway).prepare(manifest(tmp_path))

    assert result.status is RunStatus.READY_FOR_HUMAN
    assert "Post" not in gateway.activated_names
    assert gateway.filled_text == "Hermes social browser fixture"


def test_prepare_uploads_manifest_media(tmp_path: Path) -> None:
    gateway = FakeGateway()
    post = manifest(tmp_path, with_media=True)

    result = FacebookPersonalAdapter(gateway).prepare(post)

    assert result.status is RunStatus.READY_FOR_HUMAN
    assert gateway.uploaded_path == Path(post.media[0].path)


def test_account_mismatch_stops_before_fill(tmp_path: Path) -> None:
    gateway = FakeGateway(account_label="wrong-account")
    result = FacebookPersonalAdapter(gateway).prepare(manifest(tmp_path))

    assert result.status is RunStatus.BLOCKED_ACCOUNT_MISMATCH
    assert gateway.filled_text is None


def test_ui_drift_retries_once(tmp_path: Path) -> None:
    gateway = FakeGateway()
    gateway.fail_observations = 2
    result = FacebookPersonalAdapter(gateway).prepare(manifest(tmp_path))

    assert result.status is RunStatus.FAILED_UI_DRIFT
    assert gateway.observation_count == 2


def test_verify_published_requires_matching_text_and_permalink(tmp_path: Path) -> None:
    gateway = FakeGateway()
    post = manifest(tmp_path)
    gateway.filled_text = post.text
    gateway.published_url = (
        "https://www.facebook.com/test-account/posts/123456789"
    )

    result = FacebookPersonalAdapter(gateway).verify_published(post)

    assert result == gateway.published_url
