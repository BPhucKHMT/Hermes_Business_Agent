from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"


def layer_1() -> None:
    # Required runtime documents; authorization behavior is checked in Layer 2.
    skill_file = SRC / "skills/email/SKILL.md"
    assert skill_file.is_file(), "skills/email/SKILL.md must exist"

    # 2. Config & schema validation
    policy_file = SRC / "config/email_policy.json"
    assert policy_file.is_file(), "config/email_policy.json must exist"
    policy_data = json.loads(policy_file.read_text(encoding="utf-8"))
    assert policy_data["schema_version"] == 1
    assert policy_data["gmail_scopes"] == [
        "https://www.googleapis.com/auth/gmail.readonly"
    ]

    # 3. Feature list validation
    feature_file = ROOT / "feature-list.json"
    assert feature_file.is_file()
    features = json.loads(feature_file.read_text(encoding="utf-8"))
    assert features["schema_version"] == 1
    assert sum(f["state"] == "active" for f in features["features"]) <= features["wip_limit"]

    print("email intake layer 1: pass")


def layer_2() -> None:
    # Run all focused test suites in tests/email
    tests_dir = ROOT / "tests/email"
    test_files = sorted([str(f) for f in tests_dir.glob("test_*.py")])

    basetemp_dir = ROOT / ".runtime/tmp/pytest_tmp"
    basetemp_dir.mkdir(parents=True, exist_ok=True)
    venv_py = SRC / ".venv" / "Scripts" / "python.exe"
    py_exec = str(venv_py) if venv_py.is_file() else sys.executable
    cmd = [
        py_exec,
        "-m",
        "pytest",
        "-p",
        "no:trio",
        "-p",
        "no:anyio",
        "--basetemp",
        str(basetemp_dir),
        "-q",
    ] + test_files
    env = dict(os.environ)
    sep = ";" if sys.platform == "win32" else ":"
    env["PYTHONPATH"] = (
        f"{SRC}{sep}{PLUGIN}{sep}{UPSTREAM}{sep}{env.get('PYTHONPATH', '')}"
    )

    proc = subprocess.run(
        cmd, cwd=str(SRC), env=env, capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        print(f"STDOUT:\n{proc.stdout}")
        print(f"STDERR:\n{proc.stderr}")
        raise RuntimeError("Layer 2 test suites failed")

    print(proc.stdout.strip())
    print("email intake layer 2: pass")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Email Intake Layer Gates")
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()

    if args.layer == 1:
        layer_1()
    else:
        layer_2()


if __name__ == "__main__":
    main()
