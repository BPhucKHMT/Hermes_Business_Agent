from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.social_browser.contracts import (
    AccessibleNode,
    BrowserObservation,
    BrowserOperation,
)
from tools.social_browser.harness import BrowserHarnessRunner
from tools.social_browser.policy import SocialBrowserPolicy


class SafeBrowserGateway:
    def __init__(
        self,
        policy: SocialBrowserPolicy,
        platform: str,
        runner: BrowserHarnessRunner,
        session: str = "social-default",
    ):
        self.policy = policy
        self.platform = platform
        self.runner = runner
        self.session = session
        self.current_url = ""

    def dispatch(self, operation: str, payload: dict[str, Any]) -> dict:
        try:
            typed = BrowserOperation(operation)
        except ValueError as exc:
            raise PermissionError("operation_not_allowed") from exc
        if not self.policy.allows_operation(self.platform, typed.value):
            raise PermissionError("operation_not_allowed")
        return self.runner.run(typed, {"session": self.session, **payload})

    def open(self, url: str) -> dict:
        self.policy.require_origin(self.platform, url)
        result = self.dispatch(BrowserOperation.OPEN.value, {"url": url})
        observed_url = str(result.get("url", url))
        self.policy.require_origin(self.platform, observed_url)
        self.current_url = observed_url
        return result

    def observe(self) -> BrowserObservation:
        result = self.dispatch(BrowserOperation.OBSERVE.value, {})
        url = str(result.get("url", self.current_url))
        self.policy.require_origin(self.platform, url)
        self.current_url = url
        nodes = tuple(
            AccessibleNode(
                backend_node_id=int(item["backend_node_id"]),
                role=str(item.get("role", "")),
                name=str(item.get("name", "")),
                url=str(item.get("url", "")),
            )
            for item in result.get("accessible_nodes", [])
        )
        return BrowserObservation(
            url=url,
            title=str(result.get("title", "")),
            account_label=str(result.get("account_label", "")),
            accessible_nodes=nodes,
            warning_codes=tuple(result.get("warning_codes", [])),
        )

    def activate_control(self, node: AccessibleNode) -> dict:
        if self.policy.is_terminal_name(self.platform, node.name):
            raise PermissionError("terminal_action_denied")
        return self.dispatch(
            BrowserOperation.ACTIVATE_CONTROL.value,
            {"backend_node_id": node.backend_node_id},
        )

    def fill(self, selector: str, text: str) -> dict:
        return self.dispatch(
            BrowserOperation.FILL.value, {"selector": selector, "text": text}
        )

    def upload(self, selector: str, path: Path) -> dict:
        resolved = Path(path).resolve(strict=True)
        return self.dispatch(
            BrowserOperation.UPLOAD.value,
            {"selector": selector, "path": str(resolved)},
        )

    def close(self) -> dict:
        return self.dispatch(BrowserOperation.CLOSE.value, {})
