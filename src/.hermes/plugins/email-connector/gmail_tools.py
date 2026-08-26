from caller import CallerContextRegistry, DM_REDIRECT_TEXT, DmOnlyError


class PersonalGmailTools:
    """Host-bound entrypoint for personal Gmail tool calls."""

    def __init__(self, session_store, gmail_client):
        self._session_store = session_store
        self._gmail_client = gmail_client
        self.registry = CallerContextRegistry(session_store)

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
        entry = self._session_store.lookup_by_session_id(session_id)
        if entry is not None:
            self.registry.forget(entry.session_key)
