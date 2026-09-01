from argparse import ArgumentParser
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any, Optional
import unicodedata
from urllib.parse import urlparse, urlsplit

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MODES = {"temporary", "save", "track", "watch"}
_CLAIM_TYPES = {"fact", "source-assertion", "inference", "recommendation", "unknown"}
_EVIDENCE_KINDS = {"text", "structured"}
logger = logging.getLogger(__name__)


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


def normalize_text(value: str) -> bytes:
    text = unicodedata.normalize("NFC", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).encode("utf-8")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def fingerprint(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def validate_first_party_endpoint(official_domain: str, endpoint: str) -> None:
    domain = str(official_domain or "").lower().strip(".")
    parts = urlsplit(str(endpoint or "").strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("endpoint must use http or https")
    host = (parts.hostname or "").lower().strip(".")
    if not domain or not host or (host != domain and not host.endswith("." + domain)):
        raise ValueError("data endpoint is not first-party")


def _unique_ids(items: list, label: str) -> set[str]:
    ids = [safe_id(item.get("id", "")) for item in items if isinstance(item, dict)]
    if len(ids) != len(items):
        raise ValueError(f"invalid {label}")
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {label} id")
    return set(ids)


def validate_dossier(data: dict) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 2:
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
    evidence = data.get("evidence")
    claims = data.get("claims")
    if not isinstance(sources, list) or not isinstance(evidence, list) or not isinstance(claims, list):
        raise ValueError("sources, evidence, and claims must be lists")

    source_ids = _unique_ids(sources, "source")
    evidence_ids = _unique_ids(evidence, "evidence")
    _unique_ids(claims, "claim")

    source_map = {}
    for source in sources:
        s_id = source.get("id")
        for key in (
            "title",
            "publisher",
            "retrieved_at",
            "access_status",
            "classification",
            "independence",
            "acquisition_method",
            "freshness",
            "fingerprint",
        ):
            _required_text(source, key)
        url = source.get("url")
        if url is not None and urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("source URL must use http or https")
        if url is None and not source.get("file_provenance"):
            raise ValueError("source needs URL or file_provenance")
        source_map[s_id] = source

    for item in evidence:
        s_id = _required_text(item, "source_id")
        if s_id not in source_ids:
            raise ValueError(f"evidence references unknown source: {s_id}")
        kind = _required_text(item, "kind")
        if kind not in _EVIDENCE_KINDS:
            raise ValueError("invalid evidence kind")
        val = item.get("value")
        if val is None:
            raise ValueError("evidence value is required")

        expected_fp = _required_text(item, "fingerprint")
        if kind == "text":
            if not isinstance(val, str) or not val.strip():
                raise ValueError("text evidence must be non-empty string")
            if len(val) > 4000:
                raise ValueError("text evidence exceeds 4000 chars")
            computed = fingerprint(normalize_text(val))
        else:
            canonical_bytes = canonical_json(val)
            if len(canonical_bytes) > 65536:
                raise ValueError("structured evidence exceeds 64 KiB")
            computed = fingerprint(canonical_bytes)

        if computed != expected_fp:
            raise ValueError(f"evidence fingerprint mismatch: expected {expected_fp}, computed {computed}")

    for claim in claims:
        if claim.get("type") not in _CLAIM_TYPES:
            raise ValueError("invalid claim type")
        _required_text(claim, "text")
        _required_text(claim, "confidence")
        _required_text(claim, "confidence_rationale")
        ev_ids = claim.get("evidence_ids", [])
        counter_ids = claim.get("counter_evidence_ids", [])
        missing = (set(ev_ids) | set(counter_ids)) - evidence_ids
        if missing:
            raise ValueError(f"missing evidence references: {sorted(missing)}")
        if claim["type"] in {"fact", "source-assertion", "recommendation"} and not ev_ids:
            raise ValueError("material claim needs missing evidence")

        if claim["type"] == "fact":
            for e_id in ev_ids:
                matching_ev = next(e for e in evidence if e["id"] == e_id)
                src = source_map[matching_ev["source_id"]]
                if src.get("classification") == "candidate":
                    raise ValueError("factual claim cannot cite candidate source evidence")


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


def archive_legacy_dossiers(workspace: Path) -> list:
    saved_root = runtime_root(workspace) / "saved"
    legacy_root = runtime_root(workspace) / "legacy-v1"
    archived = []
    if saved_root.is_dir():
        for path in list(saved_root.iterdir()):
            if path.is_dir():
                dossier_file = path / "dossier.json"
                if dossier_file.is_file():
                    try:
                        content = json.loads(dossier_file.read_text(encoding="utf-8"))
                        if content.get("schema_version") == 1:
                            target = legacy_root / path.name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(path), str(target))
                            archived.append(path.name)
                    except (json.JSONDecodeError, OSError) as exc:
                        logger.debug("Skipping unreadable legacy dossier at %s: %s", path, exc)
    return archived

def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "command",
        choices=("temporary", "save", "track", "watch", "load", "delete", "cleanup", "migrate-v1"),
    )
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--ttl", type=int, default=86400)
    args = parser.parse_args()
    try:
        if args.command == "load":
            result = load_dossier(args.workspace, args.id)
        elif args.command == "delete":
            delete_dossier(args.workspace, args.id)
            result = {"deleted": args.id}
        elif args.command == "cleanup":
            result = {"removed": cleanup_temporary(args.workspace, args.ttl)}
        elif args.command == "migrate-v1":
            result = {"archived_legacy_v1": archive_legacy_dossiers(args.workspace)}
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
