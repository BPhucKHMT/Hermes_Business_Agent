from argparse import ArgumentParser
from pathlib import Path
import json
import os
import sys

from clients import create_clients, load_config
from indexing import indexer_status, run_indexers, wait_for_indexers, wait_for_website_absent, website_absent, website_readiness
from policy import load_website_policy
from provision import provision
from retrieval import knowledge_search, knowledge_search_many
from storage import delete_source, delete_website_capture, upload_source, upload_website_capture
from crawl import trusted_crawl
from web import accept_observation, capture_diff, finalize_session, load_manifest, start_session, validate_capture

INTERNAL_GROUP = "internal"
RUNTIME = Path(".runtime/knowledge/web-sessions")


def load_env(path: Path) -> None:
    if not path.is_file(): raise ValueError("environment file not found: %s" % path)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1); os.environ.setdefault(name.strip(), value.strip())


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def runtime_path(value: str) -> Path:
    root = RUNTIME.resolve()
    path = Path(value).resolve()
    if path != root and root not in path.parents:
        raise ValueError("web session path must stay under runtime storage")
    return path


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    parser = ArgumentParser(description="Azure-managed Hermes Knowledge Base")
    parser.add_argument("--env-file", default=".env")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("provision")
    upload = commands.add_parser("upload"); upload.add_argument("file"); upload.add_argument("--source-path")
    delete = commands.add_parser("delete"); delete.add_argument("source_path")
    commands.add_parser("index"); commands.add_parser("status")
    search = commands.add_parser("search"); search.add_argument("query"); search.add_argument("--query-variant", action="append", default=[]); search.add_argument("--top-k", type=int, default=8)
    scope = search.add_mutually_exclusive_group(); scope.add_argument("--source-path"); scope.add_argument("--website-id")
    search.add_argument("--generation")
    start = commands.add_parser("web-start"); start.add_argument("url"); start.add_argument("--scope", choices=("page", "site"), required=True); start.add_argument("--policy", default="config/website_policy.json")
    crawl = commands.add_parser("web-crawl"); crawl.add_argument("url"); crawl.add_argument("--scope", choices=("page", "site"), required=True); crawl.add_argument("--policy", default="config/website_policy.json")
    observe = commands.add_parser("web-observe"); observe.add_argument("session"); observe.add_argument("event")
    finish = commands.add_parser("web-finalize"); finish.add_argument("session"); finish.add_argument("capture"); finish.add_argument("--stop-reason", required=True); finish.add_argument("--unresolved-frontier")
    ingest = commands.add_parser("web-ingest"); ingest.add_argument("validated_capture")
    verify = commands.add_parser("web-verify"); verify.add_argument("validated_capture")
    refresh = commands.add_parser("web-refresh"); refresh.add_argument("previous_capture"); refresh.add_argument("current_capture"); refresh.add_argument("--confirm-remove")
    delete_url = commands.add_parser("web-delete"); delete_url.add_argument("website_id"); delete_url.add_argument("--confirm", required=True)
    absent = commands.add_parser("web-verify-absent"); absent.add_argument("website_id")
    args = parser.parse_args()

    if args.command == "web-start":
        result = start_session(args.url, load_website_policy(Path(args.policy)), args.scope)
        path = RUNTIME / (result["session_id"] + ".json"); atomic_json(path, result)
        result = {"status": "started", "session": str(path), "crawl": result}
    elif args.command == "web-crawl":
        crawled = trusted_crawl(args.url, load_website_policy(Path(args.policy)), RUNTIME, args.scope)
        session_path = RUNTIME / (crawled["session"]["session_id"] + ".json")
        validated_path = RUNTIME / (crawled["session"]["session_id"] + ".validated.json")
        atomic_json(session_path, crawled["session"]); atomic_json(validated_path, crawled["validated"])
        result = {"status": "captured", "session": str(session_path), "validated_capture": str(validated_path), "coverage": crawled["validated"]["completion"]["coverage"], "artifacts": crawled["artifacts"]}
    elif args.command == "web-observe":
        path = runtime_path(args.session); result = accept_observation(load_manifest(path), load_manifest(Path(args.event))); atomic_json(path, result)
    elif args.command == "web-finalize":
        path = runtime_path(args.session)
        frontier = json.loads(Path(args.unresolved_frontier).read_text(encoding="utf-8")) if args.unresolved_frontier else []
        session = finalize_session(load_manifest(path), args.stop_reason, frontier)
        result = validate_capture(session, load_manifest(Path(args.capture)), Path.cwd())
        output = RUNTIME / (session["session_id"] + ".validated.json"); atomic_json(output, result)
        result = {"status": "validated", "validated_capture": str(output), "capture": result}
    else:
        load_env(Path(args.env_file)); config = load_config(); clients = create_clients(config)
        if args.command == "provision": result = provision(clients, config)
        elif args.command == "upload":
            path = Path(args.file); result = upload_source(clients.layout_container, clients.text_container, args.source_path or path.name, path.read_bytes(), [INTERNAL_GROUP])
        elif args.command == "delete": result = delete_source(clients.layout_container, clients.text_container, args.source_path)
        elif args.command == "index": result = run_indexers(clients.indexers, [config["AZURE_SEARCH_LAYOUT_INDEXER"], config["AZURE_SEARCH_TEXT_INDEXER"]])
        elif args.command == "status": result = {name: indexer_status(clients.indexers, config[name]) for name in ("AZURE_SEARCH_LAYOUT_INDEXER", "AZURE_SEARCH_TEXT_INDEXER", "AZURE_SEARCH_IMAGE_INDEXER")}
        elif args.command == "search":
            if args.generation and not args.website_id: raise ValueError("--generation requires --website-id")
            queries = [args.query] + args.query_variant
            result = (knowledge_search_many(clients.search, queries, [INTERNAL_GROUP], args.top_k, source_path=args.source_path, website_id=args.website_id, generation=args.generation) if args.query_variant else knowledge_search(clients.search, args.query, [INTERNAL_GROUP], args.top_k, source_path=args.source_path, website_id=args.website_id, generation=args.generation)).to_dict()
        elif args.command == "web-ingest":
            captured = load_manifest(runtime_path(args.validated_capture))
            if not captured.get("session_id") or not captured.get("completion") or not captured.get("captures"): raise ValueError("web-ingest requires a finalized validated capture")
            uploads = [upload_website_capture(clients.text_container, clients.image_container, page, [INTERNAL_GROUP]) for page in captured["captures"]]
            used = [config["AZURE_SEARCH_TEXT_INDEXER"]]
            if any(page.get("assets") for page in captured["captures"]): used.append(config["AZURE_SEARCH_IMAGE_INDEXER"])
            submitted = run_indexers(clients.indexers, used)
            waited = wait_for_indexers(clients.indexers, used, submitted_at=submitted["submitted_at"])
            readiness = website_readiness(clients.search, captured["website_id"], captured["generation"], captured["captures"]) if waited["status"] == "success" else {"status": "not_checked"}
            result = {"status": "ready" if readiness["status"] == "ready" else "partial", "coverage": captured["completion"], "uploads": uploads, "submitted": submitted, "indexers": waited, "readiness": readiness}
        elif args.command == "web-verify":
            captured = load_manifest(runtime_path(args.validated_capture))
            result = website_readiness(clients.search, captured["website_id"], captured["generation"], captured["captures"])
        elif args.command == "web-refresh":
            previous = load_manifest(runtime_path(args.previous_capture)); current = load_manifest(runtime_path(args.current_capture))
            diff = capture_diff(previous, current)
            if diff["missing"] and args.confirm_remove != previous["website_id"]:
                result = {"status": "confirmation_required", "website_id": previous["website_id"], "diff": diff}
            else:
                selected = set(diff["changed"] + diff["added"])
                uploads = [upload_website_capture(clients.text_container, clients.image_container, page, [INTERNAL_GROUP]) for page in current["captures"] if page["page_id"] in selected]
                used = [config["AZURE_SEARCH_TEXT_INDEXER"]] + ([config["AZURE_SEARCH_IMAGE_INDEXER"]] if any(page.get("assets") for page in current["captures"] if page["page_id"] in selected) else [])
                submitted = run_indexers(clients.indexers, used); waited = wait_for_indexers(clients.indexers, used, submitted_at=submitted["submitted_at"])
                readiness = website_readiness(clients.search, current["website_id"], current["generation"], current["captures"]) if waited["status"] == "success" else {"status": "not_checked"}
                cleanup = None
                if readiness["status"] == "ready" and previous["generation"] != current["generation"]:
                    cleanup = delete_website_capture(clients.text_container, clients.image_container, previous["website_id"], previous["generation"])
                result = {"status": "ready" if readiness["status"] == "ready" else "partial", "diff": diff, "uploads": uploads, "submitted": submitted, "indexers": waited, "readiness": readiness, "old_generation_cleanup": cleanup}
        elif args.command == "web-verify-absent":
            absent_result = website_absent(clients.search, args.website_id)
            result = {"status": "absent" if absent_result else "stale_evidence", "website_id": args.website_id}
        else:
            if args.confirm != args.website_id: raise ValueError("web-delete confirmation must exactly match website id")
            deletion = delete_website_capture(clients.text_container, clients.image_container, args.website_id)
            used = [config["AZURE_SEARCH_TEXT_INDEXER"], config["AZURE_SEARCH_IMAGE_INDEXER"]]
            submitted = run_indexers(clients.indexers, used)
            absent_result = wait_for_website_absent(clients.search, args.website_id)
            result = dict(deletion, status="deleted" if absent_result and deletion["status"] == "deleted" else "partial", submitted=submitted, search_absent=absent_result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
