from argparse import ArgumentParser
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes" / "plugins" / "calendar-connector"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "hermes-agent"


def load_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def layer_1() -> None:
    required = (
        SRC / "config/calendar_policy.json",
        SRC / "tools/calendar/contracts.py",
        SRC / "tools/calendar/policy.py",
        SRC / "tools/calendar/google_calendar.py",
        SRC / "tools/calendar/store.py",
        SRC / "tools/calendar/service.py",
        SRC / "tools/calendar/cli.py",
        PLUGIN / "plugin.yaml",
        PLUGIN / "calendar_schemas.py",
        PLUGIN / "calendar_caller.py",
        PLUGIN / "calendar_guard.py",
        PLUGIN / "calendar_client.py",
        PLUGIN / "calendar_plugin_tools.py",
        PLUGIN / "calendar_commands.py",
        PLUGIN / "__init__.py",
        SRC / "skills/calendar/SKILL.md",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing calendar files: {missing}"

    # Verify policy schema
    policy = json.loads(required[0].read_text(encoding="utf-8"))
    assert policy["schema_version"] == 1
    assert "working_hours" in policy
    assert "https://www.googleapis.com/auth/calendar.events" in policy["scopes"]

    # Verify schemas
    schemas = load_module("calendar_schemas", PLUGIN / "calendar_schemas.py")
    expected_tools = {
        "calendar_list_events",
        "calendar_find_free_slots",
        "calendar_create_draft_event",
        "calendar_confirm_event",
        "calendar_status",
    }
    actual_tools = {
        schemas.CALENDAR_LIST_EVENTS_SCHEMA["name"],
        schemas.CALENDAR_FIND_FREE_SLOTS_SCHEMA["name"],
        schemas.CALENDAR_CREATE_DRAFT_EVENT_SCHEMA["name"],
        schemas.CALENDAR_CONFIRM_EVENT_SCHEMA["name"],
        schemas.CALENDAR_STATUS_SCHEMA["name"],
    }
    assert actual_tools == expected_tools

    # Verify skill text
    skill = (SRC / "skills/calendar/SKILL.md").read_text(encoding="utf-8").lower()
    for phrase in ("tier 2", "calendar_create_draft_event", "calendar_confirm_event", "free slot"):
        assert phrase in skill, f"missing phrase in calendar skill: {phrase}"
    # Verify AGENTS capability
    agents_txt = (SRC / "AGENTS.md").read_text(encoding="utf-8")
    assert "/calendar" in agents_txt

    print("calendar layer 1: pass")


def layer_2() -> None:
    runtime = ROOT / ".runtime" / "tmp"
    runtime.mkdir(parents=True, exist_ok=True)
    basetemp = Path(tempfile.mkdtemp(prefix="calendar-pytest-", dir=runtime))
    env = dict(os.environ)
    separator = os.pathsep
    env["PYTHONPATH"] = separator.join((str(SRC), str(PLUGIN), str(UPSTREAM), env.get("PYTHONPATH", "")))

    import shutil
    uv_candidate = shutil.which("uv") or (str(Path.home() / ".local/bin/uv") if (Path.home() / ".local/bin/uv").is_file() else ("C:/Users/ADMIN/.local/bin/uv.exe" if Path("C:/Users/ADMIN/.local/bin/uv.exe").is_file() else None))
    targets = [str(ROOT / "tests/google_calendar"), str(ROOT / "tests/test_calendar_e2e.py")]
    if uv_candidate:
        command = [str(uv_candidate), "run", "--frozen", "python", "-m", "pytest", *targets, "-q", "--basetemp", str(basetemp)]
    else:
        command = [sys.executable, "-m", "pytest", *targets, "-q", "--basetemp", str(basetemp)]
    completed = subprocess.run(
        command,
        cwd=SRC,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print("calendar layer 2: pass")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
