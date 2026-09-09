"""Run Google dependencies in the project interpreter, not Hermes's venv."""

import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def call_google(operation: str, principal_id: str, params: dict | None = None):
    """Return the domain result; caller identity comes from the host guard."""
    if not principal_id or not principal_id.strip():
        raise ValueError("Google operation requires a bound caller")
    if os.environ.get("HERMES_FORCE_GOOGLE_BRIDGE") != "1":
        inprocess_dispatch = None
        try:
            import composio  # noqa: F401
            import tools

            tools_path = str(Path(__file__).resolve().parents[1])
            if hasattr(tools, "__path__") and tools_path not in tools.__path__:
                tools.__path__.insert(0, tools_path)

            from tools.composio.worker import dispatch as inprocess_dispatch
        except (ImportError, ModuleNotFoundError):
            inprocess_dispatch = None

        if inprocess_dispatch is not None:
            return inprocess_dispatch(
                {"operation": operation, "principal_id": principal_id, "params": params or {}}
            )
    uv = shutil.which("uv")
    if not uv:
        for candidate in (
            Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv"),
            Path.home() / ".cargo" / "bin" / ("uv.exe" if os.name == "nt" else "uv"),
        ):
            if candidate.is_file():
                uv = str(candidate)
                break
    if not uv:
        raise RuntimeError("uv is unavailable; install uv and run setup --local")
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    env["PYTHONIOENCODING"] = "utf-8"
    request = {"operation": operation, "principal_id": principal_id, "params": params or {}}
    try:
        completed = subprocess.run(
            [uv, "run", "--project", str(ROOT), "--frozen", "--no-sync",
             "python", "-m", "tools.composio.worker"],
            input=json.dumps(request), capture_output=True, text=True,
            encoding="utf-8", cwd=ROOT, env=env, timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Google operation timed out; verify its outcome before retrying") from exc
    try:
        response = json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Google project worker unavailable; run the project setup") from exc
    if not isinstance(response, dict) or "ok" not in response:
        raise RuntimeError("Google project worker returned an invalid response")
    if not response["ok"]:
        error = response.get("error", {})
        error_type = {"ValueError": ValueError, "LookupError": LookupError,
                      "KeyError": LookupError, "PermissionError": PermissionError}
        raise error_type.get(error.get("type"), RuntimeError)(
            error.get("message") or "Google operation failed"
        )
    if completed.returncode:
        raise RuntimeError("Google project worker exited unsuccessfully")
    return response["result"]
