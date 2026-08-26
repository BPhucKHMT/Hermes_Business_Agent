from dataclasses import dataclass
from threading import Lock

from gateway.session import build_session_key


DM_REDIRECT_TEXT = "Mở chat riêng với Hermes để xem Gmail cá nhân."


class DmOnlyError(ValueError):
    pass


@dataclass(frozen=True)
class CallerContext:
    principal_id: str
    platform: str
    user_id: str
    chat_id: str
    thread_id: str | None
    chat_type: str
    profile: str
    session_key: str


class CallerContextRegistry:
    def __init__(self, session_store, gateway_config=None):
        self._session_store = session_store
        self._gateway_config = gateway_config
        self._by_session_key: dict[str, CallerContext] = {}
        self._redirect_only: set[str] = set()
        self._session_keys_by_runtime_id: dict[str, str] = {}
        self._lock = Lock()

    def capture_gateway(self, event: object) -> CallerContext | None:
        source = event.source
        platform = getattr(source.platform, "value", source.platform)
        if platform != "telegram":
            return None

        session_key = self._session_key(source)
        if source.chat_type != "dm":
            with self._lock:
                self._by_session_key.pop(session_key, None)
                self._redirect_only.add(session_key)
            return None
        return self.capture_dm(event, session_key)

    def capture_dm(self, event: object, session_key: str) -> CallerContext:
        source = event.source
        platform = getattr(source.platform, "value", source.platform)
        if platform != "telegram" or source.chat_type != "dm":
            raise DmOnlyError(DM_REDIRECT_TEXT)
        if not source.user_id or not source.chat_id:
            raise ValueError("Telegram DM caller requires user_id and chat_id")

        profile = source.profile or "default"
        derived_key = self._session_key(source)
        if session_key != derived_key:
            raise ValueError("session_key does not match the trusted gateway source")

        caller = CallerContext(
            principal_id=f"telegram:{profile}:{source.user_id}",
            platform=platform,
            user_id=str(source.user_id),
            chat_id=str(source.chat_id),
            thread_id=str(source.thread_id) if source.thread_id else None,
            chat_type="dm",
            profile=profile,
            session_key=session_key,
        )
        with self._lock:
            self._redirect_only.discard(session_key)
            self._by_session_key[session_key] = caller
        return caller

    def resolve_dm_tool(self, *, task_id: str, session_id: str) -> CallerContext:
        if task_id and session_id and task_id != session_id:
            raise LookupError("conflicting Hermes runtime session identifiers")
        runtime_id = session_id or task_id
        if not runtime_id:
            raise LookupError("Hermes runtime session identifier is required")

        entry = self._session_store.lookup_by_session_id(runtime_id)
        if entry is None:
            raise LookupError("Hermes session is not bound to a gateway caller")
        with self._lock:
            self._session_keys_by_runtime_id[runtime_id] = entry.session_key
            if entry.session_key in self._redirect_only:
                raise DmOnlyError(DM_REDIRECT_TEXT)
            caller = self._by_session_key.get(entry.session_key)
        if caller is None:
            raise LookupError("Hermes session has no captured Telegram DM caller")
        return caller

    def require_issued(self, caller: CallerContext) -> None:
        with self._lock:
            issued = self._by_session_key.get(caller.session_key)
        if issued is not caller:
            raise LookupError("caller is not a registry-issued captured context")

    def forget_runtime(self, session_id: str) -> None:
        with self._lock:
            session_key = self._session_keys_by_runtime_id.pop(session_id, None)
        if session_key is not None:
            self.forget(session_key)

    def forget(self, session_key: str) -> None:
        with self._lock:
            self._by_session_key.pop(session_key, None)
            self._redirect_only.discard(session_key)
            stale_ids = [
                runtime_id
                for runtime_id, bound_key in self._session_keys_by_runtime_id.items()
                if bound_key == session_key
            ]
            for runtime_id in stale_ids:
                self._session_keys_by_runtime_id.pop(runtime_id, None)

    def _session_key(self, source) -> str:
        config = self._gateway_config
        profile = source.profile
        if config is not None and not getattr(config, "multiplex_profiles", False):
            profile = None
        return build_session_key(
            source,
            group_sessions_per_user=getattr(
                config,
                "group_sessions_per_user",
                True,
            ),
            thread_sessions_per_user=getattr(
                config,
                "thread_sessions_per_user",
                False,
            ),
            profile=profile,
        )
