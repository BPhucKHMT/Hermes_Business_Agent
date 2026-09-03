from argparse import ArgumentParser
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
COMPOSIO_DIR = SRC / "tools" / "composio"


def layer_1() -> None:
    required_files = (
        COMPOSIO_DIR / "__init__.py",
        COMPOSIO_DIR / "client.py",
        COMPOSIO_DIR / "auth.py",
        COMPOSIO_DIR / "mail_tools.py",
        COMPOSIO_DIR / "calendar_tools.py",
        COMPOSIO_DIR / "commands.py",
        ROOT / "docs" / "superpowers" / "specs" / "2026-09-03-composio-integration-design.md",
        ROOT / "docs" / "superpowers" / "plans" / "2026-09-03-composio-integration-plan.md",
    )
    missing = [str(p.relative_to(ROOT)) for p in required_files if not p.is_file()]
    assert not missing, f"Missing required Composio files: {missing}"

    # Verify imports and basic signatures
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(SRC))

    from src.tools.composio.client import format_user_id, get_composio_client
    from src.tools.composio.auth import initiate_google_connection, check_connection_status, disconnect_user
    from src.tools.composio.mail_tools import composio_mail_search, composio_mail_send, composio_mail_create_draft
    from src.tools.composio.calendar_tools import composio_calendar_list_events, composio_calendar_create_event, composio_calendar_find_free_slots
    from src.tools.composio.commands import handle_connect_google, handle_google_status, handle_disconnect_google

    assert callable(format_user_id)
    assert callable(get_composio_client)
    assert callable(initiate_google_connection)
    assert callable(check_connection_status)
    assert callable(disconnect_user)
    assert callable(composio_mail_search)
    assert callable(composio_mail_send)
    assert callable(composio_mail_create_draft)
    assert callable(composio_calendar_list_events)
    assert callable(composio_calendar_create_event)
    assert callable(composio_calendar_find_free_slots)
    assert callable(handle_connect_google)
    assert callable(handle_google_status)
    assert callable(handle_disconnect_google)

    # Verify user formatting
    assert format_user_id(123) == "telegram_123"

    print("composio layer 1: pass")


def layer_2() -> None:
    test_files = [
        "tests/test_composio_auth.py",
        "tests/test_composio_mail.py",
        "tests/test_composio_calendar.py",
        "tests/test_composio_commands.py",
        "tests/test_composio_mail_outbound.py",
    ]

    for test_file in test_files:
        assert (ROOT / test_file).is_file(), f"Missing test file: {test_file}"

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *test_files, "-v"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError("Composio Layer 2 tests failed")

    print(f"composio layer 2: pass ({len(test_files)} test suites passed)")


def main() -> None:
    parser = ArgumentParser(description="Verify Composio integration")
    parser.add_argument("--layer", choices=["1", "2"], required=True)
    args = parser.parse_args()

    if args.layer == "1":
        layer_1()
    elif args.layer == "2":
        layer_2()


if __name__ == "__main__":
    main()
