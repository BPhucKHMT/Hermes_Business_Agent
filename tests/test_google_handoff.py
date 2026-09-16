"""Security behavior tests for group-to-DM handoff tokens."""

from pathlib import Path
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src/.hermes/plugins/email-connector")
)

from handoff import (
    HandoffStore,
    build_deep_link,
    handoff_notice,
)


@pytest.fixture
def store(tmp_path):
    return HandoffStore(db_path=tmp_path / "handoffs.db")


def _issue(store, **overrides):
    params = {
        "platform": "telegram",
        "user_id": "12345",
        "workspace": "protein-bar",
        "chat_type": "group",
        "chat_id": "-100999",
        "thread_id": "11",
        "request_text": "gửi mail cho Nam báo giá",
        "ttl_seconds": 900,
    }
    params.update(overrides)
    return store.issue(**params)


def test_issue_and_redeem_happy_path(store):
    token = _issue(store)
    assert token and len(token) >= 32
    record = store.redeem(
        token,
        platform="telegram",
        user_id="12345",
        workspace="protein-bar",
    )
    assert record is not None
    assert record["request_text"] == "gửi mail cho Nam báo giá"
    assert record["workspace"] == "protein-bar"


def test_redeem_is_single_use(store):
    token = _issue(store)
    first = store.redeem(
        token, platform="telegram", user_id="12345", workspace="protein-bar"
    )
    assert first is not None
    second = store.redeem(
        token, platform="telegram", user_id="12345", workspace="protein-bar"
    )
    assert second is None


def test_cross_user_rejected(store):
    token = _issue(store)
    result = store.redeem(
        token, platform="telegram", user_id="99999", workspace="protein-bar"
    )
    assert result is None
    # original user can still redeem after the intruder failed
    ok = store.redeem(
        token, platform="telegram", user_id="12345", workspace="protein-bar"
    )
    assert ok is not None


def test_workspace_mismatch_rejected(store):
    token = _issue(store, workspace="protein-bar")
    result = store.redeem(
        token, platform="telegram", user_id="12345", workspace="titan-ai"
    )
    assert result is None


def test_expired_token_rejected(store):
    token = _issue(store, ttl_seconds=-1)
    result = store.redeem(
        token, platform="telegram", user_id="12345", workspace="protein-bar"
    )
    assert result is None


def test_unknown_token_rejected(store):
    assert (
        store.redeem(
            "not-a-real-token",
            platform="telegram",
            user_id="12345",
            workspace="protein-bar",
        )
        is None
    )


def test_raw_token_not_stored(store, tmp_path):
    token = _issue(store)
    db_bytes = (tmp_path / "handoffs.db").read_bytes()
    assert token.encode() not in db_bytes


def test_active_token_cap_per_user(store):
    for _ in range(6):
        _issue(store)
    with store._connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM google_handoffs WHERE user_id='12345' AND redeemed_at IS NULL"
        ).fetchone()["c"]
    assert count <= 5


def test_deep_link_carries_token_only():
    link = build_deep_link("hermes_bot", "tok123")
    assert link == "https://t.me/hermes_bot?start=tok123"
    assert "mail" not in link and "nam@" not in link


def test_handoff_notice_does_not_leak_account():
    notice = handoff_notice("gửi mail cho Nam", "https://t.me/hermes_bot?start=tok123")
    assert "gmail.com" not in notice
    assert "private chat" in notice


def test_purge_expired_removes_rows(store):
    _issue(store, ttl_seconds=-10)
    _issue(store)
    removed = store.purge_expired()
    assert removed >= 1
    with store._connect() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) AS c FROM google_handoffs"
        ).fetchone()["c"]
    assert remaining == 1
