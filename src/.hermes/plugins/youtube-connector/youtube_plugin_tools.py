from __future__ import annotations

import json
from typing import Any, Dict

from youtube_caller import CallerContextRegistry, DmOnlyError


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


def handle_youtube_channel_status(
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
        return _error("youtube_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        res = client.get_channel_status(caller)
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("youtube_status_failed", str(exc))


def handle_youtube_list_videos(
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
        return _error("youtube_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        res = client.list_videos(caller=caller, limit=params.get("limit", 10))
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("youtube_list_videos_failed", str(exc))


def handle_youtube_create_draft_video(
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
        return _error("youtube_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        title = str(params.get("title", ""))
        video_file_path = str(params.get("video_file_path", ""))
        if not title or not video_file_path:
            return _error("missing_required_video_fields")
        tags = tuple(params.get("tags", []))
        res = client.create_draft_video(
            caller=caller,
            title=title,
            video_file_path=video_file_path,
            description=str(params.get("description", "")),
            tags=tags,
            privacy_status=str(params.get("privacy_status", "unlisted")),
            thumbnail_file_path=str(params.get("thumbnail_file_path", "")),
        )
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("create_draft_video_failed", str(exc))


def handle_youtube_upload_video(
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
        return _error("youtube_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        draft_id = str(params.get("draft_id", ""))
        if not draft_id:
            return _error("draft_id_required")
        res = client.upload_video(caller=caller, draft_id=draft_id)
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("upload_video_failed", str(exc))


def handle_youtube_update_video_metadata(
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
        return _error("youtube_connector_unavailable")
    try:
        caller = _resolve_caller(registry, task_id, session_id)
        video_id = str(params.get("video_id", ""))
        title = str(params.get("title", ""))
        if not video_id or not title:
            return _error("missing_required_update_fields")
        tags = tuple(params.get("tags", []))
        res = client.update_metadata(
            caller=caller,
            video_id=video_id,
            title=title,
            description=str(params.get("description", "")),
            tags=tags,
            privacy_status=str(params.get("privacy_status", "unlisted")),
        )
        return _json(res)
    except (DmOnlyError, LookupError) as exc:
        return _caller_error(exc)
    except Exception as exc:
        return _error("update_metadata_failed", str(exc))
