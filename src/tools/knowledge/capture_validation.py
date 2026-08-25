from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import socket
from typing import Callable

from session import stable_id
from url_validation import validate_public_target


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}


def _validate_asset(asset: dict, root: Path, resolver: Callable) -> dict:
    path = Path(str(asset.get("path", ""))).resolve()
    if not path.is_file() or root not in path.parents:
        raise ValueError("captured asset must be under runtime root")

    content = path.read_bytes()
    digest = str(asset.get("sha256", ""))
    if not digest or sha256(content).hexdigest() != digest:
        raise ValueError("captured asset digest does not match binary")
    if asset.get("byte_count") != len(content) or asset.get("mime_type") not in ALLOWED_IMAGE_TYPES:
        raise ValueError("captured asset metadata is malformed")

    asset_id = str(asset.get("asset_id", "")).strip()
    if not asset_id:
        raise ValueError("captured asset id is required")
    source_url = validate_public_target(str(asset.get("source_url", "")), resolver)
    return dict(asset, path=str(path), source_url=source_url)


def _normalize_page(
    session: dict,
    generation: str,
    page: dict,
    events: dict,
    root: Path,
    resolver: Callable,
) -> dict:
    event = events.get(page.get("event_id"))
    if not event:
        raise ValueError("capture page is not bound to an accepted observation")

    canonical = validate_public_target(page.get("canonical_url", ""), resolver)
    if canonical != event["canonical_url"]:
        raise ValueError("capture canonical URL differs from observation")
    text = str(page.get("rendered_text", "")).strip()
    if not text:
        raise ValueError("capture rendered text is required")

    assets = [_validate_asset(asset, root, resolver) for asset in page.get("assets", [])]
    media = list(page.get("media", []))
    semantic = {
        "text": " ".join(text.split()),
        "structure": page.get("semantic_structure", []),
        "assets": [
            {"asset_id": asset.get("asset_id"), "source_url": asset.get("source_url")}
            for asset in assets
        ],
        "media": media,
    }
    return {
        "website_id": session["website_id"],
        "page_id": stable_id("page", canonical),
        "generation": generation,
        "canonical_url": canonical,
        "title": str(page.get("title") or canonical),
        "rendered_text": text,
        "minimal_html": str(page.get("minimal_html", "")),
        "content_hash": sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest(),
        "assets": assets,
        "media": media,
        "event_id": event["event_id"],
    }


def validate_capture(
    session: dict,
    capture: dict,
    runtime_root: Path,
    resolver: Callable = socket.getaddrinfo,
) -> dict:
    if "completion" not in session or capture.get("session_id") != session["session_id"]:
        raise ValueError("capture is not bound to a finalized crawl session")

    generation = str(capture.get("generation", "")).strip()
    pages = capture.get("pages")
    if not generation or not isinstance(pages, list) or not pages:
        raise ValueError("capture generation and pages are required")

    root = runtime_root.resolve()
    if not root.is_dir():
        raise ValueError("runtime root must be an existing directory")
    events = {item["event_id"]: item for item in session["events"]}
    normalized = [
        _normalize_page(session, generation, page, events, root, resolver)
        for page in pages
    ]
    return {
        "session_id": session["session_id"],
        "website_id": session["website_id"],
        "generation": generation,
        "scope": session["scope"],
        "captures": normalized,
        "completion": session["completion"],
    }
