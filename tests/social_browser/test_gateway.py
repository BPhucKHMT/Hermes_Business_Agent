from pathlib import Path

import pytest

from tools.social_browser.contracts import AccessibleNode, BrowserOperation
from tools.social_browser.gateway import SafeBrowserGateway
from tools.social_browser.policy import load_policy


ROOT = Path(__file__).resolve().parents[2]


class FakeRunner:
    def __init__(self) -> None:
        self.calls = []

    def run(self, operation, payload):
        self.calls.append((operation, payload))
        return {"url": payload.get("url", "https://www.facebook.com/")}


@pytest.fixture
def gateway() -> SafeBrowserGateway:
    policy = load_policy(ROOT / "src/config/social_browser_policy.json")
    return SafeBrowserGateway(policy, "facebook-personal", FakeRunner())


def node(name: str) -> AccessibleNode:
    return AccessibleNode(backend_node_id=42, role="button", name=name)


def test_gateway_denies_terminal_accessible_name(gateway) -> None:
    with pytest.raises(PermissionError, match="terminal_action_denied"):
        gateway.activate_control(node("Post"))


def test_gateway_denies_raw_operations(gateway) -> None:
    for operation in ("raw_cdp", "javascript", "coordinate_click", "shell"):
        with pytest.raises(PermissionError, match="operation_not_allowed"):
            gateway.dispatch(operation, {})


def test_gateway_rejects_cross_origin_open(gateway) -> None:
    with pytest.raises(PermissionError, match="origin_not_allowed"):
        gateway.open("https://example.com/")


def test_gateway_allows_nonterminal_control(gateway) -> None:
    gateway.activate_control(node("Bạn đang nghĩ gì?"))

    operation, payload = gateway.runner.calls[-1]
    assert operation is BrowserOperation.ACTIVATE_CONTROL
    assert payload["backend_node_id"] == 42
