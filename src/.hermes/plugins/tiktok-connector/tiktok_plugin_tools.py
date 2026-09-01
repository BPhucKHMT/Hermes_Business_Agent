from __future__ import annotations

import json
from typing import Any, Dict

from tiktok_caller import CallerContextRegistry, DmOnlyError


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(code: str, message: str = "") -> str:
    err: Dict[str, Any] = {"code": code}
    if message:
        err["message"] = message
    return _json({"ok": False, "error": err})


def _resolve_caller(
    registry: CallerContextRegistry | Any,
    task_id: str,
    session_id: str,
) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_dm_tool(task_id=task_id, session_id=session_id)


def _caller_error(exc: Exception) -> str:
    if isinstance(exc, DmOnlyError):
        return _error("dm_required", str(exc))
    return _error("missing_caller_context", str(exc))


def handle_tiktok_creator_info(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del params, kwargs
    if client is None:
        return _error("tiktok_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        res = client.get_creator_info(caller)
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("tiktok_creator_info_failed", str(exc))


def handle_tiktok_create_draft_post(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("tiktok_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        caption = str(params.get("caption", ""))
        video_file_path = str(params.get("video_file_path", ""))
        if not caption or not video_file_path:
            return _error("missing_required_tiktok_fields")
        res = client.create_draft_post(
            caller=caller,
            caption=caption,
            video_file_path=video_file_path,
            privacy_level=str(params.get("privacy_level", "SELF_ONLY")),
            disable_comment=bool(params.get("disable_comment", False)),
            disable_duet=bool(params.get("disable_duet", False)),
            disable_stitch=bool(params.get("disable_stitch", False)),
            brand_content_toggle=bool(params.get("brand_content_toggle", False)),
        )
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("create_tiktok_draft_failed", str(exc))


def handle_tiktok_publish_video(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("tiktok_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        draft_id = str(params.get("draft_id", ""))
        if not draft_id:
            return _error("draft_id_required")
        res = client.publish_video(caller=caller, draft_id=draft_id)
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("tiktok_publish_failed", str(exc))


def handle_tiktok_post_status(
    params: Dict[str, Any],
    *,
    client: Any = None,
    registry: Any = None,
    task_id: str = "",
    session_id: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    if client is None:
        return _error("tiktok_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        publish_id = str(params.get("publish_id", ""))
        if not publish_id:
            return _error("publish_id_required")
        res = client.get_post_status(caller=caller, publish_id=publish_id)
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("tiktok_post_status_failed", str(exc))
