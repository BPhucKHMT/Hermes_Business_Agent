"""Flow A JSON CLI; registered targets only."""
from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Flow A JSON CLI for progress reports")
    parser.add_argument("command", choices=("ingest", "preview", "approve", "status"))
    parser.add_argument("--payload", default=None)
    args = parser.parse_args()

    result = {
        "status": "accepted",
        "command": args.command,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
