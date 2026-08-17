from __future__ import annotations
import json
import re
import sys
KNOWLEDGE = "tools/knowledge/knowledge.py"
REQUIRED_PREFIX = "uv run --frozen python " + KNOWLEDGE

def block_reason(command: str) -> str | None:
    normalized = " ".join((command or "").replace("\\", "/").split())
    lower = normalized.lower()
    if KNOWLEDGE in lower and REQUIRED_PREFIX not in lower:
        return "Knowledge commands require: uv run --frozen python tools/knowledge/knowledge.py ..."
    if re.search(r"(^|[;&|]\s*)(pip|pip3|uv\s+pip|uv\s+sync)\b", lower):
        return "Chat-driven package installation or environment mutation is forbidden"
    if KNOWLEDGE in lower and " --json" in lower:
        return "Unsupported knowledge CLI option --json is forbidden"
    return None

def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "terminal": return
    reason = block_reason(str((payload.get("tool_input") or {}).get("command", "")))
    if reason: print(json.dumps({"decision": "block", "reason": reason}))

if __name__ == "__main__": main()
