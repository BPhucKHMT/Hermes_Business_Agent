from caller import CallerContextRegistry, DM_REDIRECT_TEXT, DmOnlyError


PERSONAL_GMAIL_TOOL_NAMES = frozenset(
    (
        "email_search",
        "email_get_thread",
        "email_connection_status",
    )
)


class PersonalGmailTools:
    """Production PersonalGmailTools entrypoint and guard."""
    def __init__(self, registry: CallerContextRegistry | None = None) -> None:
        if isinstance(registry, CallerContextRegistry):
            self.registry = registry
        else:
            self.registry = CallerContextRegistry(session_store=registry)

    def pre_gateway_dispatch(
        self,
        event: object,
        gateway: object = None,
        session_store: object = None,
        **kwargs,
    ) -> dict | None:
        del gateway
        del kwargs
        if session_store is not None:
            self.registry.set_session_store(session_store)
        try:
            self.registry.capture(event)
        except DmOnlyError:
            pass
        return None

    def pre_tool_call(
        self,
        tool_name: str,
        _args: dict = None,
        task_id: str = "",
        session_id: str = "",
        **kwargs,
    ) -> dict | None:
        del _args
        del kwargs
        if tool_name not in PERSONAL_GMAIL_TOOL_NAMES:
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
        **kwargs,
    ) -> None:
        del platform
        del kwargs
        if session_id:
            self.registry.forget_by_session_id(session_id)
