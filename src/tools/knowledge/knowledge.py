from argparse import ArgumentParser
from pathlib import Path
import json
import os

from clients import create_clients, load_config
from indexing import indexer_status, run_indexers
from provision import provision
from retrieval import knowledge_search
from storage import delete_source, upload_source


def load_env(path: Path) -> None:
    if not path.is_file():
        raise ValueError("environment file not found: %s" % path)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip())


def main() -> None:
    parser = ArgumentParser(description="Azure-managed Hermes Knowledge Base")
    parser.add_argument("--env-file", default=".env")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("provision")
    upload = commands.add_parser("upload"); upload.add_argument("file"); upload.add_argument("--source-path"); upload.add_argument("--access-group", action="append", required=True)
    delete = commands.add_parser("delete"); delete.add_argument("source_path")
    commands.add_parser("index")
    commands.add_parser("status")
    search = commands.add_parser("search"); search.add_argument("query"); search.add_argument("--access-group", required=True); search.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()
    load_env(Path(args.env_file))
    config = load_config()
    clients = create_clients(config)
    if args.command == "provision":
        result = provision(clients, config)
    elif args.command == "upload":
        path = Path(args.file)
        result = upload_source(clients.layout_container, clients.text_container, args.source_path or path.name, path.read_bytes(), args.access_group)
    elif args.command == "delete":
        result = delete_source(clients.layout_container, clients.text_container, args.source_path)
    elif args.command == "index":
        result = run_indexers(clients.indexers, [config["AZURE_SEARCH_LAYOUT_INDEXER"], config["AZURE_SEARCH_TEXT_INDEXER"]])
    elif args.command == "status":
        result = {name: indexer_status(clients.indexers, config[name]) for name in ("AZURE_SEARCH_LAYOUT_INDEXER", "AZURE_SEARCH_TEXT_INDEXER")}
    else:
        result = knowledge_search(clients.search, args.query, args.access_group, args.top_k).to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
