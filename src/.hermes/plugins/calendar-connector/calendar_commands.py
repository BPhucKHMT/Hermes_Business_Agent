from __future__ import annotations

import json
from typing import Any

from calendar_caller import DM_REDIRECT_TEXT, DmOnlyError


def _caller(registry: Any) -> Any:
    if registry is None:
        raise LookupError("caller_registry_unavailable")
    return registry.resolve_command()


def _principal_id(caller: Any) -> str:
    principal_id = str(getattr(caller, "principal_id", "")).strip()
    if not principal_id:
        raise LookupError("caller_principal_unavailable")
    return principal_id


def _call_google(
    operation: str,
    principal_id: str,
    params: dict | None = None,
) -> Any:
    try:
        from tools.composio.bridge import call_google
        return call_google(operation, principal_id, params)
    except (ImportError, ModuleNotFoundError):
        pass
    import importlib.util, os, sys
    from pathlib import Path
    for candidate in (
        Path(os.environ.get("HERMES_PROJECT_SRC", "")),
        Path("C:/Hermes-Business-Agent/src"),
        Path.cwd() / "src",
        Path.cwd(),
    ):
        target = candidate / "tools" / "composio" / "bridge.py"
        if target.is_file():
            src_dir = str(candidate.resolve())
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            try:
                import tools
                tools_dir = str((candidate / "tools").resolve())
                if hasattr(tools, "__path__") and tools_dir not in tools.__path__:
                    tools.__path__.insert(0, tools_dir)
            except Exception:
                pass
            spec = importlib.util.spec_from_file_location("tools.composio.bridge", str(target))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["tools.composio.bridge"] = mod
                spec.loader.exec_module(mod)
                return mod.call_google(operation, principal_id, params)
    raise RuntimeError("call_google bridge unavailable; run python src/setup_local.py --local")


def _unavailable(code: str = "connector_unavailable") -> str:
    return f"Dịch vụ Calendar không khả dụng ({code})."


def handle_connect_calendar(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    del raw_args
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    return _call_google("handle_connect_calendar", principal_id)


def handle_calendar_status_cmd(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    del raw_args
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    return _call_google("handle_google_status", principal_id)


def handle_disconnect_calendar(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    return _call_google(
        "handle_disconnect_google", principal_id, {"target": raw_args.strip()}
    )
