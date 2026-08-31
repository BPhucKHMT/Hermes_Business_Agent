from pathlib import Path

import pytest

from tools.social_browser.contracts import RunStatus, create_manifest
from tools.social_browser.store import SocialBrowserStore


@pytest.fixture
def store(tmp_path: Path) -> SocialBrowserStore:
    return SocialBrowserStore(tmp_path / "social.sqlite3")


@pytest.fixture
def manifest():
    return create_manifest(
        "facebook-personal", "klaus", "Hello Facebook", [], "friends"
    )


def test_duplicate_manifest_returns_existing_run(store, manifest) -> None:
    first = store.create_or_get(manifest)
    duplicate = create_manifest(
        "facebook-personal", "klaus", "Hello Facebook", [], "friends"
    )
    second = store.create_or_get(duplicate)

    assert first.run_id == second.run_id
    assert first.idempotency_key == second.idempotency_key


def test_published_requires_verified_identifier(store, manifest) -> None:
    store.create_or_get(manifest)
    store.transition(manifest.run_id, RunStatus.REQUESTED, RunStatus.PREPARING)
    store.transition(
        manifest.run_id, RunStatus.PREPARING, RunStatus.READY_FOR_HUMAN
    )

    with pytest.raises(ValueError, match="verified_post_id_required"):
        store.transition(
            manifest.run_id,
            RunStatus.READY_FOR_HUMAN,
            RunStatus.PUBLISHED,
        )


def test_compare_and_set_rejects_stale_transition(store, manifest) -> None:
    store.create_or_get(manifest)

    with pytest.raises(ValueError, match="unexpected_run_status"):
        store.transition(
            manifest.run_id,
            RunStatus.PREPARING,
            RunStatus.READY_FOR_HUMAN,
        )


def test_verified_identifier_marks_published(store, manifest) -> None:
    store.create_or_get(manifest)
    store.transition(manifest.run_id, RunStatus.REQUESTED, RunStatus.PREPARING)
    store.transition(
        manifest.run_id, RunStatus.PREPARING, RunStatus.READY_FOR_HUMAN
    )
    published = store.transition(
        manifest.run_id,
        RunStatus.READY_FOR_HUMAN,
        RunStatus.PUBLISHED,
        verified_post_id="https://www.facebook.com/test/posts/123",
    )

    assert published.status is RunStatus.PUBLISHED
    assert published.verified_post_id.endswith("/123")
