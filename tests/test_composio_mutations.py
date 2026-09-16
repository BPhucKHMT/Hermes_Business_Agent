"""Behavioral tests for write lifecycle, direct send, and duplicate safety."""

import json
from unittest.mock import patch

import pytest

from src.tools.composio.action_store import ActionStore
from src.tools.composio.actions import (
    classify_send_intent,
    evaluate_direct_send,
    extract_recipient,
    is_model_supplied_approval,
)
import src.tools.composio.mutations as mut
from src.tools.composio.mutations import (
    _begin_write,
    _request_key,
    composio_email_send_direct,
)


def _key(principal, recipient, subject, body):
    return _request_key(
        principal,
        "gmail",
        "send",
        {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "account_email": None,
        },
    )


@pytest.fixture
def tmp_store(tmp_path):
    return ActionStore(db_path=tmp_path / "actions.db")


def test_classify_send_now_vietnamese():
    assert classify_send_intent("gửi luôn mail cho Nam") == "send_now"
    assert classify_send_intent("gửi ngay không cần xem nháp") == "send_now"
    assert classify_send_intent("send it now please") == "send_now"


def test_classify_draft_only_vietnamese():
    assert classify_send_intent("soạn nháp mail cho Nam") == "draft"
    assert classify_send_intent("cho tôi xem nháp trước") == "draft"
    assert classify_send_intent("chưa gửi đâu, soạn trước đi") == "draft"


def test_classify_contradiction_resolves_draft():
    text = "soạn nháp rồi gửi luôn"
    assert classify_send_intent(text) == "draft"


def test_classify_unclear():
    assert classify_send_intent("viết mail cho Nam về cuộc họp") == "unclear"


def test_extract_recipient():
    assert extract_recipient("gửi cho nam@proteinbar.vn nhé") == "nam@proteinbar.vn"
    assert extract_recipient("không có email") is None


def test_evaluate_direct_send_missing_fields():
    decision = evaluate_direct_send(
        request_text="gửi luôn", recipient=None, subject=None, body=None
    )
    assert decision.intent == "send_now"
    assert set(decision.missing) == {"recipient", "subject", "body"}


def test_evaluate_direct_send_complete():
    decision = evaluate_direct_send(
        request_text="gửi luôn",
        recipient="nam@proteinbar.vn",
        subject="Họp 3h",
        body="Chào Nam",
    )
    assert decision.intent == "send_now"
    assert decision.missing == ()
    assert decision.recipients == ("nam@proteinbar.vn",)


def test_model_approval_fields_rejected():
    assert is_model_supplied_approval({"approved": True}) is True
    assert is_model_supplied_approval({"skip_approval": "yes"}) is True
    assert is_model_supplied_approval({"recipient": "x@y.com"}) is False


def test_action_store_begin_and_duplicate(tmp_store):
    params = {"recipient": "a@b.com"}
    first = tmp_store.begin(
        request_key="k1",
        principal_id="telegram:default:1",
        service="gmail",
        action="send",
        params=params,
    )
    assert first["state"] == "pending"
    second = tmp_store.begin(
        request_key="k1",
        principal_id="telegram:default:1",
        service="gmail",
        action="send",
        params=params,
    )
    assert second["operation_id"] == first["operation_id"]
    assert second["state"] == "pending"


def test_action_store_lifecycle(tmp_store):
    record = tmp_store.begin(
        request_key="k2",
        principal_id="p",
        service="drive",
        action="upload",
        params={},
    )
    op_id = record["operation_id"]
    tmp_store.mark_executing(op_id)
    assert tmp_store.get(op_id)["state"] == "executing"
    tmp_store.mark_verified(op_id, {"message_id": "m1"})
    row = tmp_store.get(op_id)
    assert row["state"] == "verified"
    assert json.loads(row["evidence_json"])["message_id"] == "m1"


def test_action_store_unknown_outcome(tmp_store):
    record = tmp_store.begin(
        request_key="k3",
        principal_id="p",
        service="gmail",
        action="send",
        params={},
    )
    tmp_store.mark_unknown(record["operation_id"], "timeout after commit")
    row = tmp_store.get(record["operation_id"])
    assert row["state"] == "unknown"
    assert "timeout" in row["error_code"]


def test_begin_write_duplicate_returns_existing(tmp_store, monkeypatch):
    monkeypatch.setattr(mut, "_STORE", tmp_store)
    params = {"recipient": "a@b.com", "subject": "s", "body": "b"}
    first = _begin_write("telegram:default:1", "gmail", "send", params)
    second = _begin_write("telegram:default:1", "gmail", "send", params)
    assert second["operation_id"] == first["operation_id"]
    assert second["state"] == "pending"


def test_send_direct_draft_intent_never_sends():
    with patch("src.tools.composio.mutations.composio_mail_send") as send:
        res = composio_email_send_direct(
            "telegram:default:1",
            request_text="soạn nháp mail cho Nam",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
        assert res["status"] == "error"
        assert res["error_code"] == "DRAFT_ONLY"
        send.assert_not_called()


def test_send_direct_unclear_intent_never_sends():
    with patch("src.tools.composio.mutations.composio_mail_send") as send:
        res = composio_email_send_direct(
            "telegram:default:1",
            request_text="viết mail cho Nam",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
        assert res["error_code"] == "INTENT_UNCLEAR"
        send.assert_not_called()


def test_send_direct_missing_fields_never_sends():
    with patch("src.tools.composio.mutations.composio_mail_send") as send:
        res = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="",
            subject="S",
            body="B",
        )
        assert res["error_code"] == "MISSING_FIELDS"
        send.assert_not_called()


def test_send_direct_success_records_evidence(tmp_store, monkeypatch):
    monkeypatch.setattr(mut, "_STORE", tmp_store)
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={
            "status": "success",
            "active_mailbox": "a@x.com",
            "data": {"message_id": "msg_9"},
        },
    ) as send:
        res = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn cho Nam",
            recipient="nam@x.com",
            subject="Họp 3h",
            body="Chào Nam",
        )
        assert res["status"] == "success"
        assert res["message_id"] == "msg_9"
        send.assert_called_once()
        row = tmp_store.get(res["operation_id"])
        assert row["state"] == "verified"
        assert json.loads(row["evidence_json"])["message_id"] == "msg_9"


def test_send_direct_duplicate_request_blocked(tmp_store, monkeypatch):
    monkeypatch.setattr(mut, "_STORE", tmp_store)
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={"status": "success", "data": {"message_id": "m1"}},
    ):
        first = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
        assert first["status"] == "success"
        assert first["message_id"] == "m1"
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={"status": "success", "data": {"message_id": "m2"}},
    ) as send:
        second = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
        assert second["status"] == "error"
        assert second["error_code"] == "DUPLICATE_REQUEST"
        send.assert_not_called()


def test_send_direct_distinct_request_not_deduped(tmp_store, monkeypatch):
    monkeypatch.setattr(mut, "_STORE", tmp_store)
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={"status": "success", "data": {"message_id": "m1"}},
    ):
        composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={"status": "success", "data": {"message_id": "m2"}},
    ):
        second = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="nam@x.com",
            subject="S khác",
            body="B",
        )
        assert second["status"] == "success"
        assert second["message_id"] == "m2"


def test_send_direct_provider_failure_marks_failed(tmp_store, monkeypatch):
    monkeypatch.setattr(mut, "_STORE", tmp_store)
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={
            "status": "error",
            "error_code": "PROVIDER_ERROR",
            "message": "boom",
        },
    ):
        res = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
        assert res["status"] == "error"
        record = tmp_store.get_by_request_key(
            _key("telegram:default:1", "nam@x.com", "S", "B")
        )
        assert record is not None
        assert record["state"] == "failed"


def test_send_direct_success_without_message_id_is_unknown(tmp_store, monkeypatch):
    monkeypatch.setattr(mut, "_STORE", tmp_store)
    with patch(
        "src.tools.composio.mutations.composio_mail_send",
        return_value={"status": "success", "data": {}},
    ):
        res = composio_email_send_direct(
            "telegram:default:1",
            request_text="gửi luôn",
            recipient="nam@x.com",
            subject="S",
            body="B",
        )
        assert res["status"] == "error"
        assert res["error_code"] == "UNKNOWN_OUTCOME"
        row = tmp_store.get(res["operation_id"])
        assert row["state"] == "unknown"
