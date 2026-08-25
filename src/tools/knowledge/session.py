from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path
import socket
import time
from typing import Callable
from urllib.parse import urlsplit
import uuid

from url_validation import validate_public_target

STOP_REASONS = {
    "frontier_exhausted", "novelty_converged", "budget_exhausted", "blocked_boundary", "cancelled",
}


def stable_id(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def start_session(
    root_url: str,
    policy,
    scope: str,
    resolver: Callable = socket.getaddrinfo,
    now: float | None = None,
) -> dict:
    if scope not in {"page", "site"}:
        raise ValueError("crawl scope must be page or site")
    started = time.time() if now is None else now
    root = validate_public_target(root_url, resolver)
    snapshot = policy.as_dict()
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    origin = f"{urlsplit(root).scheme}://{urlsplit(root).netloc}"

    return {
        "schema_version": 2,
        "session_id": str(uuid.uuid4()),
        "root_url": root,
        "scope": scope,
        "root_origin": origin,
        "website_id": stable_id("website", origin),
        "policy": snapshot,
        "policy_digest": sha256(serialized.encode()).hexdigest(),
        "started_at": started,
        "deadline": started + snapshot["crawl_budget"]["wall_clock_seconds"],
        "resource_ledger": {
            "download_bytes": 0,
            "content_asset_bytes": 0,
            "screenshot_bytes": 0,
        },
        "events": [],
        "semantic_fingerprints": [],
        "canonical_urls": [],
        "no_progress_count": 0,
    }


def _validate_policy(session: dict) -> None:
    serialized = json.dumps(session.get("policy"), sort_keys=True, separators=(",", ":"))
    expected = sha256(serialized.encode()).hexdigest()
    if not compare_digest(str(session.get("policy_digest", "")), expected):
        raise ValueError("crawl session policy was modified")


def _validate_event_identity(session: dict, event: dict) -> None:
    required = {
        "event_id", "parent_event_id", "capability", "requested_url", "final_url",
        "canonical_url", "started_at", "finished_at", "download_bytes",
        "content_asset_bytes", "screenshot_bytes", "semantic_fingerprint",
        "links", "artifacts",
    }
    if not isinstance(event, dict) or not required.issubset(event):
        raise ValueError("observation event is malformed")

    event_ids = {item["event_id"] for item in session["events"]}
    if not event["event_id"] or event["event_id"] in event_ids:
        raise ValueError("duplicate observation event id")
    if session["events"] and event["parent_event_id"] not in event_ids:
        raise ValueError("observation parent event is unknown")
    if not session["events"] and event["parent_event_id"] is not None:
        raise ValueError("root observation cannot have a parent")


def _validate_event_urls(session: dict, event: dict, resolver: Callable) -> tuple[str, str, str]:
    requested = validate_public_target(event["requested_url"], resolver)
    final = validate_public_target(event["final_url"], resolver)
    canonical = validate_public_target(event["canonical_url"], resolver)
    root_origin = urlsplit(session["root_url"])[0:2]
    if urlsplit(final)[0:2] != root_origin or urlsplit(canonical)[0:2] != root_origin:
        raise ValueError("observation left approved origin")
    return requested, final, canonical


def _apply_event_budget(session: dict, event: dict) -> None:
    if event["finished_at"] < event["started_at"] or event["finished_at"] > session["deadline"]:
        raise ValueError("observation exceeded time budget")
    for field in ("download_bytes", "content_asset_bytes", "screenshot_bytes"):
        if type(event[field]) is not int or event[field] < 0:
            raise ValueError("observation byte counts must be non-negative integers")
        session["resource_ledger"][field] += event[field]
        if session["resource_ledger"][field] > session["policy"]["crawl_budget"][field]:
            raise ValueError("observation exceeded byte budget")


def _validate_artifacts(event: dict) -> None:
    artifacts = event.get("artifacts", [])
    if (
        event.get("executor") != "hermes-crawl4ai"
        or event["finished_at"] <= event["started_at"]
        or event["download_bytes"] <= 0
        or not artifacts
    ):
        raise ValueError("observation requires a trusted artifact from hermes-crawl4ai")
    for artifact in artifacts:
        path = Path(str(artifact.get("path", "")))
        if not path.is_file() or not str(artifact.get("digest", "")).strip():
            raise ValueError("trusted artifact is missing or unbound")


def _record_progress(session: dict, canonical: str, fingerprint: str) -> bool:
    progress = canonical not in session["canonical_urls"] or (
        fingerprint and fingerprint not in session["semantic_fingerprints"]
    )
    session["no_progress_count"] = 0 if progress else session["no_progress_count"] + 1
    if session["no_progress_count"] > session["policy"]["crawl_budget"]["consecutive_no_progress"]:
        raise ValueError("observation exceeded no-progress budget")
    if canonical not in session["canonical_urls"]:
        session["canonical_urls"].append(canonical)
    if fingerprint and fingerprint not in session["semantic_fingerprints"]:
        session["semantic_fingerprints"].append(fingerprint)
    return progress


def accept_observation(
    session: dict,
    event: dict,
    resolver: Callable = socket.getaddrinfo,
) -> dict:
    result = deepcopy(session)
    _validate_policy(result)
    _validate_event_identity(result, event)
    requested, final, canonical = _validate_event_urls(result, event, resolver)
    _apply_event_budget(result, event)
    _validate_artifacts(event)

    fingerprint = str(event["semantic_fingerprint"]).strip()
    progress = _record_progress(result, canonical, fingerprint)
    result["events"].append(dict(
        event,
        requested_url=requested,
        final_url=final,
        canonical_url=canonical,
        derived_progress=progress,
    ))
    return result


def finalize_session(session: dict, stop_reason: str, unresolved_frontier: list) -> dict:
    if stop_reason not in STOP_REASONS:
        raise ValueError("invalid crawl stop reason")
    if not session["events"]:
        raise ValueError("crawl session has no observations")
    if stop_reason == "frontier_exhausted" and unresolved_frontier:
        raise ValueError("frontier_exhausted cannot retain unresolved frontier")

    result = deepcopy(session)
    result["completion"] = {
        "stop_reason": stop_reason,
        "unresolved_frontier": list(unresolved_frontier),
        "coverage": {
            "observed_urls": len(session["canonical_urls"]),
            "semantic_states": len(session["semantic_fingerprints"]),
        },
    }
    return result
