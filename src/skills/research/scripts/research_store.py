from argparse import ArgumentParser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import json
import os
import re
import shutil
import tempfile
import time

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MODES = {"temporary", "save", "track", "watch"}
_CLAIM_TYPES = {"fact", "source-assertion", "inference", "recommendation", "unknown"}


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value) or value in {".", ".."}:
        raise ValueError("invalid id: use lowercase ASCII letters, digits, dot, underscore, or hyphen")
    return value


def runtime_root(workspace: Path) -> Path:
    return Path(workspace).resolve() / ".runtime" / "research"


def _required_text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {key}")
    return value


def _unique_ids(items: list, label: str) -> set[str]:
    ids = [safe_id(item.get("id", "")) for item in items if isinstance(item, dict)]
    if len(ids) != len(items):
        raise ValueError(f"invalid {label}")
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {label} id")
    return set(ids)


def validate_dossier(data: dict) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")
    safe_id(_required_text(data, "dossier_id"))
    safe_id(_required_text(data, "session_id"))
    mode = data.get("mode")
    if mode not in _MODES:
        raise ValueError("invalid mode")
    for key in ("question", "scope", "created_at", "updated_at", "executive_answer", "method"):
        _required_text(data, key)
    if mode == "watch" and not isinstance(data.get("watch_intent"), dict):
        raise ValueError("watch mode requires watch_intent")

    sources = data.get("sources")
    claims = data.get("claims")
    if not isinstance(sources, list) or not isinstance(claims, list):
        raise ValueError("sources and claims must be lists")
    source_ids = _unique_ids(sources, "source")
    _unique_ids(claims, "claim")

    for source in sources:
        for key in ("title", "publisher", "retrieved_at", "access_status", "classification", "independence", "fingerprint"):
            _required_text(source, key)
        url = source.get("url")
        if url is not None and urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("source URL must use http or https")
        if url is None and not source.get("file_provenance"):
            raise ValueError("source needs URL or file_provenance")

    for claim in claims:
        if claim.get("type") not in _CLAIM_TYPES:
            raise ValueError("invalid claim type")
        _required_text(claim, "text")
        _required_text(claim, "confidence")
        _required_text(claim, "confidence_rationale")
        evidence = claim.get("evidence_ids", [])
        counter = claim.get("counter_evidence_ids", [])
        missing = (set(evidence) | set(counter)) - source_ids
        if missing:
            raise ValueError(f"missing source references: {sorted(missing)}")
        if claim["type"] in {"fact", "source-assertion", "recommendation"} and not evidence:
            raise ValueError("material claim needs evidence")


def _atomic_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".write-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return path


def write_temporary(workspace: Path, session_id: str, dossier: dict) -> Path:
    session_id = safe_id(session_id)
    data = dict(dossier, session_id=session_id, mode="temporary")
    validate_dossier(data)
    return _atomic_json(runtime_root(workspace) / "temporary" / session_id / "dossier.json", data)


def save_dossier(workspace: Path, dossier_id: str, dossier: dict, mode: str = "save") -> Path:
    dossier_id = safe_id(dossier_id)
    if mode not in {"save", "track", "watch"}:
        raise ValueError("durable mode must be save, track, or watch")
    data = dict(dossier, dossier_id=dossier_id, mode=mode)
    validate_dossier(data)
    return _atomic_json(runtime_root(workspace) / "saved" / dossier_id / "dossier.json", data)


def load_dossier(workspace: Path, dossier_id: str) -> dict:
    path = runtime_root(workspace) / "saved" / safe_id(dossier_id) / "dossier.json"
    if not path.is_file():
        raise FileNotFoundError(f"saved dossier not found: {dossier_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_dossier(data)
    return data


def delete_dossier(workspace: Path, dossier_id: str) -> None:
    path = runtime_root(workspace) / "saved" / safe_id(dossier_id)
    if not path.is_dir():
        raise FileNotFoundError(f"saved dossier not found: {dossier_id}")
    shutil.rmtree(path)


def cleanup_temporary(workspace: Path, ttl_seconds: int, now: Optional[float] = None) -> list:
    if ttl_seconds < 0:
        raise ValueError("ttl_seconds must be non-negative")
    root = runtime_root(workspace) / "temporary"
    removed = []
    cutoff = (time.time() if now is None else now) - ttl_seconds
    if root.is_dir():
        for path in root.iterdir():
            if path.is_dir() and path.stat().st_mtime < cutoff:
                safe_id(path.name)
                shutil.rmtree(path)
                removed.append(path.name)
    return removed


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("command", choices=("temporary", "save", "track", "watch", "load", "delete", "cleanup"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--ttl", type=int, default=86400)
    args = parser.parse_args()
    try:
        if args.command == "load":
            result = load_dossier(args.workspace, args.id)
        elif args.command == "delete":
            delete_dossier(args.workspace, args.id); result = {"deleted": args.id}
        elif args.command == "cleanup":
            result = {"removed": cleanup_temporary(args.workspace, args.ttl)}
        else:
            if not args.input:
                raise ValueError("--input is required")
            data = json.loads(args.input.read_text(encoding="utf-8"))
            if args.command == "temporary":
                path = write_temporary(args.workspace, args.id or data.get("session_id", ""), data)
            else:
                path = save_dossier(args.workspace, args.id or data.get("dossier_id", ""), data, args.command)
            result = {"path": str(path.resolve())}
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
