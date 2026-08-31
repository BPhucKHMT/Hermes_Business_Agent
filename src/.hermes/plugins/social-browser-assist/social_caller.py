from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Any

from gateway.session import build_session_key


DM_REDIRECT_TEXT = "Open a private Telegram chat with Hermes to prepare a social post."


class DmOnlyError(ValueError):
    pass


@dataclass(frozen=True)
class CallerContext:
    principal_id: str
    platform: str
    user_id: str
    chat_id: str
    profile: str
    session_key: str


class CallerContextRegistry:
    def __init__(self) -> None:
        self._session_store: Any = None
        self._by_session_key: dict[str, CallerContext] = {}
        self._session_key_by_session_id: dict[str, str] = {}
        self._redirect_keys: set[str] = set()
        self._current: ContextVar[CallerContext | None] = ContextVar(
            f"social_caller_{id(self)}", default=None
        )
        self._lock = Lock()

    def set_session_store(self, session_store: Any) -> None:
        with self._lock:
            self._session_store = session_store

    def capture(self, event: object) -> CallerContext:
        source = getattr(event, "source", None)
        if source is None:
            raise ValueError("event_source_required")
        platform = getattr(source.platform, "value", source.platform)
        profile = getattr(source, "profile", None) or "default"
        session_key = build_session_key(source)
        if platform != "telegram" or getattr(source, "chat_type", "") != "dm":
            self._current.set(None)
            with self._lock:
                self._redirect_keys.add(session_key)
            raise DmOnlyError(DM_REDIRECT_TEXT)
        if not getattr(source, "user_id", None) or not getattr(source, "chat_id", None):
            raise ValueError("telegram_dm_identity_required")
        caller = CallerContext(
            principal_id=f"telegram:{profile}:{source.user_id}",
            platform="telegram",
            user_id=str(source.user_id),
            chat_id=str(source.chat_id),
            profile=profile,
            session_key=session_key,
        )
        with self._lock:
            self._by_session_key[session_key] = caller
            self._redirect_keys.discard(session_key)
        self._current.set(caller)
        return caller

    def resolve_dm_tool(
        self, *, task_id: str = "", session_id: str = ""
    ) -> CallerContext:
        if task_id and session_id and task_id != session_id:
            raise LookupError("conflicting_runtime_identifiers")
        runtime_id = session_id or task_id
        if not runtime_id:
            raise LookupError("runtime_identifier_required")
        session_key = self._session_key_by_session_id.get(runtime_id)
        if session_key is None and self._session_store is not None:
            entry = self._session_store.lookup_by_session_id(runtime_id)
            session_key = getattr(entry, "session_key", None) if entry else None
            if session_key:
                self._session_key_by_session_id[runtime_id] = session_key
        if session_key is None:
            raise LookupError("caller_session_not_bound")
        with self._lock:
            if session_key in self._redirect_keys:
                raise DmOnlyError(DM_REDIRECT_TEXT)
            caller = self._by_session_key.get(session_key)
        if caller is None:
            raise LookupError("caller_context_missing")
        return caller

    def forget_by_session_id(self, session_id: str) -> None:
        with self._lock:
            session_key = self._session_key_by_session_id.pop(session_id, None)
            if session_key:
                self._by_session_key.pop(session_key, None)
                self._redirect_keys.discard(session_key)
