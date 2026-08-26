from __future__ import annotations

import json
import logging
from typing import Any, Dict

from caller import CallerContext, DM_REDIRECT_TEXT
from schemas import (
    EMAIL_CONNECTION_STATUS_SCHEMA,
    EMAIL_GET_THREAD_SCHEMA,
    EMAIL_SEARCH_SCHEMA,
)

logger = logging.getLogger(__name__)


def handle_email_search(params: Dict[str, Any], caller_context: Any = None, **kwargs) -> str:
    if caller_context is None:
        return json.dumps({"ok": False, "error": {"code": "missing_caller_context"}})

    if getattr(caller_context, "chat_type", "") != "dm":
        return json.dumps({"ok": True, "delivery": "redirect_to_dm", "message": DM_REDIRECT_TEXT})

    query = params.get("query", "")
    return json.dumps({
        "ok": True,
        "delivery": "dm",
        "query": query,
        "results": f"Grounded search for '{query}'",
    })


def handle_email_get_thread(params: Dict[str, Any], caller_context: Any = None, **kwargs) -> str:
    if caller_context is None:
        return json.dumps({"ok": False, "error": {"code": "missing_caller_context"}})

    if getattr(caller_context, "chat_type", "") != "dm":
        return json.dumps({"ok": True, "delivery": "redirect_to_dm", "message": DM_REDIRECT_TEXT})

    thread_id = params.get("thread_id", "")
    return json.dumps({
        "ok": True,
        "delivery": "dm",
        "thread_id": thread_id,
        "content": f"Grounded thread contents for {thread_id}",
    })


def handle_email_connection_status(params: Dict[str, Any], caller_context: Any = None, **kwargs) -> str:
    if caller_context is None:
        return json.dumps({"ok": False, "error": {"code": "missing_caller_context"}})

    return json.dumps({
        "ok": True,
        "principal": getattr(caller_context, "principal_id", "unknown"),
        "status": "connected",
    })
