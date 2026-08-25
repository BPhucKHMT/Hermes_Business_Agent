from argparse import ArgumentParser


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Azure-managed Hermes Knowledge Base")
    parser.add_argument("--env-file", default=".env")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("provision")

    upload = commands.add_parser("upload")
    upload.add_argument("file")
    upload.add_argument("--source-path")
    upload.add_argument("--workspace", default=None)

    delete = commands.add_parser("delete")
    delete.add_argument("source_path")

    commands.add_parser("index")
    commands.add_parser("status")

    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--query-variant", action="append", default=[])
    search.add_argument("--top-k", type=int, default=8)
    search.add_argument("--workspace", default=None)
    scope = search.add_mutually_exclusive_group()
    scope.add_argument("--source-path")
    scope.add_argument("--website-id")
    search.add_argument("--generation")

    start = commands.add_parser("web-start")
    start.add_argument("url")
    start.add_argument("--scope", choices=("page", "site"), required=True)
    start.add_argument("--policy", default="config/website_policy.json")

    crawl = commands.add_parser("web-crawl")
    crawl.add_argument("url")
    crawl.add_argument("--scope", choices=("page", "site"), required=True)
    crawl.add_argument("--policy", default="config/website_policy.json")

    observe = commands.add_parser("web-observe")
    observe.add_argument("session")
    observe.add_argument("event")

    finish = commands.add_parser("web-finalize")
    finish.add_argument("session")
    finish.add_argument("capture")
    finish.add_argument("--stop-reason", required=True)
    finish.add_argument("--unresolved-frontier")

    ingest = commands.add_parser("web-ingest")
    ingest.add_argument("validated_capture")
    ingest.add_argument("--workspace", default=None)

    verify = commands.add_parser("web-verify")
    verify.add_argument("validated_capture")

    refresh = commands.add_parser("web-refresh")
    refresh.add_argument("previous_capture")
    refresh.add_argument("current_capture")
    refresh.add_argument("--confirm-remove")

    delete_url = commands.add_parser("web-delete")
    delete_url.add_argument("website_id")
    delete_url.add_argument("--confirm", required=True)

    absent = commands.add_parser("web-verify-absent")
    absent.add_argument("website_id")
    return parser
