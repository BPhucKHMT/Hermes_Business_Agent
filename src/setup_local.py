"""Configure one deployed workspace for native Hermes CLI/Desktop Google use."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from tools.composio.local_owner import ensure_local_owner


PROJECT_PLUGINS = ("email-connector", "calendar-connector")


class SetupError(RuntimeError):
    """Raised when a local setup prerequisite or command fails."""


def _resolve_executable(name: str, install_hint: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
    if name == "uv":
        for candidate in (
            Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv"),
            Path.home() / ".cargo" / "bin" / ("uv.exe" if os.name == "nt" else "uv"),
        ):
            if candidate.is_file():
                return str(candidate)
    raise SetupError(f"{name} was not found on PATH. {install_hint}")


def _command(executable: str, arguments: Sequence[str]) -> list[str]:
    if os.name == "nt" and Path(executable).suffix.lower() in {".bat", ".cmd"}:
        return ["cmd.exe", "/d", "/c", executable, *arguments]
    return [executable, *arguments]


def _run_hermes(
    executable: str,
    arguments: Sequence[str],
    root: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            _command(executable, arguments),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise SetupError(
            "Unable to execute native Hermes. Check the PATH entry and "
            "operator permissions."
        ) from exc
    if result.returncode:
        command = " ".join(("hermes", *arguments))
        raise SetupError(
            f"Hermes command failed (exit {result.returncode}): {command}. "
            "Check the native Hermes installation and operator permissions."
        )
    return result


def _read_external_dirs(
    executable: str,
    root: Path,
) -> list[str]:
    result = _run_hermes(
        executable,
        ("config", "get", "skills.external_dirs", "--json"),
        root,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError(
            "Hermes returned invalid JSON for skills.external_dirs; "
            "repair the native config and run setup again."
        ) from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SetupError(
            "Hermes skills.external_dirs is not a list of paths; "
            "repair the native config and run setup again."
        )
    return value


def _is_same_path(value: str, target: Path, root: Path) -> bool:
    candidate = Path(os.path.expanduser(value))
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve() == target.resolve()
    except OSError:
        return os.path.normcase(str(candidate)) == os.path.normcase(str(target))


def _merge_skill_directory(
    existing: list[str], skills_dir: Path, root: Path
) -> list[str]:
    if any(_is_same_path(item, skills_dir, root) for item in existing):
        return existing
    return [*existing, str(skills_dir)]


def _provision_owner(root: Path) -> str:
    try:
        owner_id = ensure_local_owner(root)
    except LookupError as exc:
        raise SetupError(
            "Local owner binding is malformed; remove it only after confirming "
            "the installation owner and rerun setup."
        ) from exc
    if not owner_id:
        raise SetupError("Local owner provisioning returned no owner id; setup stopped.")
    return owner_id


def _configure_hermes(executable: str, root: Path) -> None:
    external_dirs = _merge_skill_directory(
        _read_external_dirs(executable, root),
        root / "skills",
        root,
    )
    config_values = (
        ("terminal.cwd", str(root)),
        ("skills.external_dirs", json.dumps(external_dirs, separators=(",", ":"))),
        ("HERMES_PROJECT_SRC", str(root)),
        ("HERMES_ENABLE_PROJECT_PLUGINS", "1"),
    )
    for key, value in config_values:
        _run_hermes(executable, ("config", "set", key, value), root)


def _enable_project_plugins(executable: str, root: Path) -> None:
    for plugin in PROJECT_PLUGINS:
        _run_hermes(
            executable,
            ("plugins", "enable", plugin, "--no-allow-tool-override"),
            root,
        )

def _sync_plugins(root: Path) -> None:
    source_dir = root / ".hermes" / "plugins"
    if not source_dir.is_dir():
        return
    target_dirs: list[Path] = []
    if os.environ.get("HERMES_HOME"):
        target_dirs.append(Path(os.environ["HERMES_HOME"]) / "plugins")
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        target_dirs.append(Path(os.environ["LOCALAPPDATA"]) / "hermes" / "plugins")
    target_dirs.append(Path.home() / ".hermes" / "plugins")

    seen: set[str] = set()
    for target_base in target_dirs:
        norm = os.path.normcase(str(target_base.resolve())) if target_base.exists() else str(target_base)
        if norm in seen:
            continue
        seen.add(norm)
        if target_base.parent.exists():
            target_base.mkdir(parents=True, exist_ok=True)
            for plugin_dir in source_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                dst_p = target_base / plugin_dir.name
                shutil.copytree(plugin_dir, dst_p, dirs_exist_ok=True)
                for pycache in dst_p.rglob("__pycache__"):
                    if pycache.is_dir():
                        shutil.rmtree(pycache, ignore_errors=True)

def configure_local(root: Path) -> str:
    """Provision the local owner and configure native Hermes for this workspace."""
    root = root.resolve()
    if not (root / "skills").is_dir():
        raise SetupError(
            f"Deployed Hermes workspace has no skills directory: {root}"
        )

    _resolve_executable(
        "uv",
        "Install uv from "
        "https://docs.astral.sh/uv/getting-started/installation/",
    )
    hermes = _resolve_executable(
        "hermes",
        "Install Hermes Agent using its official instructions, then retry setup.",
    )
    owner_id = _provision_owner(root)
    _configure_hermes(hermes, root)
    _sync_plugins(root)
    _enable_project_plugins(hermes, root)
    return owner_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Opt in this deployed Hermes workspace to local Google mode."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Provision the installation owner and configure native Hermes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.local:
        print("Refusing to change Hermes configuration without explicit --local.", file=sys.stderr)
        return 2
    try:
        configure_local(Path(__file__).resolve().parent)
    except SetupError as exc:
        print(f"Local setup failed: {exc}", file=sys.stderr)
        return 1
    print("Local Hermes mode configured for this deployed workspace.")
    print("Next: add COMPOSIO_API_KEY to the native Hermes operator environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
