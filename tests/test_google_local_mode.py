import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for name in ("email-connector", "calendar-connector"):
    sys.path.insert(0, str(ROOT / "src/.hermes/plugins" / name))

from calendar_caller import (  # noqa: E402 -- imports follow plugin path bootstrap
    CallerContextRegistry as CalendarRegistry,
)
from calendar_commands import (  # noqa: E402 -- imports follow plugin path bootstrap
    _candidate_src_dirs as calendar_candidate_src_dirs,
)
from caller import (  # noqa: E402 -- imports follow plugin path bootstrap
    CallerContextRegistry as MailRegistry,
)
from commands import (  # noqa: E402 -- imports follow plugin path bootstrap
    _candidate_src_dirs as email_candidate_src_dirs,
)

from tools.composio.auth import (  # noqa: E402 -- imports follow source path bootstrap
    resolve_account_target,
)
from tools.composio.local_owner import (  # noqa: E402 -- imports follow source path bootstrap
    ensure_local_owner,
    load_local_owner,
)

OWNER_ID = "12345678-1234-4234-8234-123456789abc"


@pytest.fixture
def owner_file(tmp_path):
    path = tmp_path / "local-owner.json"
    path.write_text(json.dumps({"schema_version": 1, "owner_id": OWNER_ID}))
    return path


@pytest.mark.parametrize(
    ("candidate_src_dirs", "yaml_mode"),
    [
        (email_candidate_src_dirs, "missing"),
        (email_candidate_src_dirs, "malformed"),
        (calendar_candidate_src_dirs, "missing"),
        (calendar_candidate_src_dirs, "malformed"),
    ],
)
def test_yaml_discovery_continues_after_optional_config_failure(
    tmp_path, monkeypatch, candidate_src_dirs, yaml_mode
):
    home = tmp_path / "home"
    config_dir = home / ".hermes"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("terminal: [", encoding="utf-8")
    source_dir = tmp_path / "project-src"
    (source_dir / "tools").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("HERMES_PROJECT_SRC", str(source_dir))
    module = sys.modules[candidate_src_dirs.__module__]
    if yaml_mode == "missing":
        monkeypatch.setattr(module, "yaml", None)
    else:

        class BrokenYaml:
            class YAMLError(Exception):
                pass

            @classmethod
            def safe_load(cls, _text):
                raise cls.YAMLError("malformed")

        monkeypatch.setattr(module, "yaml", BrokenYaml)

    assert source_dir in candidate_src_dirs()


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

    accounts = {"account-a": "alpha@example.invalid"}
    with (
        patch("tools.composio.auth.get_user_emails", return_value=accounts),
        pytest.raises(ValueError),
    ):
        resolve_account_target("local:owner:audit", "absent@example.invalid")
