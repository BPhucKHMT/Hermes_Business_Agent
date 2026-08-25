import json
import os
from pathlib import Path
import sys

from cli import build_parser
from clients import create_clients, load_config

WORKSPACE_FLAG = "--workspace"
from indexing import (
    indexer_status,
    run_indexers,
    wait_for_indexers,
    wait_for_website_absent,
    website_absent,
    website_readiness,
)
from policy import load_website_policy
from provision import provision
from retrieval import knowledge_search, knowledge_search_many
from storage import (
    delete_source,
    delete_website_capture,
    upload_source,
    upload_website_capture,
)
from web import (
    accept_observation,
    capture_diff,
    finalize_session,
    load_manifest,
    start_session,
    validate_capture,
)

INTERNAL_GROUP = "internal"
RUNTIME = Path(".runtime/knowledge/web-sessions")


def load_env(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"environment file not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip())


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


def run_offline_command(args):
    if args.command == "web-start":
        result = start_session(args.url, load_website_policy(Path(args.policy)), args.scope)
        path = RUNTIME / f"{result['session_id']}.json"
        atomic_json(path, result)
        result = {"status": "started", "session": str(path), "crawl": result}

    elif args.command == "web-crawl":
        from crawl import trusted_crawl

        crawled = trusted_crawl(args.url, load_website_policy(Path(args.policy)), RUNTIME, args.scope)
        session_path = RUNTIME / f"{crawled['session']['session_id']}.json"
        validated_path = RUNTIME / f"{crawled['session']['session_id']}.validated.json"
        atomic_json(session_path, crawled["session"])
        atomic_json(validated_path, crawled["validated"])
        result = {
            "status": "captured",
            "session": str(session_path),
            "validated_capture": str(validated_path),
            "coverage": crawled["validated"]["completion"]["coverage"],
            "artifacts": crawled["artifacts"],
        }

    elif args.command == "web-observe":
        path = runtime_path(args.session)
        result = accept_observation(load_manifest(path), load_manifest(Path(args.event)))
        atomic_json(path, result)

    elif args.command == "web-finalize":
        path = runtime_path(args.session)
        frontier = (
            json.loads(Path(args.unresolved_frontier).read_text(encoding="utf-8"))
            if args.unresolved_frontier
            else []
        )
        session = finalize_session(load_manifest(path), args.stop_reason, frontier)
        result = validate_capture(session, load_manifest(Path(args.capture)), Path.cwd())
        output = RUNTIME / f"{session['session_id']}.validated.json"
        atomic_json(output, result)
        result = {"status": "validated", "validated_capture": str(output), "capture": result}

    return result


def run_basic_command(args, clients, config, image_indexer_enabled):
    if args.command == "provision":
        result = provision(clients, config)

    elif args.command == "upload":
        path = Path(args.file)
        result = upload_source(
            clients.layout_container,
            clients.text_container,
            args.source_path or path.name,
            path.read_bytes(),
            [INTERNAL_GROUP],
            workspace=getattr(args, "workspace", None),
        )

    elif args.command == "delete":
        result = delete_source(clients.layout_container, clients.text_container, args.source_path)

    elif args.command == "index":
        result = run_indexers(
            clients.indexers,
            [config["AZURE_SEARCH_LAYOUT_INDEXER"], config["AZURE_SEARCH_TEXT_INDEXER"]],
        )

    elif args.command == "status":
        status_indexers = ["AZURE_SEARCH_LAYOUT_INDEXER", "AZURE_SEARCH_TEXT_INDEXER"]
        if image_indexer_enabled:
            status_indexers.append("AZURE_SEARCH_IMAGE_INDEXER")
        result = {name: indexer_status(clients.indexers, config[name]) for name in status_indexers}

    elif args.command == "search":
        if args.generation and not args.website_id:
            raise ValueError("--generation requires --website-id")
        queries = [args.query] + args.query_variant
        workspace = getattr(args, "workspace", None)
        if args.query_variant:
            search_res = knowledge_search_many(
                clients.search,
                queries,
                [INTERNAL_GROUP],
                args.top_k,
                source_path=args.source_path,
                website_id=args.website_id,
                generation=args.generation,
                workspace=workspace,
            )
        else:
            search_res = knowledge_search(
                clients.search,
                args.query,
                [INTERNAL_GROUP],
                args.top_k,
                source_path=args.source_path,
                website_id=args.website_id,
                generation=args.generation,
                workspace=workspace,
            )
        result = search_res.to_dict()

    return result


def run_refresh_command(args, clients, config, image_indexer_enabled):
    previous = load_manifest(runtime_path(args.previous_capture))
    current = load_manifest(runtime_path(args.current_capture))
    diff = capture_diff(previous, current)

    if diff["missing"] and args.confirm_remove != previous["website_id"]:
        result = {
            "status": "confirmation_required",
            "website_id": previous["website_id"],
            "diff": diff,
        }
    else:
        selected = set(diff["changed"] + diff["added"])
        uploads = [
            upload_website_capture(
                clients.text_container,
                clients.image_container if image_indexer_enabled else None,
                page,
                [INTERNAL_GROUP],
            )
            for page in current["captures"]
            if page["page_id"] in selected
        ]
        used = [config["AZURE_SEARCH_TEXT_INDEXER"]]
        if image_indexer_enabled and any(page.get("assets") for page in current["captures"] if page["page_id"] in selected):
            used.append(config["AZURE_SEARCH_IMAGE_INDEXER"])

        submitted = run_indexers(clients.indexers, used)
        waited = wait_for_indexers(clients.indexers, used, submitted_at=submitted["submitted_at"])
        readiness = (
            website_readiness(clients.search, current["website_id"], current["generation"], current["captures"])
            if waited["status"] == "success"
            else {"status": "not_checked"}
        )
        cleanup = None
        if readiness["status"] == "ready" and previous["generation"] != current["generation"]:
            cleanup = delete_website_capture(
                clients.text_container,
                clients.image_container,
                previous["website_id"],
                previous["generation"],
            )
        result = {
            "status": "ready" if readiness["status"] == "ready" else "partial",
            "diff": diff,
            "uploads": uploads,
            "submitted": submitted,
            "indexers": waited,
            "readiness": readiness,
            "old_generation_cleanup": cleanup,
        }
    return result


def run_website_command(args, clients, config, image_indexer_enabled):
    if args.command == "web-ingest":
        captured = load_manifest(runtime_path(args.validated_capture))
        if not captured.get("session_id") or not captured.get("completion") or not captured.get("captures"):
            raise ValueError("web-ingest requires a finalized validated capture")

        ws = getattr(args, "workspace", None) or captured.get("workspace")
        uploads = [
            upload_website_capture(
                clients.text_container,
                clients.image_container if image_indexer_enabled else None,
                page,
                [INTERNAL_GROUP],
                workspace=ws,
            )
            for page in captured["captures"]
        ]
        used = [config["AZURE_SEARCH_TEXT_INDEXER"]]
        if image_indexer_enabled and any(page.get("assets") for page in captured["captures"]):
            used.append(config["AZURE_SEARCH_IMAGE_INDEXER"])

        submitted = run_indexers(clients.indexers, used)
        waited = wait_for_indexers(clients.indexers, used, submitted_at=submitted["submitted_at"])
        readiness = (
            website_readiness(clients.search, captured["website_id"], captured["generation"], captured["captures"])
            if waited["status"] == "success"
            else {"status": "not_checked"}
        )
        result = {
            "status": "ready" if readiness["status"] == "ready" else "partial",
            "coverage": captured["completion"],
            "uploads": uploads,
            "submitted": submitted,
            "indexers": waited,
            "readiness": readiness,
        }

    elif args.command == "web-verify":
        captured = load_manifest(runtime_path(args.validated_capture))
        result = website_readiness(
            clients.search,
            captured["website_id"],
            captured["generation"],
            captured["captures"],
        )

    elif args.command == "web-refresh":
        result = run_refresh_command(args, clients, config, image_indexer_enabled)

    elif args.command == "web-verify-absent":
        absent_result = website_absent(clients.search, args.website_id)
        result = {
            "status": "absent" if absent_result else "stale_evidence",
            "website_id": args.website_id,
        }

    else:
        if args.confirm != args.website_id:
            raise ValueError("web-delete confirmation must exactly match website id")

        deletion = delete_website_capture(clients.text_container, clients.image_container, args.website_id)
        used = [config["AZURE_SEARCH_TEXT_INDEXER"]]
        if image_indexer_enabled:
            used.append(config["AZURE_SEARCH_IMAGE_INDEXER"])
        submitted = run_indexers(clients.indexers, used)
        absent_result = wait_for_website_absent(clients.search, args.website_id)
        result = dict(
            deletion,
            status="deleted" if absent_result and deletion["status"] == "deleted" else "partial",
            submitted=submitted,
            search_absent=absent_result,
        )

    return result


def run_azure_command(args):
    load_env(Path(args.env_file))
    config = load_config()
    clients = create_clients(config)
    image_indexer_enabled = os.environ.get("HERMES_IMAGE_INDEXER", "true").strip().lower() not in {
        "false", "0", "no", "off",
    }
    basic = {"provision", "upload", "delete", "index", "status", "search"}
    runner = run_basic_command if args.command in basic else run_website_command
    return runner(args, clients, config, image_indexer_enabled)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    offline = {"web-start", "web-crawl", "web-observe", "web-finalize"}
    result = run_offline_command(args) if args.command in offline else run_azure_command(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
