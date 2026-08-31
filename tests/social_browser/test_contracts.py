from pathlib import Path

import pytest

from tools.social_browser.contracts import RunStatus, create_manifest


def test_manifest_idempotency_is_content_addressed(tmp_path: Path) -> None:
    media = tmp_path / "post.png"
    media.write_bytes(b"image")

    first = create_manifest(
        "facebook-personal", "klaus", "Hello", [media], "friends"
    )
    second = create_manifest(
        "facebook-personal", "klaus", "Hello", [media], "friends"
    )

    assert first.idempotency_key == second.idempotency_key
    assert first.status is RunStatus.REQUESTED


def test_manifest_rejects_changed_media_after_hashing(tmp_path: Path) -> None:
    media = tmp_path / "post.png"
    media.write_bytes(b"image")
    manifest = create_manifest(
        "facebook-personal", "klaus", "Hello", [media], "friends"
    )
    media.write_bytes(b"changed")

    with pytest.raises(ValueError, match="media_digest_mismatch"):
        manifest.verify_media()


def test_manifest_rejects_missing_text_and_media() -> None:
    with pytest.raises(ValueError, match="content_required"):
        create_manifest("facebook-personal", "klaus", "", [], "friends")
