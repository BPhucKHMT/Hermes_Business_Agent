"""Composio Docs/Sheets/Slides read tools with capability enforcement."""

from __future__ import annotations

from typing import Any

from .drive_tools import _run

_READ_ACTIONS = {
    # service -> (tool_slug, required_argument_builder)
    "docs_get": ("GOOGLEDOCS_GET_DOCUMENT_BY_ID", lambda a: {"id": a["resource_id"]}),
    "docs_search": ("GOOGLEDOCS_SEARCH_DOCUMENTS", lambda a: {"query": a["query"]}),
    "sheets_info": (
        "GOOGLESHEETS_GET_SPREADSHEET_INFO",
        lambda a: {"spreadsheet_id": a["resource_id"]},
    ),
    "sheets_names": (
        "GOOGLESHEETS_GET_SHEET_NAMES",
        lambda a: {"spreadsheet_id": a["resource_id"]},
    ),
    "sheets_values": ("GOOGLESHEETS_BATCH_GET", lambda a: a["flat"]),
    "slides_get": (
        "GOOGLESLIDES_PRESENTATIONS_GET",
        lambda a: {"presentationId": a["resource_id"]},
    ),
    "slides_page": (
        "GOOGLESLIDES_PRESENTATIONS_PAGES_GET",
        lambda a: a["arguments"],
    ),
}


def composio_docs_get(
    principal_id: int | str,
    document_id: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Read a Google Docs document (all tabs) via authenticated API."""
    slug, build = _READ_ACTIONS["docs_get"]
    return _run(
        principal_id, "docs", slug, build({"resource_id": document_id}), account_email
    )


def composio_docs_search(
    principal_id: int | str,
    query: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Search Google Docs documents."""
    slug, build = _READ_ACTIONS["docs_search"]
    return _run(principal_id, "docs", slug, build({"query": query}), account_email)


def composio_sheets_info(
    principal_id: int | str,
    spreadsheet_id: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Read spreadsheet metadata including sheet/tab list."""
    slug, build = _READ_ACTIONS["sheets_info"]
    return _run(
        principal_id,
        "sheets",
        slug,
        build({"resource_id": spreadsheet_id}),
        account_email,
    )


def composio_sheets_values(
    principal_id: int | str,
    spreadsheet_id: str,
    ranges: list[str] | None = None,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Read cell values/ranges from a spreadsheet."""
    slug, build = _READ_ACTIONS["sheets_values"]
    arguments: dict[str, Any] = {"spreadsheet_id": spreadsheet_id}
    if ranges:
        arguments["ranges"] = ranges
    return _run(principal_id, "sheets", slug, build({"flat": arguments}), account_email)


def composio_slides_get(
    principal_id: int | str,
    presentation_id: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Read presentation structure and slide text."""
    slug, build = _READ_ACTIONS["slides_get"]
    return _run(
        principal_id,
        "slides",
        slug,
        build({"resource_id": presentation_id}),
        account_email,
    )


def composio_slides_page(
    principal_id: int | str,
    presentation_id: str,
    page_object_id: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Read one slide's elements."""
    slug, build = _READ_ACTIONS["slides_page"]
    return _run(
        principal_id,
        "slides",
        slug,
        build(
            {
                "arguments": {
                    "presentationId": presentation_id,
                    "pageObjectId": page_object_id,
                }
            }
        ),
        account_email,
    )
