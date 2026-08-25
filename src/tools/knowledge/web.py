from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from capture_validation import validate_capture
from session import accept_observation, finalize_session, start_session
from url_validation import normalize_public_url, validate_public_target

__all__ = [
    "accept_observation", "capture_diff", "finalize_session",
    "load_manifest", "normalize_public_url", "start_session", "stable_id",
    "validate_capture", "validate_public_target",
]

STOP_REASONS = {
    "frontier_exhausted", "novelty_converged", "budget_exhausted", "blocked_boundary", "cancelled",
}


def stable_id(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def capture_diff(previous: dict, current: dict) -> dict:
    if previous.get("website_id") != current.get("website_id"):
        raise ValueError("refresh captures belong to different websites")

    old = {page["page_id"]: page for page in previous.get("captures", [])}
    new = {page["page_id"]: page for page in current.get("captures", [])}
    shared = set(old) & set(new)

    return {
        "unchanged": sorted(page_id for page_id in shared if old[page_id].get("content_hash") == new[page_id].get("content_hash")),
        "changed": sorted(page_id for page_id in shared if old[page_id].get("content_hash") != new[page_id].get("content_hash")),
        "added": sorted(set(new) - set(old)),
        "missing": sorted(set(old) - set(new)),
    }


def load_manifest(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("manifest file not found")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value
