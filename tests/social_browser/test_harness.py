import json
from pathlib import Path
from types import SimpleNamespace

from tools.social_browser.contracts import BrowserOperation
from tools.social_browser.harness import BrowserHarnessRunner


class FakeProcess:
    def __init__(self) -> None:
        self.command = None
        self.stdin = None
        self.env = None

    def __call__(self, command, **kwargs):
        self.command = command
        self.stdin = kwargs["input"]
        self.env = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout='{"ok": true}\n', stderr="")


def test_runner_uses_fixed_templates_without_user_code(tmp_path: Path) -> None:
    process = FakeProcess()
    runner = BrowserHarnessRunner(
        workspace=tmp_path, cdp_url="http://127.0.0.1:9222", process=process
    )

    result = runner.run(BrowserOperation.OBSERVE, {"session": "run-1"})

    assert result == {"ok": True}
    assert process.command == ["browser-harness"]
    assert "exec(" not in process.stdin
    assert "eval(" not in process.stdin
    assert "raw_code" not in process.stdin


def test_runner_forces_telemetry_off(tmp_path: Path) -> None:
    process = FakeProcess()
    runner = BrowserHarnessRunner(
        workspace=tmp_path, cdp_url="http://127.0.0.1:9222", process=process
    )

    runner.run(BrowserOperation.OBSERVE, {"session": "run-1"})

    assert process.env["BH_TELEMETRY"] == "0"
    assert process.env["BU_CDP_URL"] == "http://127.0.0.1:9222"
    assert "BROWSER_USE_API_KEY" not in process.env


def test_runner_rejects_unknown_payload_fields(tmp_path: Path) -> None:
    process = FakeProcess()
    runner = BrowserHarnessRunner(
        workspace=tmp_path, cdp_url="http://127.0.0.1:9222", process=process
    )

    try:
        runner.run(BrowserOperation.OBSERVE, {"session": "run-1", "raw_code": "x"})
    except ValueError as exc:
        assert str(exc) == "invalid_browser_payload"
    else:
        raise AssertionError("invalid payload was accepted")


def test_runner_rejects_non_local_or_ambiguous_cdp_endpoint(tmp_path: Path) -> None:
    for endpoint in (
        "https://127.0.0.1:9222",
        "http://127.0.0.1:9222/path",
        "http://127.0.0.1:99999",
        "http://user@localhost:9222",
    ):
        try:
            BrowserHarnessRunner(workspace=tmp_path, cdp_url=endpoint)
        except ValueError as exc:
            assert str(exc) == "local_cdp_endpoint_required"
        else:
            raise AssertionError(f"unsafe endpoint accepted: {endpoint}")
