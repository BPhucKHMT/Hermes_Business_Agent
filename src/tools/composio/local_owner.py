"""Explicit single-installation owner binding for native Google integrations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

_SCHEMA_VERSION = 1
_OWNER_RELATIVE_PATH = Path(".runtime") / "google" / "local-owner.json"


def _default_owner_path() -> Path:
    return Path(__file__).resolve().parents[2] / _OWNER_RELATIVE_PATH


def _validate_payload(payload: object, path: Path) -> str:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "owner_id"}
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != _SCHEMA_VERSION
    ):
        raise LookupError(f"invalid local owner binding: {path}")
    owner_id = payload.get("owner_id")
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise LookupError(f"invalid local owner binding: {path}")
    try:
        return str(UUID(owner_id.strip()))
    except (ValueError, AttributeError) as exc:
        raise LookupError(f"invalid local owner binding: {path}") from exc


def load_local_owner(path: Path | None = None) -> str | None:
    """Load a validated owner UUID, returning ``None`` when unprovisioned."""
    owner_path = Path(path) if path is not None else _default_owner_path()
    try:
        raw = owner_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise LookupError(f"cannot read local owner binding: {owner_path}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LookupError(f"invalid local owner binding: {owner_path}") from exc
    return _validate_payload(payload, owner_path)


def ensure_local_owner(root: Path) -> str:
    """Provision an installation owner exactly once under ``root``."""
    owner_path = Path(root) / _OWNER_RELATIVE_PATH
    try:
        existing = load_local_owner(owner_path)
    except LookupError:
        raise
    if existing is not None:
        return existing

    owner_path.parent.mkdir(parents=True, exist_ok=True)
    owner_id = str(uuid4())
    payload = json.dumps(
        {"schema_version": _SCHEMA_VERSION, "owner_id": owner_id},
        separators=(",", ":"),
    )
    try:
        descriptor = os.open(
            owner_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        existing = load_local_owner(owner_path)
        if existing is None:
            raise LookupError(f"local owner binding disappeared: {owner_path}")
        return existing
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            owner_path.unlink()
        except OSError:
            pass
        raise
    return owner_id
