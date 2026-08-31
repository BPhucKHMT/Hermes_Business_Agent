from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tools.calendar.contracts import CalendarConnection, CalendarConnectionStatus
from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import load_calendar_policy
from tools.calendar.service import CalendarService
from tools.calendar.store import CalendarStore


def build_service() -> CalendarService:
    policy_path = _SRC / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)
    runtime_db = _SRC / ".runtime" / "calendar" / "calendar.sqlite3"
    store = CalendarStore(runtime_db)
    client = GoogleCalendarClient()
    return CalendarService(policy=policy, store=store, google_client=client)


def main() -> None:
    parser = ArgumentParser(description="Calendar CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    status_p = sub.add_parser("status")
    status_p.add_argument("--principal-id", default="telegram:default:operator")

    list_p = sub.add_parser("list")
    list_p.add_argument("--principal-id", default="telegram:default:operator")
    list_p.add_argument("--limit", type=int, default=10)

    free_p = sub.add_parser("free")
    free_p.add_argument("--principal-id", default="telegram:default:operator")
    free_p.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    free_p.add_argument("--duration", type=int, default=30)

    draft_p = sub.add_parser("draft")
    draft_p.add_argument("--principal-id", default="telegram:default:operator")
    draft_p.add_argument("--summary", required=True)
    draft_p.add_argument("--start", required=True)
    draft_p.add_argument("--end", required=True)
    draft_p.add_argument("--location", default="")

    confirm_p = sub.add_parser("confirm")
    confirm_p.add_argument("--principal-id", default="telegram:default:operator")
    confirm_p.add_argument("--draft-id", required=True)

    args = parser.parse_args()
    svc = build_service()
    caller = SimpleNamespace(principal_id=args.principal_id)

    if args.cmd == "status":
        print(json.dumps(svc.status(caller), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        events = [asdict(ev) for ev in svc.list_events(caller, limit=args.limit)]
        print(json.dumps(events, ensure_ascii=False, indent=2))
    elif args.cmd == "free":
        slots = [asdict(s) for s in svc.find_free_slots(caller, args.date, args.duration)]
        print(json.dumps(slots, ensure_ascii=False, indent=2))
    elif args.cmd == "draft":
        d = svc.create_draft_event(caller, args.summary, args.start, args.end, location=args.location)
        print(json.dumps(asdict(d), ensure_ascii=False, indent=2))
    elif args.cmd == "confirm":
        ev = svc.confirm_event(caller, args.draft_id)
        print(json.dumps(asdict(ev), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
