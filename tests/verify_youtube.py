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
PLUGIN = SRC / ".hermes" / "plugins" / "youtube-connector"
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
        SRC / "config/youtube_policy.json",
        SRC / "tools/youtube/contracts.py",
        SRC / "tools/youtube/policy.py",
        SRC / "tools/youtube/youtube_client.py",
        SRC / "tools/youtube/store.py",
        SRC / "tools/youtube/service.py",
        PLUGIN / "plugin.yaml",
        PLUGIN / "youtube_schemas.py",
        PLUGIN / "youtube_caller.py",
        PLUGIN / "youtube_guard.py",
        PLUGIN / "youtube_client_plugin.py",
        PLUGIN / "youtube_plugin_tools.py",
        PLUGIN / "__init__.py",
        SRC / "skills/youtube/SKILL.md",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing youtube files: {missing}"

    # Verify policy schema
    policy = json.loads(required[0].read_text(encoding="utf-8"))
    assert policy["schema_version"] == 1
    assert "https://www.googleapis.com/auth/youtube.upload" in policy["scopes"]

    schemas = load_module("youtube_schemas", PLUGIN / "youtube_schemas.py")
    expected_tools = {
        "youtube_channel_status",
        "youtube_list_videos",
        "youtube_create_draft_video",
        "youtube_upload_video",
        "youtube_update_video_metadata",
    }
    actual_tools = {
        schemas.YOUTUBE_CHANNEL_STATUS_SCHEMA["name"],
        schemas.YOUTUBE_LIST_VIDEOS_SCHEMA["name"],
        schemas.YOUTUBE_CREATE_DRAFT_VIDEO_SCHEMA["name"],
        schemas.YOUTUBE_UPLOAD_VIDEO_SCHEMA["name"],
        schemas.YOUTUBE_UPDATE_METADATA_SCHEMA["name"],
    }
    assert actual_tools == expected_tools

    # Verify skill text
    skill = (SRC / "skills/youtube/SKILL.md").read_text(encoding="utf-8").lower()
    for phrase in ("tier 2", "youtube_create_draft_video", "youtube_upload_video", "channel"):
        assert phrase in skill, f"missing phrase in youtube skill: {phrase}"

    # Verify AGENTS capability
    agents_txt = (SRC / "AGENTS.md").read_text(encoding="utf-8")
    assert "/youtube" in agents_txt

    print("youtube layer 1: pass")


def layer_2() -> None:
    runtime = ROOT / ".runtime" / "tmp"
    runtime.mkdir(parents=True, exist_ok=True)
    basetemp = Path(tempfile.mkdtemp(prefix="youtube-pytest-", dir=runtime))
    env = dict(os.environ)
    separator = os.pathsep
    env["PYTHONPATH"] = separator.join((str(SRC), str(PLUGIN), str(UPSTREAM), env.get("PYTHONPATH", "")))

    uv_path = Path("C:/Users/ADMIN/.local/bin/uv.exe")
    if uv_path.is_file():
        command = [str(uv_path), "run", "--frozen", "python", "-m", "pytest", str(ROOT / "tests/youtube_tool"), "-q", "--basetemp", str(basetemp)]
    else:
        command = [sys.executable, "-m", "pytest", str(ROOT / "tests/youtube_tool"), "-q", "--basetemp", str(basetemp)]

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
    print("youtube layer 2: pass")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
