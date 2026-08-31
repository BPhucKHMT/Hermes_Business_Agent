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
PLUGIN = SRC / ".hermes" / "plugins" / "social-browser-assist"
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
        PLUGIN / "plugin.yaml",
        PLUGIN / "social_schemas.py",
        PLUGIN / "social_plugin_tools.py",
        PLUGIN / "social_caller.py",
        PLUGIN / "social_guard.py",
        PLUGIN / "social_client.py",
        PLUGIN / "__init__.py",
        SRC / "skills/social-browser-assist/SKILL.md",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing social browser files: {missing}"

    manifest = required[0].read_text(encoding="utf-8")
    assert "social_connection_status" in manifest
    assert "social_prepare_facebook_post" not in manifest
    assert "social_browser_status" not in manifest
    assert "social_verify_facebook_post" not in manifest
    env_example = (SRC / ".env.example").read_text(encoding="utf-8")
    for value in (
        "SOCIAL_BROWSER_FACEBOOK_ACCOUNT_LABEL",
        "SOCIAL_BROWSER_ALLOWED_TELEGRAM_USERS",
        "SOCIAL_BROWSER_CDP_URL",
    ):
        assert value not in env_example

    schemas = load_module(
        "hermes_social_browser_assist.social_schemas",
        PLUGIN / "social_schemas.py",
    )
    assert schemas.SOCIAL_CONNECTION_STATUS_SCHEMA["name"] == (
        "social_connection_status"
    )
    assert schemas.SOCIAL_CONNECTION_STATUS_SCHEMA["parameters"]["properties"] == {}
    skill = (SRC / "skills/social-browser-assist/SKILL.md").read_text(
        encoding="utf-8"
    ).lower()
    for phrase in (
        "telegram is the customer gateway",
        "personal-profile publishing is disabled",
        "passwords",
        "future scope",
    ):
        assert phrase in skill, f"missing skill boundary: {phrase}"
    print("social browser layer 1: pass")



def layer_2() -> None:
    runtime = ROOT / ".runtime" / "tmp"
    runtime.mkdir(parents=True, exist_ok=True)
    basetemp = Path(tempfile.mkdtemp(prefix="social-browser-pytest-", dir=runtime))
    env = dict(os.environ)
    separator = os.pathsep
    env["PYTHONPATH"] = separator.join(
        (str(SRC), str(PLUGIN), str(UPSTREAM), env.get("PYTHONPATH", ""))
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(ROOT / "tests/social_browser"),
        "-q",
        "--basetemp",
        str(basetemp),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
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
    print("social browser layer 2: pass")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    arguments = parser.parse_args()
    (layer_1 if arguments.layer == 1 else layer_2)()
