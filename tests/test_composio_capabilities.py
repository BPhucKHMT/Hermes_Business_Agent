"""Behavioral tests for capability-aware connection and account selection."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.composio.auth import (
    get_account_service_states,
    has_service_capability,
    select_service_account,
)
from src.tools.composio.capabilities import (
    SERVICES,
    account_toolkit,
    assess_service,
    extract_scopes,
)

ALL_SCOPES = frozenset(
    {
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/presentations",
    }
)


def _account(
    account_id: str,
    slug: str = "googlesuper",
    scopes: frozenset[str] | None = None,
    status: str = "ACTIVE",
):
    return {
        "id": account_id,
        "status": status,
        "toolkit": {"slug": slug},
        "data": {"scope": " ".join(sorted(ALL_SCOPES if scopes is None else scopes))},
    }


def test_assess_ready_for_all_services():
    account = _account("ca_full")
    for service in SERVICES:
        result = assess_service(account, service)
        assert result["state"] == "ready", result


def test_assess_needs_scope_when_drive_scope_missing():
    account = _account("ca_mail_only", scopes=frozenset({"https://mail.google.com/"}))
    assert assess_service(account, "gmail")["state"] == "ready"
    assert assess_service(account, "drive")["state"] == "needs_scope"
    assert assess_service(account, "docs")["state"] == "needs_scope"


def test_assess_unknown_scope_reports_needs_scope_not_ready():
    account = _account("ca_opaque", scopes=frozenset())
    assert assess_service(account, "drive")["state"] == "needs_scope"
    assert assess_service(account, "drive")["reason"] == "scope_unknown"


def test_assess_toolkit_mismatch_is_unsupported():
    account = _account("ca_gmail", slug="gmail")
    assert assess_service(account, "drive")["state"] == "unsupported"
    assert assess_service(account, "gmail")["state"] == "ready"


def test_extract_scopes_handles_object_and_dict():
    obj = MagicMock()
    obj.data = {"scope": "https://www.googleapis.com/auth/drive"}
    assert extract_scopes(obj) == frozenset({"https://www.googleapis.com/auth/drive"})
    assert extract_scopes(_account("x")) == ALL_SCOPES


def test_account_toolkit_normalizes_calendar_spelling():
    assert account_toolkit({"toolkit": {"slug": "google_calendar"}}) == "googlecalendar"
    assert account_toolkit(_account("x", slug="googlesuper")) == "googlesuper"


def _patch_auth(monkeypatch, accounts, emails):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test_key_123")
    monkeypatch.patch = None
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
    ):
        yield


def test_select_service_account_explicit_email(monkeypatch):
    accounts = [_account("ca_a"), _account("ca_b")]
    emails = {"ca_a": "a@gmail.com", "ca_b": "b@gmail.com"}
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
    ):
        result = select_service_account(7275339077, "drive", "b@gmail.com")
        assert result["account_id"] == "ca_b"
        assert result["email"] == "b@gmail.com"


def test_select_service_account_single_ready_resolves_without_question(monkeypatch):
    accounts = [_account("ca_a")]
    emails = {"ca_a": "solo@gmail.com"}
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
    ):
        result = select_service_account(7275339077, "sheets")
        assert result["account_id"] == "ca_a"


def test_select_service_account_ambiguous_requires_selection(monkeypatch):
    accounts = [_account("ca_a"), _account("ca_b")]
    emails = {"ca_a": "a@gmail.com", "ca_b": "b@gmail.com"}
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
        pytest.raises(
            ValueError, match="account_selection_required:a@gmail.com,b@gmail.com"
        ),
    ):
        select_service_account(7275339077, "drive")


def test_select_service_account_relogin_supersedes_old_session(monkeypatch):
    """Same mailbox connected twice: the newest grant wins, not the stale one."""
    old = _account("ca_old")
    old["created_at"] = "2026-09-16T07:34:02.225Z"
    new = _account("ca_new")
    new["created_at"] = "2026-09-16T07:41:05.505Z"
    emails = {"ca_old": "dup@gmail.com", "ca_new": "dup@gmail.com"}
    with (
        patch(
            "src.tools.composio.auth._connected_accounts",
            return_value=[old, new],
        ),
        patch(
            "src.tools.composio.auth.get_user_emails",
            return_value=emails,
        ),
    ):
        result = select_service_account(7275339077, "drive")
        assert result["account_id"] == "ca_new"


def test_select_service_account_explicit_email_picks_newest_duplicate(
    monkeypatch,
):
    old = _account("ca_old")
    old["created_at"] = "2026-09-16T07:34:02.225Z"
    new = _account("ca_new")
    new["created_at"] = "2026-09-16T07:41:05.505Z"
    emails = {"ca_old": "dup@gmail.com", "ca_new": "dup@gmail.com"}
    with (
        patch(
            "src.tools.composio.auth._connected_accounts",
            return_value=[new, old],
        ),
        patch(
            "src.tools.composio.auth.get_user_emails",
            return_value=emails,
        ),
    ):
        result = select_service_account(7275339077, "gmail", "dup@gmail.com")
        assert result["account_id"] == "ca_new"


def test_select_service_account_no_ready_account_raises_service_not_ready(monkeypatch):
    accounts = [_account("ca_a", scopes=frozenset({"https://mail.google.com/"}))]
    emails = {"ca_a": "a@gmail.com"}
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
        pytest.raises(ValueError, match="service_not_ready:drive"),
    ):
        select_service_account(7275339077, "drive")


def test_select_service_account_unknown_email_rejected(monkeypatch):
    accounts = [_account("ca_a")]
    emails = {"ca_a": "a@gmail.com"}
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
        pytest.raises(ValueError, match="account_target_not_found:other@gmail.com"),
    ):
        select_service_account(7275339077, "drive", "other@gmail.com")


def test_select_service_account_duplicate_connections_dedupe(monkeypatch):
    accounts = [_account("ca_a"), _account("ca_a2")]
    emails = {"ca_a": "same@gmail.com", "ca_a2": "same@gmail.com"}
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=accounts),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
    ):
        result = select_service_account(7275339077, "docs")
        assert result["account_id"] == "ca_a"


def test_service_states_ready_and_needs_scope_split(monkeypatch):
    full = _account("ca_full")
    mail_only = _account(
        "ca_mail", slug="gmail", scopes=frozenset({"https://mail.google.com/"})
    )
    emails = {"ca_full": "full@gmail.com", "ca_mail": "mail@gmail.com"}
    with (
        patch(
            "src.tools.composio.auth._connected_accounts",
            return_value=[full, mail_only],
        ),
        patch("src.tools.composio.auth.get_user_emails", return_value=emails),
    ):
        states = get_account_service_states(7275339077)
        assert states["gmail"]["state"] == "ready"
        assert states["drive"]["state"] == "ready"
        assert states["sheets"]["state"] == "ready"


def test_service_states_not_connected_when_no_accounts(monkeypatch):
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=[]),
        patch("src.tools.composio.auth.get_user_emails", return_value={}),
    ):
        states = get_account_service_states(7275339077)
        assert states["drive"]["state"] == "not_connected"


def test_has_service_capability_false_on_expired(monkeypatch):
    expired = _account("ca_x", status="EXPIRED")
    with (
        patch("src.tools.composio.auth._connected_accounts", return_value=[expired]),
        patch("src.tools.composio.auth.get_user_emails", return_value={}),
    ):
        assert has_service_capability(7275339077, "gmail") is False


def test_has_service_capability_true_when_scoped(monkeypatch):
    with (
        patch(
            "src.tools.composio.auth._connected_accounts",
            return_value=[_account("ca_x")],
        ),
        patch("src.tools.composio.auth.get_user_emails", return_value={}),
    ):
        assert has_service_capability(7275339077, "slides") is True
