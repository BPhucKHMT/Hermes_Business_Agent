from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

from gateway.session import build_session_key


DM_REDIRECT_TEXT = "Mở chat riêng với Hermes để truy cập Google Calendar cá nhân."


class DmOnlyError(ValueError):
    pass
@dataclass(frozen=True)
class CallerContext:
    principal_id: str
    platform: str
    user_id: str
    chat_id: str
    thread_id: Optional[str]
    chat_type: str
    profile: str
    session_key: str


class CallerContextRegistry:
    def __init__(self, session_store: Optional[Any] = None) -> None:
        self._session_store = session_store
        self._by_session_key: dict[str, CallerContext] = {}
        self._session_key_by_session_id: dict[str, str] = {}
        self._redirect_only_session_keys: set[str] = set()
        self._current_caller: ContextVar[CallerContext | None] = ContextVar(
            f"calendar_caller_{id(self)}",
            default=None,
        )
        self._lock = Lock()

    def set_session_store(self, session_store: Any) -> None:
        with self._lock:
            self._session_store = session_store

    def capture(self, event: object, session_key: str | None = None) -> CallerContext:
        source = getattr(event, "source", None)
        if source is None:
            raise ValueError("Event has no source")

        profile = getattr(source, "profile", None)
        derived_key = build_session_key(source)
        profile_key = build_session_key(source, profile=profile)
        effective_key = session_key or derived_key
        platform = getattr(source.platform, "value", source.platform)
        if getattr(source, "chat_type", "") != "dm":
            self._current_caller.set(None)
            with self._lock:
                self._redirect_only_session_keys.add(effective_key)
                if profile_key:
                    self._redirect_only_session_keys.add(profile_key)
            raise DmOnlyError(DM_REDIRECT_TEXT)

        if not getattr(source, "user_id", None) or not getattr(source, "chat_id", None):
            raise ValueError(f"{str(platform).capitalize()} DM caller requires user_id and chat_id")

        caller = CallerContext(
            principal_id=f"{platform}:{profile or 'default'}:{source.user_id}",
            platform=platform,
            user_id=str(source.user_id),
            chat_id=str(source.chat_id),
            thread_id=str(source.thread_id) if getattr(source, "thread_id", None) else None,
            chat_type="dm",
            profile=profile or "default",
            session_key=effective_key,
        )
        with self._lock:
            self._by_session_key[effective_key] = caller
            self._redirect_only_session_keys.discard(effective_key)
            if profile_key:
                self._by_session_key[profile_key] = caller
                self._redirect_only_session_keys.discard(profile_key)
        self._current_caller.set(caller)
        return caller

    def resolve_dm_tool(self, *, task_id: str = "", session_id: str = "") -> CallerContext:
        if task_id and session_id and task_id != session_id:
            raise LookupError("conflicting runtime identifiers")

        runtime_id = session_id or task_id
        if not runtime_id:
            raise LookupError("runtime identifier required to resolve caller")

        session_key: Optional[str] = None
        with self._lock:
            session_key = self._session_key_by_session_id.get(runtime_id)

        if session_key is None and self._session_store is not None:
            entry = self._session_store.lookup_by_session_id(runtime_id)
            if entry is not None:
                session_key = getattr(entry, "session_key", None)
                if session_key:
                    with self._lock:
                        self._session_key_by_session_id[runtime_id] = session_key

        if session_key is None:
            raise LookupError("Hermes session is not bound to a gateway caller")

        with self._lock:
            if session_key in self._redirect_only_session_keys:
                raise DmOnlyError(DM_REDIRECT_TEXT)
            caller = self._by_session_key.get(session_key)

        if caller is None:
            raise LookupError("Hermes session has no captured Telegram DM caller")
        return caller
    def resolve_command(self) -> CallerContext:
        caller = self._current_caller.get()
        if caller is None:
            raise LookupError("command has no captured Telegram DM caller")
        return caller


    def forget_by_session_id(self, session_id: str) -> None:
        with self._lock:
            session_key = self._session_key_by_session_id.pop(session_id, None)
            if session_key:
                self._by_session_key.pop(session_key, None)
                self._redirect_only_session_keys.discard(session_key)
