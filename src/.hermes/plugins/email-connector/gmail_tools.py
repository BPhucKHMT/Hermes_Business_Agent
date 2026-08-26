from .caller import CallerContextRegistry, DM_REDIRECT_TEXT, DmOnlyError


PERSONAL_GMAIL_TOOL_NAMES = frozenset(
    {"email_connection_status", "email_search", "email_get_thread"}
)


class PersonalGmailGuard:
    """Fail-closed Hermes hooks guarding every personal Gmail tool."""

    def __init__(self):
        self.registry = None
        self._session_store = None

    def pre_gateway_dispatch(self, event, gateway, session_store, **_kwargs):
        if self.registry is None:
            self._session_store = session_store
            self.registry = CallerContextRegistry(session_store, gateway.config)
        elif session_store is not self._session_store:
            raise RuntimeError("Gmail caller guard received a different session store")
        self.registry.capture_gateway(event)
        return None

    def pre_tool_call(
        self,
        tool_name,
        args,
        task_id,
        session_id="",
        **_kwargs,
    ):
        del args
        if tool_name not in PERSONAL_GMAIL_TOOL_NAMES:
            return None
        if self.registry is None:
            return {"action": "block", "message": DM_REDIRECT_TEXT}
        try:
            self.registry.resolve_dm_tool(
                task_id=task_id,
                session_id=session_id,
            )
        except (DmOnlyError, LookupError):
            return {"action": "block", "message": DM_REDIRECT_TEXT}
        return None

    def on_session_finalize(self, session_id, **_kwargs):
        if self.registry is not None:
            self.registry.forget_runtime(session_id)


class PersonalGmailTools:
    """Host-bound entrypoint for personal Gmail tool calls."""

    def __init__(self, session_store, gmail_client, gateway_config=None):
        self._gmail_client = gmail_client
        self.registry = CallerContextRegistry(session_store, gateway_config)

    def pre_gateway_dispatch(self, event, **_kwargs):
        self.registry.capture_gateway(event)
        return None

    def email_search(self, *, task_id: str, session_id: str, model_args: dict):
        try:
            caller = self.registry.resolve_dm_tool(
                task_id=task_id,
                session_id=session_id,
            )
        except DmOnlyError:
            return {
                "status": "redirect_to_dm",
                "public_text": DM_REDIRECT_TEXT,
            }

        return self._gmail_client.search(
            caller.principal_id,
            str(model_args.get("query", "")),
        )

    def on_session_finalize(self, session_id: str, **_kwargs) -> None:
        self.registry.forget_runtime(session_id)
