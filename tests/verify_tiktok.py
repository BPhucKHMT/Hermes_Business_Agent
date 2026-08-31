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
PLUGIN = SRC / ".hermes" / "plugins" / "tiktok-connector"
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
        SRC / "config/tiktok_policy.json",
        SRC / "tools/tiktok/contracts.py",
        SRC / "tools/tiktok/policy.py",
        SRC / "tools/tiktok/tiktok_client.py",
        SRC / "tools/tiktok/store.py",
        SRC / "tools/tiktok/service.py",
        SRC / "tools/tiktok/cli.py",
        SRC / "tools/tiktok/__init__.py",
        PLUGIN / "plugin.yaml",
        PLUGIN / "schemas.py",
        PLUGIN / "caller.py",
        PLUGIN / "guard.py",
        PLUGIN / "client.py",
        PLUGIN / "plugin_tools.py",
        PLUGIN / "__init__.py",
        SRC / "skills/tiktok/SKILL.md",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing tiktok files: {missing}"

    # Verify policy schema
    policy = json.loads(required[0].read_text(encoding="utf-8"))
    assert policy["schema_version"] == 1
    assert "video.publish" in policy["scopes"]

    # Verify schemas
    schemas = load_module("tiktok_schemas", PLUGIN / "schemas.py")
    expected_tools = {
        "tiktok_creator_info",
        "tiktok_create_draft_post",
        "tiktok_publish_video",
        "tiktok_post_status",
    }
    actual_tools = {
        schemas.TIKTOK_CREATOR_INFO_SCHEMA["name"],
        schemas.TIKTOK_CREATE_DRAFT_POST_SCHEMA["name"],
        schemas.TIKTOK_PUBLISH_VIDEO_SCHEMA["name"],
        schemas.TIKTOK_POST_STATUS_SCHEMA["name"],
    }
    assert actual_tools == expected_tools

    # Verify skill text
    skill = (SRC / "skills/tiktok/SKILL.md").read_text(encoding="utf-8").lower()
    for phrase in ("tier 2", "tiktok_create_draft_post", "tiktok_publish_video", "creator"):
        assert phrase in skill, f"missing phrase in tiktok skill: {phrase}"

    # Verify AGENTS capability
    agents_txt = (SRC / "AGENTS.md").read_text(encoding="utf-8")
    assert "/tiktok" in agents_txt

    print("tiktok layer 1: pass")


def layer_2() -> None:
    runtime = ROOT / ".runtime" / "tmp"
    runtime.mkdir(parents=True, exist_ok=True)
    basetemp = Path(tempfile.mkdtemp(prefix="tiktok-pytest-", dir=runtime))
    env = dict(os.environ)
    separator = os.pathsep
    env["PYTHONPATH"] = separator.join((str(SRC), str(PLUGIN), str(UPSTREAM), env.get("PYTHONPATH", "")))

    uv_path = Path("C:/Users/ADMIN/.local/bin/uv.exe")
    if uv_path.is_file():
        command = [str(uv_path), "run", "--frozen", "python", "-m", "pytest", str(ROOT / "tests/tiktok_tool"), "-q", "--basetemp", str(basetemp)]
    else:
        command = [sys.executable, "-m", "pytest", str(ROOT / "tests/tiktok_tool"), "-q", "--basetemp", str(basetemp)]

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
    print("tiktok layer 2: pass")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
