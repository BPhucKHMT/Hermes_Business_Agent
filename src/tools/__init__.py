import tools
import os
from pathlib import Path

UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"
if (UPSTREAM / "tools").exists():
    upstream_tools_path = str(UPSTREAM / "tools")
    if upstream_tools_path not in tools.__path__:
        tools.__path__.append(upstream_tools_path)
