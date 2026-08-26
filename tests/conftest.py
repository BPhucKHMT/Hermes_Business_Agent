import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PLUGIN = SRC / ".hermes/plugins/email-connector"
UPSTREAM = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes/hermes-agent"

for p in (SRC, PLUGIN, UPSTREAM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
