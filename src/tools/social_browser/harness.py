from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

from tools.social_browser.contracts import BrowserOperation


_COMMON = """import base64, json, os
payload = json.loads(base64.b64decode(os.environ[\"BH_INPUT_JSON\"]))
"""
_SCRIPTS = {
    BrowserOperation.OPEN: _COMMON
    + """goto_url(payload[\"url\"])
wait_for_load()
print(json.dumps(page_info(), ensure_ascii=False))
""",
    BrowserOperation.OBSERVE: _COMMON
    + """info = page_info()
ax = cdp(\"Accessibility.getFullAXTree\")
nodes = []
for item in ax.get(\"nodes\", []):
    backend_id = item.get(\"backendDOMNodeId\")
    role = item.get(\"role\", {}).get(\"value\", \"\")
    name = item.get(\"name\", {}).get(\"value\", \"\")
    properties = {
        prop.get(\"name\"): prop.get(\"value\", {}).get(\"value\", \"\")
        for prop in item.get(\"properties\", [])
    }
    if backend_id and (role or name):
        nodes.append({
            \"backend_node_id\": backend_id,
            \"role\": role,
            \"name\": name,
            \"url\": properties.get(\"url\", \"\"),
        })
print(json.dumps({**info, \"accessible_nodes\": nodes[:2000]}, ensure_ascii=False))
""",
    BrowserOperation.ACTIVATE_CONTROL: _COMMON
    + """model = cdp(\"DOM.getBoxModel\", backendNodeId=int(payload[\"backend_node_id\"]))[\"model\"]
quad = model[\"content\"]
x = sum(quad[0::2]) / 4
y = sum(quad[1::2]) / 4
click_at_xy(x, y)
print(json.dumps({\"activated\": True}))
""",
    BrowserOperation.FILL: _COMMON
    + """fill_input(payload[\"selector\"], payload[\"text\"], timeout=10)
print(json.dumps({\"filled\": True}))
""",
    BrowserOperation.UPLOAD: _COMMON
    + """upload_file(payload[\"selector\"], payload[\"path\"])
print(json.dumps({\"uploaded\": True}))
""",
    BrowserOperation.CLOSE: _COMMON
    + """close_tab()
print(json.dumps({\"closed\": True}))
""",
}
_REQUIRED_FIELDS = {
    BrowserOperation.OPEN: {"session", "url"},
    BrowserOperation.OBSERVE: {"session"},
    BrowserOperation.ACTIVATE_CONTROL: {"session", "backend_node_id"},
    BrowserOperation.FILL: {"session", "selector", "text"},
    BrowserOperation.UPLOAD: {"session", "selector", "path"},
    BrowserOperation.CLOSE: {"session"},
}
_ENV_ALLOWLIST = {
    "APPDATA",
    "HOME",
    "LOCALAPPDATA",
    "PATH",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}


class BrowserHarnessRunner:
    def __init__(
        self,
        workspace: Path,
        cdp_url: str,
        process: Callable[..., Any] = subprocess.run,
        timeout_seconds: int = 30,
        max_output_chars: int = 50_000,
    ):
        if not cdp_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("local_cdp_endpoint_required")
        self.workspace = Path(workspace).resolve()
        self.cdp_url = cdp_url
        self.process = process
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def run(self, operation: BrowserOperation, payload: dict[str, Any]) -> dict:
        if set(payload) != _REQUIRED_FIELDS[operation]:
            raise ValueError("invalid_browser_payload")
        script = _SCRIPTS[operation]
        environment = self._environment(payload["session"], payload)
        completed = self.process(
            ["browser-harness"],
            input=script,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=self.timeout_seconds,
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip()[-500:]
            raise RuntimeError(f"browser_harness_failed: {error}")
        if len(completed.stdout) > self.max_output_chars:
            raise RuntimeError("browser_harness_output_exceeded")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("browser_harness_empty_output")
        try:
            result = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("browser_harness_invalid_output") from exc
        if not isinstance(result, dict):
            raise RuntimeError("browser_harness_invalid_output")
        return result

    def _environment(self, session: str, payload: dict[str, Any]) -> dict[str, str]:
        environment = {
            key: value for key, value in os.environ.items() if key in _ENV_ALLOWLIST
        }
        encoded = base64.b64encode(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        environment.update(
            {
                "BH_AGENT_WORKSPACE": str(self.workspace),
                "BH_INPUT_JSON": encoded,
                "BH_OPEN_LIVE_URL": "0",
                "BH_TELEMETRY": "0",
                "BU_CDP_URL": self.cdp_url,
                "BU_NAME": session,
                "PYTHONUTF8": "1",
            }
        )
        return environment
