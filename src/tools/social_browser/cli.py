from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil

from tools.social_browser.gateway import SafeBrowserGateway
from tools.social_browser.harness import BrowserHarnessRunner
from tools.social_browser.policy import load_policy
from tools.social_browser.service import PrepareFacebookRequest, SocialBrowserService
from tools.social_browser.store import SocialBrowserStore


SRC = Path(__file__).resolve().parents[2]
RUNTIME = SRC / ".runtime" / "social-browser"


def _resolve_browser_harness() -> str:
    configured = os.environ.get(
        "SOCIAL_BROWSER_HARNESS_EXECUTABLE", ""
    ).strip()
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("SOCIAL_BROWSER_HARNESS_EXECUTABLE is invalid")
        return str(path)
    discovered = shutil.which("browser-harness")
    if discovered:
        return discovered
    executable_name = (
        "browser-harness.exe" if os.name == "nt" else "browser-harness"
    )
    fallback = Path.home() / ".local" / "bin" / executable_name
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("browser-harness executable not found")


def build_service() -> SocialBrowserService:
    cdp_url = os.environ.get("SOCIAL_BROWSER_CDP_URL", "").strip()
    workspace_value = os.environ.get("BH_AGENT_WORKSPACE", "").strip()
    if not cdp_url:
        raise RuntimeError("SOCIAL_BROWSER_CDP_URL is required")
    if not workspace_value:
        raise RuntimeError("BH_AGENT_WORKSPACE is required")
    workspace = Path(workspace_value).expanduser().resolve()
    if not workspace.is_relative_to(SRC.resolve()):
        raise RuntimeError("BH_AGENT_WORKSPACE must be inside deployed src")
    policy = load_policy(SRC / "config" / "social_browser_policy.json")
    harness_executable = _resolve_browser_harness()
    store = SocialBrowserStore(RUNTIME / "social_browser.sqlite3")

    def gateway_factory(run_id: str) -> SafeBrowserGateway:
        runner = BrowserHarnessRunner(
            workspace, cdp_url, executable=harness_executable
        )
        return SafeBrowserGateway(policy, "facebook-personal", runner, run_id)

    return SocialBrowserService(policy, store, gateway_factory)


def _result_json(result) -> str:
    data = asdict(result)
    data["status"] = result.status.value
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def main() -> None:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--account-label", required=True)
    prepare.add_argument("--text", default="")
    prepare.add_argument("--media", action="append", default=[])
    prepare.add_argument("--audience", choices=("friends", "only-me"), required=True)

    status = subparsers.add_parser("status")
    status.add_argument("run_id")

    verify = subparsers.add_parser("verify")
    verify.add_argument("run_id")

    args = parser.parse_args()
    service = build_service()
    if args.command == "prepare":
        result = service.prepare(
            PrepareFacebookRequest(
                account_label=args.account_label,
                text=args.text,
                media_paths=tuple(Path(path) for path in args.media),
                audience=args.audience,
            )
        )
    elif args.command == "status":
        result = service.status(args.run_id)
    else:
        result = service.verify_after_human(args.run_id)
    print(_result_json(result))


if __name__ == "__main__":
    main()
