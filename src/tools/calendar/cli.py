from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import sys

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

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


def _default_principal() -> str:
    from tools.composio.local_owner import load_local_owner

    owner_id = load_local_owner()
    if not owner_id:
        raise LookupError(
            "local_owner_binding_required: run Google setup or pass --principal-id"
        )
    return f"local:owner:{owner_id}"


def _add_principal_argument(parser: ArgumentParser) -> None:
    parser.add_argument("--principal-id", default=None)


def main() -> None:
    parser = ArgumentParser(description="Calendar CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    status_p = sub.add_parser("status")
    _add_principal_argument(status_p)

    list_p = sub.add_parser("list")
    _add_principal_argument(list_p)
    list_p.add_argument("--limit", type=int, default=10)
    list_p.add_argument("--account-email", default=None)

    free_p = sub.add_parser("free")
    _add_principal_argument(free_p)
    free_p.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    free_p.add_argument("--duration", type=int, default=30)
    free_p.add_argument("--account-email", default=None)
    free_p.add_argument("--timezone", dest="timezone_str", default=None)
    free_p.add_argument("--working-hours-start", default=None)
    free_p.add_argument("--working-hours-end", default=None)

    draft_p = sub.add_parser("draft")
    _add_principal_argument(draft_p)
    draft_p.add_argument("--summary", required=True)
    draft_p.add_argument("--start", required=True)
    draft_p.add_argument("--end", required=True)
    draft_p.add_argument("--location", default="")
    draft_p.add_argument("--account-email", default=None)

    confirm_p = sub.add_parser("confirm")
    _add_principal_argument(confirm_p)
    confirm_p.add_argument("--draft-id", required=True)

    args = parser.parse_args()
    principal_id = args.principal_id or _default_principal()
    svc = build_service()
    caller = SimpleNamespace(principal_id=principal_id)

    if args.cmd == "status":
        print(json.dumps(svc.status(caller), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        events = [
            asdict(
                event
            )
            for event in svc.list_events(
                caller,
                limit=args.limit,
                account_email=args.account_email,
            )
        ]
        print(json.dumps(events, ensure_ascii=False, indent=2))
    elif args.cmd == "free":
        slots = [
            asdict(slot)
            for slot in svc.find_free_slots(
                caller,
                args.date,
                args.duration,
                account_email=args.account_email,
                timezone_str=args.timezone_str,
                working_hours_start=args.working_hours_start,
                working_hours_end=args.working_hours_end,
            )
        ]
        print(json.dumps(slots, ensure_ascii=False, indent=2))
    elif args.cmd == "draft":
        draft = svc.create_draft_event(
            caller,
            args.summary,
            args.start,
            args.end,
            location=args.location,
            account_email=args.account_email,
        )
        print(json.dumps(asdict(draft), ensure_ascii=False, indent=2))
    elif args.cmd == "confirm":
        event = svc.confirm_event(caller, args.draft_id)
        print(json.dumps(asdict(event), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
