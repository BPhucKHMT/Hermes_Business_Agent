"""Behavioral tests for connector workspace tool handlers."""

import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/.hermes/plugins/email-connector"))

from caller import DmOnlyError  # noqa: E402 -- plugin path bootstrap
from workspace_schemas import (  # noqa: E402 -- plugin path bootstrap
    GOOGLE_DRIVE_FIND_SCHEMA,
    GOOGLE_FILE_READ_SCHEMA,
    WORKSPACE_TOOL_SCHEMAS,
)
from workspace_tools import (  # noqa: E402 -- plugin path bootstrap
    handle_google_doc_read,
    handle_google_drive_find,
    handle_google_file_read,
    handle_google_sheet_read,
    handle_google_slide_read,
)


class FakeCaller:
    principal_id = "telegram:default:12345"
    user_id = "12345"
    chat_id = "12345"
    chat_type = "dm"


class FakeRegistry:
    def resolve_dm_tool(self, task_id: str, session_id: str):
        return FakeCaller()


REGISTRY = FakeRegistry()


def test_workspace_schemas_complete():
    names = {s["name"] for s in WORKSPACE_TOOL_SCHEMAS}
    assert names == {
        "google_drive_find",
        "google_file_read",
        "google_doc_read",
        "google_sheet_read",
        "google_slide_read",
    }
    assert GOOGLE_DRIVE_FIND_SCHEMA["parameters"]["required"] == ["query"]
    assert GOOGLE_FILE_READ_SCHEMA["parameters"]["required"] == ["url_or_id"]


def test_drive_find_success():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "success",
            "account_email": "a@gmail.com",
            "data": {"files": [{"id": "f1", "name": "BaoGia"}]},
        }
        raw = handle_google_drive_find(
            {"query": "báo giá"},
            client=object(),
            registry=REGISTRY,
            session_id="s1",
        )
        res = json.loads(raw)
        assert res["ok"] is True
        assert res["result"]["files"][0]["name"] == "BaoGia"
        assert call.call_args.args[0] == "composio_drive_find"
        assert call.call_args.args[1] == "telegram:default:12345"


def test_drive_find_requires_query():
    raw = handle_google_drive_find(
        {"query": " "}, client=object(), registry=REGISTRY, session_id="s1"
    )
    res = json.loads(raw)
    assert res["ok"] is False
    assert res["error"]["code"] == "query_required"


def test_drive_find_maps_error_code():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "error",
            "error_code": "SCOPE_MISSING",
            "message": "cần cấp quyền",
        }
        raw = handle_google_drive_find(
            {"query": "x"}, client=object(), registry=REGISTRY, session_id="s1"
        )
        res = json.loads(raw)
        assert res["ok"] is False
        assert res["error"]["code"] == "scope_missing"


def test_file_read_routes_docs_url():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "success",
            "account_email": "a@x.com",
            "data": {},
        }
        raw = handle_google_file_read(
            {"url_or_id": "https://docs.google.com/document/d/DOC77/edit"},
            client=object(),
            registry=REGISTRY,
            session_id="s1",
        )
        res = json.loads(raw)
        assert res["ok"] is True
        assert call.call_args.args[0] == "composio_docs_get"
        assert call.call_args.args[2]["document_id"] == "DOC77"


def test_file_read_routes_drive_url():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "success",
            "account_email": "a@x.com",
            "data": {},
        }
        raw = handle_google_file_read(
            {"url_or_id": "https://drive.google.com/file/d/FILE5/view"},
            client=object(),
            registry=REGISTRY,
            session_id="s1",
        )
        res = json.loads(raw)
        assert res["ok"] is True
        assert call.call_args.args[0] == "composio_drive_read_file"
        assert call.call_args.args[2]["file_id"] == "FILE5"


def test_file_read_rejects_non_google_url():
    raw = handle_google_file_read(
        {"url_or_id": "https://evil.example.com/document/d/X"},
        client=object(),
        registry=REGISTRY,
        session_id="s1",
    )
    res = json.loads(raw)
    assert res["ok"] is False
    assert res["error"]["code"] == "unsupported_url"


def test_file_read_raw_id_uses_drive():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "success",
            "account_email": "a@x.com",
            "data": {},
        }
        raw = handle_google_file_read(
            {"url_or_id": "RAWID1"},
            client=object(),
            registry=REGISTRY,
            session_id="s1",
        )
        res = json.loads(raw)
        assert res["ok"] is True
        assert call.call_args.args[2]["file_id"] == "RAWID1"


def test_sheet_read_passes_ranges():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "success",
            "account_email": "a@x.com",
            "data": {},
        }
        raw = handle_google_sheet_read(
            {"spreadsheet_id": "S1", "ranges": ["Tab1!A1:B5"]},
            client=object(),
            registry=REGISTRY,
            session_id="s1",
        )
        res = json.loads(raw)
        assert res["ok"] is True
        assert call.call_args.args[2]["ranges"] == ["Tab1!A1:B5"]


def test_slide_read_single_page():
    with patch("tools.composio.bridge.call_google") as call:
        call.return_value = {
            "status": "success",
            "account_email": "a@x.com",
            "data": {},
        }
        raw = handle_google_slide_read(
            {"presentation_id": "P1", "page_object_id": "slide_2"},
            client=object(),
            registry=REGISTRY,
            session_id="s1",
        )
        res = json.loads(raw)
        assert res["ok"] is True
        assert call.call_args.args[0] == "composio_slides_page"


def test_doc_read_missing_id_errors():
    raw = handle_google_doc_read(
        {}, client=object(), registry=REGISTRY, session_id="s1"
    )
    res = json.loads(raw)
    assert res["ok"] is False
    assert res["error"]["code"] == "document_id_required"


def test_group_caller_cannot_read_private_files():
    class GroupRegistry(FakeRegistry):
        def resolve_dm_tool(self, task_id: str, session_id: str):
            raise DmOnlyError("dm required")

    raw = handle_google_drive_find(
        {"query": "x"},
        client=object(),
        registry=GroupRegistry(),
        session_id="s1",
    )
    res = json.loads(raw)
    assert res["ok"] is False
