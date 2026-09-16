"""Behavioral tests for Google link parsing and Drive/document tools."""

from unittest.mock import patch

from src.tools.composio.docs_tools import (
    composio_docs_get,
    composio_sheets_values,
    composio_slides_page,
)
from src.tools.composio.drive_tools import (
    _run,
    composio_drive_find,
    composio_drive_read_file,
)
from src.tools.composio.glinks import (
    extract_google_links,
    is_google_url,
    parse_google_url,
)


def test_parse_docs_url():
    res = parse_google_url("https://docs.google.com/document/d/DOC123/edit")
    assert res is not None
    assert res.service == "docs"
    assert res.resource_id == "DOC123"
    assert res.kind == "document"


def test_parse_sheets_url_with_gid():
    res = parse_google_url("https://docs.google.com/spreadsheets/d/SHEET9/edit#gid=42")
    assert res is not None
    assert res.service == "sheets"
    assert res.resource_id == "SHEET9"
    assert res.selector == "42"


def test_parse_drive_file_and_folder():
    file_res = parse_google_url(
        "https://drive.google.com/file/d/FILE1/view?usp=sharing"
    )
    assert file_res is not None and file_res.kind == "file"
    folder_res = parse_google_url("https://drive.google.com/drive/folders/FOLD2")
    assert folder_res is not None and folder_res.kind == "folder"


def test_parse_multiclass_folder_path():
    res = parse_google_url("https://drive.google.com/drive/u/0/folders/FOLD3")
    assert res is not None and res.resource_id == "FOLD3"


def test_parse_generic_open_id_with_resourcekey():
    res = parse_google_url("https://drive.google.com/open?id=GEN9&resourcekey=RK1")
    assert res is not None
    assert res.resource_id == "GEN9"
    assert res.resource_key == "RK1"


def test_reject_non_google_and_arbitrary_hosts():
    assert parse_google_url("https://evil.example.com/document/d/X/edit") is None
    assert parse_google_url("https://docs.google.com.evil.com/document/d/X") is None
    assert is_google_url("file:///etc/passwd") is False
    assert is_google_url("not a url") is False


def test_reject_google_host_with_wrong_path():
    assert parse_google_url("https://docs.google.com/random/path") is None


def test_extract_links_from_message_text():
    text = (
        "Xem sheet này nhé https://docs.google.com/spreadsheets/d/S1/edit#gid=3 "
        "và file https://drive.google.com/file/d/F1/view!"
    )
    links = extract_google_links(text)
    assert len(links) == 2
    assert links[0].endswith("#gid=3")


def test_extract_links_none():
    assert extract_google_links("không có link gì cả") == []


ALL_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/presentations",
        "https://mail.google.com/",
    ]
)


def _patch_env(accounts, emails):
    return (
        patch(
            "src.tools.composio.drive_tools.check_connection_status", return_value=True
        ),
        patch(
            "src.tools.composio.drive_tools.has_service_capability", return_value=True
        ),
        patch(
            "src.tools.composio.drive_tools.select_service_account",
            return_value={"account_id": "ca_x", "email": "a@gmail.com", "scopes": []},
        ),
        patch("src.tools.composio.drive_tools.get_composio_client"),
        patch("src.tools.composio.drive_tools.execute_composio_tool"),
        patch(
            "src.tools.composio.drive_tools.get_response_data",
            return_value={"items": []},
        ),
        patch("src.tools.composio.drive_tools.get_response_error", return_value=None),
    )


def test_drive_find_success_shape():
    patches = _patch_env(None, None)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
    ):
        res = composio_drive_find("telegram:default:7", query="name = 'x'")
        assert res["status"] == "success"
        assert res["account_email"] == "a@gmail.com"


def test_drive_find_scope_missing_reports_not_ready():
    with (
        patch(
            "src.tools.composio.drive_tools.check_connection_status", return_value=True
        ),
        patch(
            "src.tools.composio.drive_tools.has_service_capability", return_value=False
        ),
    ):
        res = composio_drive_find("telegram:default:7")
        assert res["status"] == "error"
        assert res["error_code"] == "SCOPE_MISSING"


def test_drive_find_not_connected():
    with patch(
        "src.tools.composio.drive_tools.check_connection_status", return_value=False
    ):
        res = composio_drive_read_file("telegram:default:7", file_id="f1")
        assert res["error_code"] == "NOT_CONNECTED"


def test_drive_ambiguous_account_propagates_selection_code():
    with patch(
        "src.tools.composio.drive_tools.select_service_account",
        side_effect=ValueError("account_selection_required:a@x.com,b@x.com"),
    ):
        res = _run("telegram:default:7", "drive", "GOOGLEDRIVE_FIND_FILE", {}, None)
        assert res["error_code"] == "ACCOUNT_SELECTION_REQUIRED"
        assert "a@x.com,b@x.com" in res["message"]


def test_docs_get_passes_document_id():
    with (
        patch(
            "src.tools.composio.drive_tools.select_service_account",
            return_value={"account_id": "ca_x", "email": "a@gmail.com", "scopes": []},
        ),
        patch("src.tools.composio.drive_tools.get_composio_client"),
        patch("src.tools.composio.drive_tools.execute_composio_tool") as ex,
        patch(
            "src.tools.composio.drive_tools.get_response_data",
            return_value={"documentId": "D1"},
        ),
        patch("src.tools.composio.drive_tools.get_response_error", return_value=None),
    ):
        res = composio_docs_get("telegram:default:7", "D1")
        assert res["status"] == "success"
        kwargs = ex.call_args.kwargs
        assert kwargs["arguments"] == {"id": "D1"}


def test_sheets_values_passes_ranges():
    with (
        patch(
            "src.tools.composio.drive_tools.select_service_account",
            return_value={"account_id": "ca_x", "email": "a@gmail.com", "scopes": []},
        ),
        patch("src.tools.composio.drive_tools.get_composio_client"),
        patch("src.tools.composio.drive_tools.execute_composio_tool") as ex,
        patch("src.tools.composio.drive_tools.get_response_data", return_value={}),
        patch("src.tools.composio.drive_tools.get_response_error", return_value=None),
    ):
        res = composio_sheets_values("telegram:default:7", "S1", ranges=["A1:B2"])
        assert res["status"] == "success"
        assert ex.call_args.kwargs["arguments"]["ranges"] == ["A1:B2"]


def test_slides_page_uses_presentation_and_page_ids():
    with (
        patch(
            "src.tools.composio.drive_tools.select_service_account",
            return_value={"account_id": "ca_x", "email": "a@gmail.com", "scopes": []},
        ),
        patch("src.tools.composio.drive_tools.get_composio_client"),
        patch("src.tools.composio.drive_tools.execute_composio_tool") as ex,
        patch("src.tools.composio.drive_tools.get_response_data", return_value={}),
        patch("src.tools.composio.drive_tools.get_response_error", return_value=None),
    ):
        res = composio_slides_page("telegram:default:7", "P1", "slide_3")
        assert res["status"] == "success"
        args = ex.call_args.kwargs["arguments"]
        assert args["presentationId"] == "P1"
        assert args["pageObjectId"] == "slide_3"
