from pathlib import Path
import json
import sys
from unittest.mock import patch

from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for name in ("email-connector", "calendar-connector"):
    sys.path.insert(0, str(ROOT / "src/.hermes/plugins" / name))

from caller import CallerContextRegistry as MailRegistry
from calendar_caller import CallerContextRegistry as CalendarRegistry

from tools.composio.local_owner import ensure_local_owner, load_local_owner

OWNER_ID = "12345678-1234-4234-8234-123456789abc"


@pytest.fixture
def owner_file(tmp_path):
    path = tmp_path / "local-owner.json"
    path.write_text(json.dumps({"schema_version": 1, "owner_id": OWNER_ID}))
    return path


def test_owner_provisioning_is_idempotent_and_restart_stable(tmp_path):
    first = ensure_local_owner(tmp_path)
    second = ensure_local_owner(tmp_path)
    owner_path = tmp_path / ".runtime" / "google" / "local-owner.json"

    assert first == second
    assert load_local_owner(owner_path) == first

    restarted = MailRegistry(local_owner_path=owner_path)
    assert restarted.resolve_command().principal_id == f"local:owner:{first}"


@pytest.mark.parametrize("registry_type", [MailRegistry, CalendarRegistry])
def test_explicit_local_binding_connects_commands_and_tools(owner_file, registry_type):
    registry = registry_type(local_owner_path=owner_file)
    command_caller = registry.resolve_command()
    tool_caller = registry.resolve_dm_tool(session_id="local-session")
    assert command_caller.principal_id == f"local:owner:{OWNER_ID}"
    assert tool_caller.principal_id == command_caller.principal_id
    assert command_caller.platform == "local"
    assert not command_caller.chat_id


@pytest.mark.parametrize("registry_type", [MailRegistry, CalendarRegistry])
def test_missing_local_binding_never_creates_owner(tmp_path, registry_type):
    path = tmp_path / "missing-owner.json"
    registry = registry_type(local_owner_path=path)
    with pytest.raises(LookupError):
        registry.resolve_command()
    assert not path.exists()


@pytest.mark.parametrize("registry_type", [MailRegistry, CalendarRegistry])
def test_corrupt_local_binding_fails_closed(owner_file, registry_type):
    owner_file.write_text('{"schema_version": 1, "owner_id": ""}')
    registry = registry_type(local_owner_path=owner_file)
    with pytest.raises(LookupError):
        registry.resolve_command()


def test_captured_group_never_falls_back_to_local_owner(owner_file):
    source = SimpleNamespace(
        platform=SimpleNamespace(value="telegram"),
        user_id="111",
        user_id_alt=None,
        scope_id=None,
        chat_id="-100",
        chat_type="group",
        profile="hermes-business",
        thread_id=None,
    )
    event = SimpleNamespace(source=source)
    for registry_type in (MailRegistry, CalendarRegistry):
        registry = registry_type(local_owner_path=owner_file)
        with pytest.raises((ValueError, Exception)):
            registry.capture(event)
        with pytest.raises((ValueError, Exception)):
            registry.resolve_command()


def test_captured_native_session_without_identity_cannot_be_local(owner_file):
    source = SimpleNamespace(
        platform=SimpleNamespace(value="cron"),
        user_id="",
        user_id_alt=None,
        scope_id=None,
        chat_id="",
        chat_type="dm",
        profile="nightly",
        thread_id=None,
    )
    event = SimpleNamespace(source=source)
    for registry_type in (MailRegistry, CalendarRegistry):
        registry = registry_type(local_owner_path=owner_file)
        with pytest.raises((ValueError, Exception)):
            registry.capture(event)
        with pytest.raises((ValueError, LookupError, Exception)):
            registry.resolve_command()
    from tools.composio.auth import resolve_account_target

    accounts = {"account-a": "alpha@example.invalid"}
    with patch("tools.composio.auth.get_user_emails", return_value=accounts):
        with pytest.raises(ValueError):
            resolve_account_target("local:owner:audit", "absent@example.invalid")
