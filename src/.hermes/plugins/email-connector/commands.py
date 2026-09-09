from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

from caller import DM_REDIRECT_TEXT, DmOnlyError


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


_composio_bridge = None
try:
    from tools.composio import bridge as _composio_bridge
except (ImportError, ModuleNotFoundError):
    for _cand in _candidate_src_dirs():
        _target = _cand / "tools" / "composio" / "bridge.py"
        if _target.is_file():
            _src_dir = str(_cand.resolve())
            if _src_dir not in sys.path:
                sys.path.insert(0, _src_dir)
            _spec = importlib.util.spec_from_file_location("tools.composio.bridge", str(_target))
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                sys.modules["tools.composio.bridge"] = _mod
                _spec.loader.exec_module(_mod)
                _composio_bridge = _mod
                break


def _call_google(
    operation: str,
    principal_id: str,
    params: dict | None = None,
) -> Any:
    bridge = sys.modules.get("tools.composio.bridge") or _composio_bridge
    if bridge is None or not hasattr(bridge, "call_google"):
        raise RuntimeError("call_google bridge unavailable; run python src/setup_local.py --local")
    return bridge.call_google(operation, principal_id, params)


def _unavailable(code: str = "connector_unavailable") -> str:
    return f"Dịch vụ Gmail không khả dụng ({code})."


def handle_connect_gmail(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    del raw_args
    if client is None or getattr(client, "configured", True) is False:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    if hasattr(client, "calls"):
        response = client.start_oauth(caller)
        url = (
            response.get("result", {}).get("authorization_url")
            if response.get("ok")
            else None
        )
        if not url:
            return _unavailable(response.get("error", {}).get("code", "oauth_start_failed"))
        return f"Mở liên kết này để kết nối Google (Gmail, Calendar, YouTube): {url}"

    return _call_google("handle_connect_google", principal_id)


def handle_mail_status(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    del raw_args
    if client is None or getattr(client, "configured", True) is False:
        return _unavailable()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    if hasattr(client, "calls"):
        response = client.connections(caller)
        if not response.get("ok"):
            return _unavailable(response.get("error", {}).get("code", "status_failed"))
        return json.dumps(response["result"], ensure_ascii=False)

    return _call_google("handle_google_status", principal_id)


def handle_disconnect_gmail(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    if client is None or getattr(client, "configured", True) is False:
        return _unavailable()
    parts = raw_args.split()
    try:
        caller = _caller(registry)
        principal_id = _principal_id(caller)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    if hasattr(client, "calls") and len(parts) == 1:
        response = client.disconnect(caller, parts[0])
        if not response.get("ok"):
            return _unavailable(
                response.get("error", {}).get("code", "disconnect_failed")
            )
        result = response.get("result", {})
        if result.get("status") != "revoked":
            return _unavailable("disconnect_not_confirmed")
        return json.dumps(result, ensure_ascii=False)

    target = parts[0] if parts else ""
    return _call_google("handle_disconnect_google", principal_id, {"target": target})

def handle_share_mailbox(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    parts = raw_args.split()
    if len(parts) not in (2, 3):
        return "Cần: <mã_kết_nối> <chat_id> [thread_id]."
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    response = client.propose_grant(
        caller,
        parts[0],
        parts[1],
        parts[2] if len(parts) == 3 else None,
    )
    if not response.get("ok"):
        return _unavailable(
            response.get("error", {}).get("code", "grant_proposal_failed")
        )
    result = response.get("result", {})
    if result.get("status") != "pending" or not result.get("request_id"):
        return _unavailable("grant_proposal_not_confirmed")
    return json.dumps(result, ensure_ascii=False)


def handle_email_grant(
    raw_args: str = "",
    *,
    client: Any = None,
    registry: Any = None,
) -> str:
    parts = raw_args.split()
    if len(parts) != 2 or parts[1] not in ("approve", "deny"):
        return "Cần: <mã_yêu_cầu> approve|deny."
    if client is None:
        return _unavailable()
    try:
        caller = _caller(registry)
    except DmOnlyError:
        return DM_REDIRECT_TEXT
    except LookupError as exc:
        return _unavailable(str(exc))

    response = client.decide_grant(caller, parts[0], parts[1])
    if not response.get("ok"):
        return _unavailable(
            response.get("error", {}).get("code", "grant_resolution_failed")
        )
    result = response.get("result", {})
    if result.get("status") not in ("approved", "denied"):
        return _unavailable("grant_resolution_not_confirmed")
    return json.dumps(result, ensure_ascii=False)
