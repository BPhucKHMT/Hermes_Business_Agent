from caller import CallerContextRegistry, DmOnlyError


SOCIAL_TOOL_NAMES = frozenset(
    {
        "social_prepare_facebook_post",
        "social_browser_status",
        "social_verify_facebook_post",
    }
)


class SocialBrowserTools:
    def __init__(self, registry: CallerContextRegistry | None = None) -> None:
        self.registry = registry or CallerContextRegistry()

    def pre_gateway_dispatch(
        self,
        event: object,
        gateway: object = None,
        session_store: object = None,
        **kwargs,
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
        **kwargs,
    ) -> dict | None:
        del _args, kwargs
        if tool_name not in SOCIAL_TOOL_NAMES:
            return None
        try:
            self.registry.resolve_dm_tool(task_id=task_id, session_id=session_id)
        except (DmOnlyError, LookupError) as exc:
            return {"action": "block", "message": str(exc)}
        return None

    def on_session_finalize(
        self, session_id: str | None = None, platform: str = "", **kwargs
    ) -> None:
        del platform, kwargs
        if session_id:
            self.registry.forget_by_session_id(session_id)
