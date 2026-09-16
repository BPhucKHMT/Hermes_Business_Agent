"""Caller-bound Drive/Docs/Sheets/Slides tool handlers for the connector."""

from __future__ import annotations

import json
import logging
from typing import Any
import urllib.parse

from caller import DmOnlyError
from plugin_tools import _caller_error, _error, _resolve_caller, _resolve_principal

try:
    from tools.composio.glinks import parse_google_url
except (ImportError, ModuleNotFoundError):
    try:
        from tools.composio.glinks import parse_google_url  # project-src import
    except (ImportError, ModuleNotFoundError):
        parse_google_url = None

logger = logging.getLogger(__name__)

try:
    from tools.composio import bridge as _composio_bridge
except (ImportError, ModuleNotFoundError):
    _composio_bridge = None

if _composio_bridge is None or not hasattr(_composio_bridge, "call_google"):
    try:
        from plugin_tools import _load_composio_bridge as _load_bridge

        _composio_bridge = _load_bridge()
    except (ImportError, RuntimeError, AttributeError):
        _composio_bridge = None


def _call_google(
    operation: str, principal_id: str, params: dict[str, Any] | None = None
) -> Any:
    bridge = _composio_bridge
    if bridge is None or not hasattr(bridge, "call_google"):
        raise RuntimeError(
            "call_google bridge unavailable; run python src/setup_local.py --local"
        )
    return bridge.call_google(operation, principal_id, params)


def _caller_context(registry: Any, task_id: str, session_id: str) -> tuple[Any, str]:
    caller = _resolve_caller(registry, task_id, session_id)
    return caller, _resolve_principal(caller)


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def handle_google_drive_find(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        _caller, principal_id = _caller_context(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    query = str(params.get("query", "")).strip()
    if not query:
        return _error("query_required", "A search keyword is required.")
    try:
        result = _call_google(
            "composio_drive_find",
            principal_id,
            {
                "query": query,
                "page_size": params.get("page_size", 20),
                "account_email": params.get("account_email"),
            },
        )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "drive_find_failed").lower(),
                result.get("message", "Drive search failed"),
            )
        return _ok(
            {
                "account_email": result.get("account_email"),
                "result": result.get("data", {}),
            }
        )
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure
        logger.warning("Drive find failed for %s: %s", principal_id, exc)
        return _error("drive_find_failed", str(exc))


def handle_google_file_read(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        _caller, principal_id = _caller_context(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    url_or_id = str(params.get("url_or_id", "")).strip()
    if not url_or_id:
        return _error("url_or_id_required")
    account_email = params.get("account_email")
    try:
        if url_or_id.startswith(("http://", "https://")):
            parsed = urllib.parse.urlparse(url_or_id)
            host = parsed.netloc.casefold()
            if host == "docs.google.com" and "/document/" in parsed.path:
                tail = parsed.path.rsplit("/document/d/", 1)[-1]
                document_id = tail.split("/", 1)[0]
                result = _call_google(
                    "composio_docs_get",
                    principal_id,
                    {"document_id": document_id, "account_email": account_email},
                )
            elif host == "docs.google.com" and "/spreadsheets/" in parsed.path:
                tail = parsed.path.rsplit("/spreadsheets/d/", 1)[-1]
                spreadsheet_id = tail.split("/", 1)[0]
                result = _call_google(
                    "composio_sheets_values",
                    principal_id,
                    {"spreadsheet_id": spreadsheet_id, "account_email": account_email},
                )
            elif host == "docs.google.com" and "/presentation/" in parsed.path:
                tail = parsed.path.rsplit("/presentation/d/", 1)[-1]
                presentation_id = tail.split("/", 1)[0]
                result = _call_google(
                    "composio_slides_get",
                    principal_id,
                    {
                        "presentation_id": presentation_id,
                        "account_email": account_email,
                    },
                )
            elif parse_google_url is not None:
                resource = parse_google_url(url_or_id)
                if resource is None:
                    return _error(
                        "unsupported_url",
                        "Unrecognized Google link. Ask the user to double-check it.",
                    )
                if resource.kind == "folder":
                    return _error(
                        "folder_not_supported",
                        "Reading Drive folders is not supported; search for a specific file.",
                    )
                result = _call_google(
                    "composio_drive_read_file",
                    principal_id,
                    {
                        "file_id": resource.resource_id,
                        "mime_type": params.get("mime_type"),
                        "account_email": account_email,
                    },
                )
        else:
            result = _call_google(
                "composio_drive_read_file",
                principal_id,
                {
                    "file_id": url_or_id,
                    "mime_type": params.get("mime_type"),
                    "account_email": account_email,
                },
            )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "file_read_failed").lower(),
                result.get("message", "Failed to read the Google document"),
            )
        return _ok(
            {
                "account_email": result.get("account_email"),
                "result": result.get("data", {}),
            }
        )
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure
        logger.warning("Google file read failed for %s: %s", principal_id, exc)
        return _error("file_read_failed", str(exc))


def handle_google_doc_read(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        _caller, principal_id = _caller_context(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    document_id = str(params.get("document_id", "")).strip()
    if not document_id:
        return _error("document_id_required")
    try:
        result = _call_google(
            "composio_docs_get",
            principal_id,
            {"document_id": document_id, "account_email": params.get("account_email")},
        )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "doc_read_failed").lower(),
                result.get("message", "Failed to read Google Docs"),
            )
        return _ok(
            {
                "account_email": result.get("account_email"),
                "result": result.get("data", {}),
            }
        )
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure
        logger.warning("Docs read failed for %s: %s", principal_id, exc)
        return _error("doc_read_failed", str(exc))


def handle_google_sheet_read(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        _caller, principal_id = _caller_context(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    spreadsheet_id = str(params.get("spreadsheet_id", "")).strip()
    if not spreadsheet_id:
        return _error("spreadsheet_id_required")
    try:
        result = _call_google(
            "composio_sheets_values",
            principal_id,
            {
                "spreadsheet_id": spreadsheet_id,
                "ranges": params.get("ranges"),
                "account_email": params.get("account_email"),
            },
        )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "sheet_read_failed").lower(),
                result.get("message", "Failed to read Google Sheets"),
            )
        return _ok(
            {
                "account_email": result.get("account_email"),
                "result": result.get("data", {}),
            }
        )
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure
        logger.warning("Sheets read failed for %s: %s", principal_id, exc)
        return _error("sheet_read_failed", str(exc))


def handle_google_slide_read(
    params: dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None or getattr(client, "configured", True) is False:
        return _error("connector_unavailable")
    try:
        _caller, principal_id = _caller_context(registry, task_id, session_id)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    presentation_id = str(params.get("presentation_id", "")).strip()
    if not presentation_id:
        return _error("presentation_id_required")
    page_object_id = params.get("page_object_id")
    try:
        if page_object_id:
            result = _call_google(
                "composio_slides_page",
                principal_id,
                {
                    "presentation_id": presentation_id,
                    "page_object_id": page_object_id,
                    "account_email": params.get("account_email"),
                },
            )
        else:
            result = _call_google(
                "composio_slides_get",
                principal_id,
                {
                    "presentation_id": presentation_id,
                    "account_email": params.get("account_email"),
                },
            )
        if result.get("status") != "success":
            return _error(
                result.get("error_code", "slide_read_failed").lower(),
                result.get("message", "Failed to read Google Slides"),
            )
        return _ok(
            {
                "account_email": result.get("account_email"),
                "result": result.get("data", {}),
            }
        )
    except Exception as exc:  # noqa: BLE001 -- tool boundary maps provider failure
        logger.warning("Slides read failed for %s: %s", principal_id, exc)
        return _error("slide_read_failed", str(exc))
