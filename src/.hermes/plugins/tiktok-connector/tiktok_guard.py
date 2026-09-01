from __future__ import annotations

from typing import Any

from tiktok_caller import CallerContextRegistry, DmOnlyError


TIKTOK_TOOL_NAMES = frozenset(
    {
        "tiktok_creator_info",
        "tiktok_create_draft_post",
        "tiktok_publish_video",
        "tiktok_post_status",
    }
)


class TikTokToolsGuard:
    """Production TikTokToolsGuard entrypoint and caller protection."""

    def __init__(self, registry: CallerContextRegistry | None = None) -> None:
        self.registry = registry or CallerContextRegistry()

    def pre_gateway_dispatch(
        self,
        event: object,
        gateway: object = None,
        session_store: object = None,
        **kwargs: Any,
    ) -> None:
        del gateway, kwargs
        if session_store is not None:
            self.registry.set_session_store(session_store)
        try:
            self.registry.capture(event)
        except DmOnlyError:
            pass

    def pre_tool_call(
        self,
        tool_name: str,
        _args: dict | None = None,
        task_id: str = "",
        session_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        del _args, kwargs
        if tool_name not in TIKTOK_TOOL_NAMES:
            return None
        try:
            self.registry.resolve_dm_tool(task_id=task_id, session_id=session_id)
        except DmOnlyError as error:
            return {"action": "block", "message": str(error)}
        except LookupError as error:
            return {"action": "block", "message": str(error)}
        return None

    def on_session_finalize(
        self,
        session_id: str | None = None,
        platform: str = "",
        **kwargs: Any,
    ) -> None:
        del platform, kwargs
        if session_id:
            self.registry.forget_by_session_id(session_id)
