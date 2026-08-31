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
        SRC / "config/social_browser_policy.json",
        SRC / "tools/social_browser/contracts.py",
        SRC / "tools/social_browser/policy.py",
        SRC / "tools/social_browser/store.py",
        SRC / "tools/social_browser/harness.py",
        SRC / "tools/social_browser/gateway.py",
        SRC / "tools/social_browser/facebook.py",
        SRC / "tools/social_browser/service.py",
        SRC / "tools/social_browser/cli.py",
        PLUGIN / "plugin.yaml",
        PLUGIN / "social_schemas.py",
        PLUGIN / "social_plugin_tools.py",
        PLUGIN / "social_caller.py",
        PLUGIN / "social_guard.py",
        PLUGIN / "social_client.py",
        PLUGIN / "__init__.py",
        SRC / "skills/social-browser-assist/SKILL.md",
        SRC / ".hermes/browser-harness-workspace/agent_helpers.py",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing social browser files: {missing}"

    policy = json.loads(required[0].read_text(encoding="utf-8"))
    assert policy["schema_version"] == 1
    assert policy["browser_harness_version"] == "0.1.10"
    assert policy["telemetry"] is False and policy["cloud"] is False
    platform = policy["platforms"]["facebook-personal"]
    assert platform["origins"] == ["https://www.facebook.com"]
    assert "handoff" in platform["allowed_operations"]
    assert not set(("post", "publish", "schedule", "send")) & set(
        platform["allowed_operations"]
    )

    setup_cmd = (SRC / "setup.cmd").read_text(encoding="utf-8")
    setup_sh = (SRC / "setup.sh").read_text(encoding="utf-8")
    for setup in (setup_cmd, setup_sh):
        assert "browser-harness==0.1.10" in setup
    env_example = (SRC / ".env.example").read_text(encoding="utf-8")
    for value in (
        "BH_TELEMETRY=0",
        "BH_AGENT_WORKSPACE=",
        "SOCIAL_BROWSER_HARNESS_EXECUTABLE=",
        "SOCIAL_BROWSER_CDP_URL=http://127.0.0.1:9222",
        "SOCIAL_BROWSER_ALLOWED_TELEGRAM_USERS=",
    ):
        assert value in env_example, f"missing env contract: {value}"

    features = json.loads((ROOT / "feature-list.json").read_text(encoding="utf-8"))
    active = [item["id"] for item in features["features"] if item["state"] == "active"]
    assert active in ([], ["H012"]), active
    h012 = next(item for item in features["features"] if item["id"] == "H012")
    assert h012["state"] in {"active", "blocked"}
    assert h012["evidence"] is None

    schemas = load_module("hermes_social_browser_assist.social_schemas", PLUGIN / "social_schemas.py")
    schemas_by_name = {
        schema["name"]: schema
        for schema in (
            schemas.SOCIAL_PREPARE_SCHEMA,
            schemas.SOCIAL_STATUS_SCHEMA,
            schemas.SOCIAL_VERIFY_SCHEMA,
        )
    }
    assert set(schemas_by_name) == {
        "social_prepare_facebook_post",
        "social_browser_status",
        "social_verify_facebook_post",
    }
    properties = schemas.SOCIAL_PREPARE_SCHEMA["parameters"]["properties"]
    assert set(properties) == {"account_label", "text", "media_paths", "audience"}
    forbidden_fields = {"publish", "auto_publish", "url", "selector", "code", "coordinates"}
    assert forbidden_fields.isdisjoint(properties)

    manifest = (PLUGIN / "plugin.yaml").read_text(encoding="utf-8")
    for tool_name in schemas_by_name:
        assert f"  - {tool_name}" in manifest
    skill = (SRC / "skills/social-browser-assist/SKILL.md").read_text(
        encoding="utf-8"
    ).lower()
    for phrase in (
        "never click",
        "user must",
        "ready_for_human",
        "youtube or tiktok",
        "only completion evidence",
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
