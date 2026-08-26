from __future__ import annotations

import argparse
import json

from tools.email.service import build_service_from_env, create_http_server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.email.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8766)
    commands.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        service = build_service_from_env()
    except Exception:
        print(json.dumps({"ok": False, "error": {"code": "connector_unavailable"}}))
        return 1

    if args.command == "status":
        print(json.dumps({"ok": True, "service": "email_connector"}))
        return 0

    server = create_http_server(service, args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
