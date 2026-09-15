from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from gateway.session import build_session_key

DM_REDIRECT_TEXT = "Mở chat riêng với Hermes để xem Gmail cá nhân."


class DmOnlyError(ValueError):
    pass


@dataclass(frozen=True)
class CallerContext:
    principal_id: str
    platform: str
    user_id: str | UUID
    chat_id: str
    thread_id: str | None
    chat_type: str
    profile: str
    session_key: str


def _candidate_src_dirs() -> list[Path]:
    candidates: list[Path] = []
    for key in ("HERMES_PROJECT_SRC", "HERMES_SRC_DIR"):
        val = os.environ.get(key)
        if val and (Path(val) / "tools").is_dir():
            candidates.append(Path(val))
    if len(Path(__file__).resolve().parents) >= 3:
        parent_candidate = Path(__file__).resolve().parents[2]
        if (parent_candidate / "tools").is_dir():
            candidates.append(parent_candidate)
    for env_file in (
        Path.home() / ".hermes" / ".env",
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
        if os.name == "nt"
        else None,
    ):
        if env_file and env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("HERMES_PROJECT_SRC="):
                        val = (
                            line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        )
                        if val and (Path(val) / "tools").is_dir():
                            candidates.append(Path(val))
            except OSError:
                pass
    for cwd_cand in (Path.cwd() / "src", Path.cwd()):
        if (cwd_cand / "tools").is_dir():
            candidates.append(cwd_cand)
    return candidates


_load_local_owner = None
try:
    from tools.composio.local_owner import load_local_owner as _load_local_owner
except (ImportError, ModuleNotFoundError):
    for _cand in _candidate_src_dirs():
        _target = _cand / "tools" / "composio" / "local_owner.py"
        if _target.is_file():
            _spec = importlib.util.spec_from_file_location(
                "_local_owner_dyn", str(_target)
            )
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _load_local_owner = getattr(_mod, "load_local_owner", None)
                if _load_local_owner is not None:
                    break


class CallerContextRegistry:
    def __init__(
        self,
        session_store: Any | None = None,
        *,
        local_owner_path: Path | None = None,
    ) -> None:
        self._session_store = session_store
        self._local_owner_path = Path(local_owner_path) if local_owner_path else None
        self._by_session_key: dict[str, CallerContext] = {}
        self._issued_by_session_key: dict[str, CallerContext] = {}
        self._session_key_by_session_id: dict[str, str] = {}
        self._redirect_only_session_keys: set[str] = set()
        self._current_caller: ContextVar[CallerContext | None] = ContextVar(
            f"email_caller_{id(self)}",
            default=None,
        )
        self._current_redirect: ContextVar[bool] = ContextVar(
            f"email_redirect_{id(self)}",
            default=False,
        )
        self._current_gateway_context: ContextVar[bool] = ContextVar(
            f"email_gateway_context_{id(self)}",
            default=False,
        )
        self._lock = Lock()

    def set_session_store(self, session_store: Any) -> None:
        with self._lock:
            self._session_store = session_store

    def _resolve_local(self) -> CallerContext:
        resolver = _load_local_owner
        if resolver is None:
            raise LookupError("local owner resolver unavailable")
        owner_id = resolver(self._local_owner_path)
        if owner_id is None:
            raise LookupError("local owner binding is not provisioned")
        return CallerContext(
            principal_id=f"local:owner:{owner_id}",
            platform="local",
            user_id=UUID(owner_id),
            chat_id="",
            thread_id=None,
            chat_type="local",
            profile="local",
            session_key=f"local:owner:{owner_id}",
        )

    def capture(self, event: object, session_key: str | None = None) -> CallerContext:
        source = getattr(event, "source", None)
        if source is None:
            raise ValueError("Event has no source")
        profile = getattr(source, "profile", None)
        platform = getattr(source.platform, "value", source.platform)
        self._current_caller.set(None)
        self._current_redirect.set(False)
        self._current_gateway_context.set(True)

        try:
            derived_key = build_session_key(source)
            profile_key = build_session_key(source, profile=profile)
        except (AttributeError, TypeError, ValueError):
            derived_key = f"{platform}:{getattr(source, 'chat_id', '')}:{getattr(source, 'user_id', '')}"
            profile_key = derived_key
        effective_key = session_key or derived_key

        if getattr(source, "chat_type", "") != "dm":
            self._current_redirect.set(True)
            with self._lock:
                self._redirect_only_session_keys.add(effective_key)
                if profile_key:
                    self._redirect_only_session_keys.add(profile_key)
            raise DmOnlyError(DM_REDIRECT_TEXT)

        if not getattr(source, "user_id", None) or not getattr(source, "chat_id", None):
            raise ValueError(
                f"{str(platform).capitalize()} DM caller requires user_id and chat_id"
            )

        caller = CallerContext(
            principal_id=f"{platform}:{profile or 'default'}:{source.user_id}",
            platform=platform,
            user_id=str(source.user_id),
            chat_id=str(source.chat_id),
            thread_id=(
                str(source.thread_id) if getattr(source, "thread_id", None) else None
            ),
            chat_type="dm",
            profile=profile or "default",
            session_key=effective_key,
        )
        with self._lock:
            self._by_session_key[effective_key] = caller
            self._issued_by_session_key[effective_key] = caller
            self._redirect_only_session_keys.discard(effective_key)
            if profile_key:
                self._by_session_key[profile_key] = caller
                self._issued_by_session_key[profile_key] = caller
                self._redirect_only_session_keys.discard(profile_key)
        self._current_caller.set(caller)
        return caller

    def resolve_dm_tool(
        self, *, task_id: str = "", session_id: str = ""
    ) -> CallerContext:
        if self._current_redirect.get():
            raise DmOnlyError(DM_REDIRECT_TEXT)

        if not self._current_gateway_context.get():
            return self._resolve_local()

        if task_id and session_id and task_id != session_id:
            raise LookupError("conflicting runtime identifiers")
        runtime_id = session_id or task_id
        if runtime_id:
            session_key: str | None = None
            with self._lock:
                session_key = self._session_key_by_session_id.get(runtime_id)

            if session_key is None and self._session_store is not None:
                entry = self._session_store.lookup_by_session_id(runtime_id)
                if entry is not None:
                    session_key = getattr(entry, "session_key", None)
                    if session_key:
                        with self._lock:
                            self._session_key_by_session_id[runtime_id] = session_key

            if session_key is not None:
                with self._lock:
                    if session_key in self._redirect_only_session_keys:
                        raise DmOnlyError(DM_REDIRECT_TEXT)
                    caller = self._by_session_key.get(session_key)
                if caller is None:
                    raise LookupError(
                        "Hermes session has no captured Telegram DM caller"
                    )
                return caller

            if self._current_gateway_context.get():
                raise LookupError("Hermes session is not bound to a gateway caller")
        elif self._current_gateway_context.get():
            raise LookupError("runtime identifier required to resolve caller")

        return self._resolve_local()

    def resolve_command(self) -> CallerContext:
        if self._current_redirect.get():
            raise DmOnlyError(DM_REDIRECT_TEXT)
        caller = self._current_caller.get()
        if caller is not None:
            return caller
        if self._current_gateway_context.get():
            raise LookupError("command has no captured caller")
        return self._resolve_local()

    def get_issued_dm(self, session_key: str) -> CallerContext | None:
        with self._lock:
            return self._issued_by_session_key.get(session_key)

    def forget_by_session_id(self, session_id: str) -> None:
        with self._lock:
            session_key = self._session_key_by_session_id.pop(session_id, None)
            if session_key:
                self._by_session_key.pop(session_key, None)
                self._issued_by_session_key.pop(session_key, None)
                self._redirect_only_session_keys.discard(session_key)
