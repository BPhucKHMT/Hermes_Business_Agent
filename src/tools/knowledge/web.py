from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from hmac import compare_digest
from ipaddress import ip_address
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import json
import socket
import uuid

TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}
STOP_REASONS = {"frontier_exhausted", "novelty_converged", "budget_exhausted", "blocked_boundary", "cancelled"}


def normalize_public_url(value: str) -> str:
    parts = urlsplit((value or "").strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("website URL must use http or https")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("website URL must contain a public host without credentials")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("website URL contains an invalid port") from error
    scheme, host = parts.scheme.lower(), parts.hostname.lower().rstrip(".")
    default = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default else "%s:%d" % (host, port)
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted((key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in TRACKING_PARAMETERS), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def validate_public_target(value: str, resolver: Callable = socket.getaddrinfo) -> str:
    normalized = normalize_public_url(value)
    parts = urlsplit(normalized)
    try:
        answers = resolver(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as error:
        raise ValueError("website hostname could not be resolved") from error
    addresses = {answer[4][0].split("%", 1)[0] for answer in answers}
    if not addresses or any(not ip_address(address).is_global for address in addresses):
        raise ValueError("website hostname resolves to a non-public address")
    return normalized


def stable_id(prefix: str, value: str) -> str:
    return "%s-%s" % (prefix, sha256(value.encode("utf-8")).hexdigest()[:20])


def start_session(root_url, policy, scope: str, resolver=socket.getaddrinfo, now=None) -> dict:
    import time
    if scope not in {"page", "site"}:
        raise ValueError("crawl scope must be page or site")
    started = time.time() if now is None else now
    root = validate_public_target(root_url, resolver)
    snapshot = policy.as_dict()
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": 2, "session_id": str(uuid.uuid4()), "root_url": root, "scope": scope,
        "root_origin": "%s://%s" % (urlsplit(root).scheme, urlsplit(root).netloc),
        "website_id": stable_id("website", "%s://%s" % (urlsplit(root).scheme, urlsplit(root).netloc)),
        "policy": snapshot, "policy_digest": sha256(serialized.encode()).hexdigest(),
        "started_at": started, "deadline": started + snapshot["crawl_budget"]["wall_clock_seconds"],
        "resource_ledger": {"download_bytes": 0, "content_asset_bytes": 0, "screenshot_bytes": 0},
        "events": [], "semantic_fingerprints": [], "canonical_urls": [], "no_progress_count": 0,
    }


def accept_observation(session: dict, event: dict, resolver=socket.getaddrinfo) -> dict:
    result = deepcopy(session)
    policy_serialized = json.dumps(result.get("policy"), sort_keys=True, separators=(",", ":"))
    expected_digest = sha256(policy_serialized.encode()).hexdigest()
    if not compare_digest(str(result.get("policy_digest", "")), expected_digest):
        raise ValueError("crawl session policy was modified")
    required = {"event_id", "parent_event_id", "capability", "requested_url", "final_url", "canonical_url", "started_at", "finished_at", "download_bytes", "content_asset_bytes", "screenshot_bytes", "semantic_fingerprint", "links", "artifacts"}
    if not isinstance(event, dict) or not required.issubset(event):
        raise ValueError("observation event is malformed")
    ids = {item["event_id"] for item in result["events"]}
    if not event["event_id"] or event["event_id"] in ids:
        raise ValueError("duplicate observation event id")
    if result["events"] and event["parent_event_id"] not in ids:
        raise ValueError("observation parent event is unknown")
    if not result["events"] and event["parent_event_id"] is not None:
        raise ValueError("root observation cannot have a parent")
    requested = validate_public_target(event["requested_url"], resolver)
    final = validate_public_target(event["final_url"], resolver)
    canonical = validate_public_target(event["canonical_url"], resolver)
    origin = lambda url: (urlsplit(url).scheme, urlsplit(url).netloc)
    if origin(final) != origin(result["root_url"]) or origin(canonical) != origin(result["root_url"]):
        raise ValueError("observation left approved origin")
    if event["finished_at"] < event["started_at"] or event["finished_at"] > result["deadline"]:
        raise ValueError("observation exceeded time budget")
    for field in ("download_bytes", "content_asset_bytes", "screenshot_bytes"):
        if type(event[field]) is not int or event[field] < 0:
            raise ValueError("observation byte counts must be non-negative integers")
        result["resource_ledger"][field] += event[field]
        if result["resource_ledger"][field] > result["policy"]["crawl_budget"][field]:
            raise ValueError("observation exceeded byte budget")
    fingerprint = str(event["semantic_fingerprint"]).strip()
    artifacts = event.get("artifacts", [])
    if event.get("executor") != "hermes-crawl4ai" or event["finished_at"] <= event["started_at"] or event["download_bytes"] <= 0 or not artifacts:
        raise ValueError("observation requires a trusted artifact from hermes-crawl4ai")
    for artifact in artifacts:
        path = Path(str(artifact.get("path", "")))
        if not path.is_file() or not str(artifact.get("digest", "")).strip():
            raise ValueError("trusted artifact is missing or unbound")
    progress = canonical not in result["canonical_urls"] or (fingerprint and fingerprint not in result["semantic_fingerprints"])
    result["no_progress_count"] = 0 if progress else result["no_progress_count"] + 1
    if result["no_progress_count"] > result["policy"]["crawl_budget"]["consecutive_no_progress"]:
        raise ValueError("observation exceeded no-progress budget")
    normalized = dict(event, requested_url=requested, final_url=final, canonical_url=canonical, derived_progress=progress)
    result["events"].append(normalized)
    if canonical not in result["canonical_urls"]: result["canonical_urls"].append(canonical)
    if fingerprint and fingerprint not in result["semantic_fingerprints"]: result["semantic_fingerprints"].append(fingerprint)
    return result


def finalize_session(session: dict, stop_reason: str, unresolved_frontier: list) -> dict:
    if stop_reason not in STOP_REASONS:
        raise ValueError("invalid crawl stop reason")
    if not session["events"]:
        raise ValueError("crawl session has no observations")
    if stop_reason == "frontier_exhausted" and unresolved_frontier:
        raise ValueError("frontier_exhausted cannot retain unresolved frontier")
    result = deepcopy(session)
    result["completion"] = {"stop_reason": stop_reason, "unresolved_frontier": list(unresolved_frontier), "coverage": {"observed_urls": len(session["canonical_urls"]), "semantic_states": len(session["semantic_fingerprints"])}}
    return result


def validate_capture(session: dict, capture: dict, runtime_root: Path, resolver=socket.getaddrinfo) -> dict:
    if "completion" not in session or capture.get("session_id") != session["session_id"]:
        raise ValueError("capture is not bound to a finalized crawl session")
    generation = str(capture.get("generation", "")).strip()
    pages = capture.get("pages")
    if not generation or not isinstance(pages, list) or not pages:
        raise ValueError("capture generation and pages are required")
    events = {item["event_id"]: item for item in session["events"]}
    root = runtime_root.resolve()
    if not root.is_dir(): raise ValueError("runtime root must be an existing directory")
    normalized = []
    for page in pages:
        event = events.get(page.get("event_id"))
        if not event: raise ValueError("capture page is not bound to an accepted observation")
        canonical = validate_public_target(page.get("canonical_url", ""), resolver)
        if canonical != event["canonical_url"]: raise ValueError("capture canonical URL differs from observation")
        text = str(page.get("rendered_text", "")).strip()
        if not text: raise ValueError("capture rendered text is required")
        assets = []
        for asset in page.get("assets", []):
            path = Path(str(asset.get("path", ""))).resolve()
            if not path.is_file() or root not in path.parents:
                raise ValueError("captured asset must be under runtime root")
            content = path.read_bytes()
            digest = str(asset.get("sha256", ""))
            if not digest or sha256(content).hexdigest() != digest:
                raise ValueError("captured asset digest does not match binary")
            if asset.get("byte_count") != len(content) or asset.get("mime_type") not in {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}:
                raise ValueError("captured asset metadata is malformed")
            source_url = validate_public_target(str(asset.get("source_url", "")), resolver)
            asset_id = str(asset.get("asset_id", "")).strip()
            if not asset_id:
                raise ValueError("captured asset id is required")
            assets.append(dict(asset, path=str(path), source_url=source_url))
        semantic = {"text": " ".join(text.split()), "structure": page.get("semantic_structure", []), "assets": [{"asset_id": x.get("asset_id"), "source_url": x.get("source_url")} for x in assets], "media": page.get("media", [])}
        normalized.append({"website_id": session["website_id"], "page_id": stable_id("page", canonical), "generation": generation, "canonical_url": canonical, "title": str(page.get("title") or canonical), "rendered_text": text, "minimal_html": str(page.get("minimal_html", "")), "content_hash": sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest(), "assets": assets, "media": list(page.get("media", [])), "event_id": event["event_id"]})
    return {"session_id": session["session_id"], "website_id": session["website_id"], "generation": generation, "scope": session["scope"], "captures": normalized, "completion": session["completion"]}


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
    if not path.is_file(): raise ValueError("manifest file not found")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError("manifest must be a JSON object")
    return value
