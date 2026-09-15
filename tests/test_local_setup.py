from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

import setup_local


def _fake_hermes_runner(config_path: Path, calls: list[tuple[str, ...]]):
    config = json.loads(config_path.read_text(encoding="utf-8"))

    def run(executable: str, arguments: tuple[str, ...], root: Path):
        del executable, root
        calls.append(arguments)
        if arguments == ("config", "env-path"):
            return subprocess.CompletedProcess(
                arguments, 0, stdout=str(config_path.parent / ".env"), stderr=""
            )
        if arguments[:4] == ("config", "get", "skills.external_dirs", "--json"):
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout=json.dumps(config["skills"]["external_dirs"]),
                stderr="",
            )
        if arguments[:2] == ("config", "set"):
            key, value = arguments[2:4]
            if "." in key:
                parts = key.split(".")
                target = config
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = (
                    json.loads(value) if key == "skills.external_dirs" else value
                )
            else:
                config[key] = value
            config_path.write_text(json.dumps(config), encoding="utf-8")
        elif arguments[:2] == ("plugins", "enable"):
            plugin = arguments[2]
            enabled = config.setdefault("plugins", {}).setdefault("enabled", [])
            if plugin not in enabled:
                enabled.append(plugin)
            config_path.write_text(json.dumps(config), encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    return run


def test_local_flag_is_required(capsys):
    assert setup_local.main([]) == 2
    assert "--local" in capsys.readouterr().err


def test_owner_file_is_stable_without_telegram(tmp_path):
    first = setup_local.ensure_local_owner(tmp_path)
    second = setup_local.ensure_local_owner(tmp_path)

    assert first == second
    payload = json.loads(
        (tmp_path / ".runtime" / "google" / "local-owner.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload == {"schema_version": 1, "owner_id": first}


def test_local_setup_preserves_config_and_never_requires_telegram(
    tmp_path, monkeypatch
):
    root = tmp_path / "src"
    (root / "skills").mkdir(parents=True)
    (root / ".hermes/plugins").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "operator"))
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "terminal": {"cwd": "C:/operator/project"},
                "skills": {"external_dirs": ["C:/operator/skills"]},
                "plugins": {"enabled": ["operator-plugin"]},
                "gateway": {"profile_routes": [{"name": "existing-route"}]},
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(setup_local, "_resolve_executable", lambda name, hint: name)
    monkeypatch.setattr(
        setup_local,
        "_run_hermes",
        _fake_hermes_runner(config_path, calls),
    )
    monkeypatch.setattr(
        setup_local,
        "_update_dotenv_var",
        lambda _path, _key, _val: None,
    )
    owner = setup_local.configure_local(root)
    updated = json.loads(config_path.read_text(encoding="utf-8"))

    assert owner == setup_local.ensure_local_owner(root)
    assert updated["terminal"]["cwd"] == str(root.resolve())
    assert updated["skills"]["external_dirs"] == [
        "C:/operator/skills",
        str((root / "skills").resolve()),
    ]
    assert updated["plugins"]["enabled"] == [
        "operator-plugin",
        "email-connector",
        "calendar-connector",
    ]
    assert "platforms" not in updated
    assert updated["gateway"] == {"profile_routes": [{"name": "existing-route"}]}
    assert updated["HERMES_PROJECT_SRC"] == str(root.resolve())
    assert updated["HERMES_ENABLE_PROJECT_PLUGINS"] == "1"
    assert not any("telegram" in part.lower() for call in calls for part in call)

    setup_local.configure_local(root)
    assert setup_local.ensure_local_owner(root) == owner


def test_plugin_sync_changes_only_selected_home(tmp_path, monkeypatch):
    root = tmp_path / "source with spaces"
    plugin = root / ".hermes/plugins/email-connector"
    plugin.mkdir(parents=True)
    (plugin / "__init__.py").write_text("CURRENT = True\n", encoding="utf-8")
    selected = tmp_path / "selected"
    selected.mkdir()
    unrelated = tmp_path / "other-user"
    (unrelated / ".hermes/plugins/email-connector").mkdir(parents=True)
    sentinel = unrelated / ".hermes/plugins/email-connector/__init__.py"
    sentinel.write_text("DO_NOT_CHANGE = True\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(selected))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "other-appdata"))
    monkeypatch.setattr(Path, "home", lambda: unrelated)

    setup_local._sync_plugins(root)

    assert sentinel.read_text(encoding="utf-8") == "DO_NOT_CHANGE = True\n"
    assert (selected / "plugins/email-connector/__init__.py").read_text(
        encoding="utf-8"
    ) == "CURRENT = True\n"


def test_plugin_sync_removes_stale_code_preserving_unowned_plugins(
    tmp_path, monkeypatch
):
    root = tmp_path / "src"
    plugin = root / ".hermes/plugins/email-connector"
    plugin.mkdir(parents=True)
    (plugin / "__init__.py").write_text("CURRENT = True\n", encoding="utf-8")
    home = tmp_path / "operator"
    target = home / "plugins/email-connector"
    target.mkdir(parents=True)
    (target / "obsolete.py").write_text("OLD = True\n", encoding="utf-8")
    custom = home / "plugins/custom-plugin"
    custom.mkdir()
    (custom / "data.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "unused")

    setup_local._sync_plugins(root)
    setup_local._sync_plugins(root)

    assert not (target / "obsolete.py").exists()
    assert (target / "__init__.py").read_text(encoding="utf-8") == "CURRENT = True\n"
    assert (custom / "data.txt").read_text(encoding="utf-8") == "keep"


def test_missing_plugin_source_is_not_success(tmp_path):
    with pytest.raises(setup_local.SetupError):
        setup_local._sync_plugins(tmp_path)


def test_failed_plugin_copy_preserves_installed_version(tmp_path, monkeypatch):
    root = tmp_path / "src"
    source = root / ".hermes/plugins/email-connector"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("new", encoding="utf-8")
    home = tmp_path / "operator"
    target = home / "plugins/email-connector"
    target.mkdir(parents=True)
    installed = target / "__init__.py"
    installed.write_text("working", encoding="utf-8")

    def fail_copy(*args, **kwargs):
        raise PermissionError("simulated locked file")

    monkeypatch.setattr(setup_local.shutil, "copytree", fail_copy)
    with pytest.raises(PermissionError):
        setup_local._sync_plugins(root, home)
    assert installed.read_text(encoding="utf-8") == "working"
    assert sorted(p.name for p in target.parent.iterdir()) == ["email-connector"]


def test_operator_env_preserves_secrets_and_quotes_path(tmp_path):
    path = tmp_path / ".env"
    path.write_text("COMPOSIO_API_KEY='test-only'\n# keep note\n", encoding="utf-8")
    value = "C:/Customer Name/Hermes #1/src"
    setup_local._update_dotenv_var(path, "HERMES_PROJECT_SRC", value)
    setup_local._update_dotenv_var(path, "HERMES_PROJECT_SRC", value)
    text = path.read_text(encoding="utf-8")
    assert "COMPOSIO_API_KEY='test-only'" in text
    assert "# keep note" in text
    assert text.count("HERMES_PROJECT_SRC=") == 1
    assert f"HERMES_PROJECT_SRC='{value}'" in text
