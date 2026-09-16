"""Tool schemas for Drive/Docs/Sheets/Slides operations via the email connector."""

from __future__ import annotations

_ACCOUNT_PROP = {
    "type": "string",
    "description": (
        "Optional connected account email to use. Pass nothing when only one "
        "account is connected or the user already named the account."
    ),
}

GOOGLE_DRIVE_FIND_SCHEMA = {
    "name": "google_drive_find",
    "description": (
        "Search the user's Google Drive for files and folders using Drive query "
        "syntax (e.g. \"name contains 'proposal'\" or a plain keyword). Returns "
        "matching file IDs, names and links. Use when the user asks to find "
        "files in their Drive."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Drive search query or plain keyword.",
            },
            "page_size": {
                "type": "integer",
                "description": "Maximum results per page (1-100). Default 20.",
            },
            "account_email": _ACCOUNT_PROP,
        },
        "required": ["query"],
    },
}

GOOGLE_FILE_READ_SCHEMA = {
    "name": "google_file_read",
    "description": (
        "Read a Google resource by link or resource ID using the user's "
        "connected account, including private files shared only with that "
        "account. Accepts Docs/Sheets/Slides/Drive URLs (with optional #gid=) "
        "or a raw file/document/spreadsheet/presentation ID. Supports Google "
        "native documents and Drive-hosted files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url_or_id": {
                "type": "string",
                "description": "Google Workspace URL or resource ID.",
            },
            "mime_type": {
                "type": "string",
                "description": "Optional export MIME type for Google native files.",
            },
            "account_email": _ACCOUNT_PROP,
        },
        "required": ["url_or_id"],
    },
}

GOOGLE_DOC_READ_SCHEMA = {
    "name": "google_doc_read",
    "description": (
        "Read a Google Docs document's full content (all tabs and tables) by "
        "document ID or link."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "Docs document ID."},
            "account_email": _ACCOUNT_PROP,
        },
        "required": ["document_id"],
    },
}

GOOGLE_SHEET_READ_SCHEMA = {
    "name": "google_sheet_read",
    "description": (
        "Read values from a Google Sheets spreadsheet. Optionally restrict to "
        "A1 ranges (e.g. ['Sheet1'!A1:C20']); returns values for requested "
        "ranges. Use google_sheet_info first when tabs are unknown."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID."},
            "ranges": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional A1 ranges to read.",
            },
            "account_email": _ACCOUNT_PROP,
        },
        "required": ["spreadsheet_id"],
    },
}

GOOGLE_SLIDE_READ_SCHEMA = {
    "name": "google_slide_read",
    "description": (
        "Read a Google Slides presentation's structure and text by presentation "
        "ID or link. Optionally pass page_object_id for one slide."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "presentation_id": {"type": "string", "description": "Presentation ID."},
            "page_object_id": {
                "type": "string",
                "description": "Optional slide object ID to read a single slide.",
            },
            "account_email": _ACCOUNT_PROP,
        },
        "required": ["presentation_id"],
    },
}

WORKSPACE_TOOL_SCHEMAS = [
    GOOGLE_DRIVE_FIND_SCHEMA,
    GOOGLE_FILE_READ_SCHEMA,
    GOOGLE_DOC_READ_SCHEMA,
    GOOGLE_SHEET_READ_SCHEMA,
    GOOGLE_SLIDE_READ_SCHEMA,
]
