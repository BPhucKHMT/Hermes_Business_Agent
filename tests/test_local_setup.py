from __future__ import annotations

import json
import subprocess
from pathlib import Path

import setup_local


def _fake_hermes_runner(config_path: Path, calls: list[tuple[str, ...]]):
    config = json.loads(config_path.read_text(encoding="utf-8"))

    def run(executable: str, arguments: tuple[str, ...], root: Path):
        del executable, root
        calls.append(arguments)
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
                section, leaf = key.split(".", 1)
                config.setdefault(section, {})[leaf] = (
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


def test_local_setup_preserves_config_and_never_requires_telegram(tmp_path, monkeypatch):
    root = tmp_path / "src"
    (root / "skills").mkdir(parents=True)
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
    assert updated["gateway"] == {"profile_routes": [{"name": "existing-route"}]}
    assert updated["HERMES_PROJECT_SRC"] == str(root.resolve())
    assert updated["HERMES_ENABLE_PROJECT_PLUGINS"] == "1"
    assert not any("telegram" in part.lower() for call in calls for part in call)

    setup_local.configure_local(root)
    assert setup_local.ensure_local_owner(root) == owner
