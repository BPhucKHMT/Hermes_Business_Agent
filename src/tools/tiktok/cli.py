from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tools.tiktok.policy import load_tiktok_policy
from tools.tiktok.service import TikTokService
from tools.tiktok.store import TikTokStore
from tools.tiktok.tiktok_client import TikTokClient


def build_service() -> TikTokService:
    policy_path = _SRC / "config" / "tiktok_policy.json"
    policy = load_tiktok_policy(policy_path)
    runtime_db = _SRC / ".runtime" / "tiktok" / "tiktok.sqlite3"
    store = TikTokStore(runtime_db)
    client = TikTokClient()
    return TikTokService(policy=policy, store=store, tiktok_client=client)


def main() -> None:
    parser = ArgumentParser(description="TikTok CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    status_p = sub.add_parser("creator")
    status_p.add_argument("--principal-id", default="telegram:default:operator")

    draft_p = sub.add_parser("draft")
    draft_p.add_argument("--principal-id", default="telegram:default:operator")
    draft_p.add_argument("--caption", required=True)
    draft_p.add_argument("--video-file", required=True)
    draft_p.add_argument("--privacy", default="SELF_ONLY")

    pub_p = sub.add_parser("publish")
    pub_p.add_argument("--principal-id", default="telegram:default:operator")
    pub_p.add_argument("--draft-id", required=True)

    check_p = sub.add_parser("status")
    check_p.add_argument("--principal-id", default="telegram:default:operator")
    check_p.add_argument("--publish-id", required=True)

    args = parser.parse_args()
    svc = build_service()
    caller = SimpleNamespace(principal_id=args.principal_id)

    if args.cmd == "creator":
        print(json.dumps(svc.get_creator_status(caller), ensure_ascii=False, indent=2))
    elif args.cmd == "draft":
        d = svc.create_draft_post(caller, args.caption, args.video_file, privacy_level=args.privacy)
        print(json.dumps(asdict(d), ensure_ascii=False, indent=2))
    elif args.cmd == "publish":
        res = svc.publish_draft_post(caller, args.draft_id)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.cmd == "status":
        st = svc.get_post_status(caller, args.publish_id)
        print(json.dumps(asdict(st), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
