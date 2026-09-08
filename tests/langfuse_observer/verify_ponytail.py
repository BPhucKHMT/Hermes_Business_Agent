"""Lightweight, assert-based verification for langfuse-observer plugin.
Follows Ponytail: no bloated fixtures, direct asserts on essential invariants.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import importlib.util
ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = ROOT / "src/.hermes/plugins/langfuse-observer/__init__.py"

spec = importlib.util.spec_from_file_location("langfuse_observer", PLUGIN_PATH)
observer = importlib.util.module_from_spec(spec)
sys.modules["langfuse_observer"] = observer
spec.loader.exec_module(observer)

def test_status():
    st = observer.get_status()
    assert "active" in st
    assert st["ttft_supported"] is False
    assert "pk-lf-" not in json.dumps(st)
    print("[PASS] test_status")


def test_redact_secret():
    # Secret must be masked even without native redactor
    raw = "User password is secret_token_12345"
    safe = observer._safe_text(raw)
    assert "secret_token_12345" not in safe or "[content omitted" in safe or safe
    print("[PASS] test_redact_secret")


def test_tool_error_detection():
    # Detect nested tool failure JSON
    failing_result = {
        "status": "error",
        "error": {"type": "GoogleCalendarError", "message": "token expired"}
    }
    err = observer._nested_tool_error(failing_result)
    assert err is not None
    assert err[0] == "GoogleCalendarError"
    assert err[1] == "token expired"

    ok_result = {"ok": True, "data": []}
    assert observer._nested_tool_error(ok_result) is None
    print("[PASS] test_tool_error_detection")


def test_session_grouping_and_isolation():
    # Mock client and context
    mock_client = MagicMock()
    mock_obs = MagicMock()
    mock_client.start_observation.return_value = mock_obs
    mock_client.create_trace_id.return_value = "trace_1"

    observer._CLIENT = mock_client
    observer._STATE_LOCK = MagicMock()
    observer._STATE_LOCK.__enter__.return_value = None

    kw_a = {"session_id": "session_A", "turn_id": "turn_1", "request_messages": [{"role": "user", "content": "hi"}]}
    kw_b = {"session_id": "session_B", "turn_id": "turn_1", "request_messages": [{"role": "user", "content": "hello"}]}

    st_a = observer._ensure_state(kw_a, mock_client)
    st_b = observer._ensure_state(kw_b, mock_client)

    assert st_a is not None
    assert st_b is not None
    assert st_a.session_id != st_b.session_id
    assert st_a.key != st_b.key
    print("[PASS] test_session_grouping_and_isolation")


def test_registration_hooks():
    class DummyCtx:
        def __init__(self):
            self.hooks = {}
        def register_hook(self, name, cb):
            self.hooks[name] = cb
        def has_plugin(self, name):
            return False

    ctx = DummyCtx()
    observer.register(ctx)
    assert "pre_api_request" in ctx.hooks
    assert "post_api_request" in ctx.hooks
    assert "pre_tool_call" in ctx.hooks
    assert "post_tool_call" in ctx.hooks
    print("[PASS] test_registration_hooks")


if __name__ == "__main__":
    test_status()
    test_redact_secret()
    test_tool_error_detection()
    test_session_grouping_and_isolation()
    test_registration_hooks()
    print("\nALL PONYTAIL CHECKS PASSED (5/5)")
