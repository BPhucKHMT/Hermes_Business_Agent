import tools
import os
from pathlib import Path

candidates = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "hermes-agent",
    Path.home() / ".hermes" / "hermes-agent",
    Path("/home/azureuser/.hermes/hermes-agent"),
    Path(os.environ.get("HERMES_HOME", "")) / "hermes-agent",
]

for upstream in candidates:
    if upstream and (upstream / "tools").is_dir():
        upstream_tools_path = str((upstream / "tools").resolve())
        if upstream_tools_path not in tools.__path__:
            tools.__path__.append(upstream_tools_path)
        break
