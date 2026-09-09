from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
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
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env" if os.name == "nt" else None,
    ):
        if env_file and env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("HERMES_PROJECT_SRC="):
                        val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        if val and (Path(val) / "tools").is_dir():
                            candidates.append(Path(val))
            except OSError:
                pass
    for cwd_cand in (Path.cwd() / "src", Path.cwd()):
        if (cwd_cand / "tools").is_dir():
            candidates.append(cwd_cand)
    return candidates


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
    for candidate in _candidate_src_dirs():
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
