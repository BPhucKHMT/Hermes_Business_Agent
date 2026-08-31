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

from tools.youtube.policy import load_youtube_policy
from tools.youtube.service import YouTubeService
from tools.youtube.store import YouTubeStore
from tools.youtube.youtube_client import YouTubeClient


def build_service() -> YouTubeService:
    policy_path = _SRC / "config" / "youtube_policy.json"
    policy = load_youtube_policy(policy_path)
    runtime_db = _SRC / ".runtime" / "youtube" / "youtube.sqlite3"
    store = YouTubeStore(runtime_db)
    client = YouTubeClient()
    return YouTubeService(policy=policy, store=store, youtube_client=client)


def main() -> None:
    parser = ArgumentParser(description="YouTube CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    status_p = sub.add_parser("status")
    status_p.add_argument("--principal-id", default="telegram:default:operator")

    list_p = sub.add_parser("list")
    list_p.add_argument("--principal-id", default="telegram:default:operator")
    list_p.add_argument("--limit", type=int, default=10)

    draft_p = sub.add_parser("draft")
    draft_p.add_argument("--principal-id", default="telegram:default:operator")
    draft_p.add_argument("--title", required=True)
    draft_p.add_argument("--video-file", required=True)
    draft_p.add_argument("--description", default="")
    draft_p.add_argument("--privacy", default="unlisted")

    upload_p = sub.add_parser("upload")
    upload_p.add_argument("--principal-id", default="telegram:default:operator")
    upload_p.add_argument("--draft-id", required=True)

    args = parser.parse_args()
    svc = build_service()
    caller = SimpleNamespace(principal_id=args.principal_id)

    if args.cmd == "status":
        print(json.dumps(svc.get_channel_status(caller), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        videos = [asdict(v) for v in svc.list_videos(caller, limit=args.limit)]
        print(json.dumps(videos, ensure_ascii=False, indent=2))
    elif args.cmd == "draft":
        d = svc.create_draft_video(caller, args.title, args.video_file, description=args.description, privacy_status=args.privacy)
        print(json.dumps(asdict(d), ensure_ascii=False, indent=2))
    elif args.cmd == "upload":
        v = svc.upload_draft_video(caller, args.draft_id)
        print(json.dumps(asdict(v), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
