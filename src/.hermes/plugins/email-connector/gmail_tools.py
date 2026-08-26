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
    def __init__(self, registry: CallerContextRegistry | None = None, gmail_client=None) -> None:
        if isinstance(registry, CallerContextRegistry):
            self.registry = registry
        else:
            self.registry = CallerContextRegistry(session_store=registry)
        self.gmail_client = gmail_client

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

    def email_search(self, model_args: dict, task_id: str = "", session_id: str = "") -> str:
        try:
            caller = self.registry.resolve_dm_tool(task_id=task_id, session_id=session_id)
        except DmOnlyError as error:
            return f'{{"status":"redirect_to_dm","public_text":"{str(error)}"}}'
        except LookupError as error:
            return f'{{"status":"error","error":"{str(error)}"}}'

        if getattr(caller, "chat_type", "") != "dm":
            return f'{{"status":"redirect_to_dm","public_text":"{DM_REDIRECT_TEXT}"}}'
        if self.gmail_client is not None:
            self.gmail_client.search_threads(query=model_args.get("query", ""))
        return f'{{"status":"ok","principal_id":"{caller.principal_id}"}}'


# Alias for backward compatibility
PersonalGmailGuard = PersonalGmailTools
