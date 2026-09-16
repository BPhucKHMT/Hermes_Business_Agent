"""Google Workspace link parsing with strict host/path allowlisting.

Only recognized Google hosts and resource path shapes are accepted. The module
returns stable resource identifiers (file IDs, document IDs, optional
sheet/tab selectors). It never fetches URLs and never follows redirects; those
belong to authenticated tool layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_GOOGLE_HOSTS = frozenset(
    {
        "docs.google.com",
        "drive.google.com",
        "sheets.google.com",
        "slides.google.com",
    }
)


@dataclass(frozen=True)
class GoogleResource:
    """A resolved Google resource reference from a user-pasted link."""

    service: str  # drive | docs | sheets | slides
    resource_id: str
    kind: str  # file | folder | document | spreadsheet | presentation
    selector: str | None = None  # gid / range / slide object id when present
    resource_key: str | None = None


def is_google_url(url: str) -> bool:
    """Return True only for recognized Google document hosts."""
    try:
        parsed = urlparse(str(url).strip())
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and parsed.netloc.lower() in _GOOGLE_HOSTS


def parse_google_url(url: str) -> GoogleResource | None:
    """Parse a Google link into a resource reference, or None if unrecognized.

    Accepted shapes (path prefixes):
      /document/d/<id>          -> docs
      /spreadsheets/d/<id>      -> sheets (optionally /edit#gid=<gid>)
      /presentation/d/<id>      -> slides
      /file/d/<id>              -> drive file
      /drive/folders/<id>       -> drive folder
      /drive/u/*/folders/<id>   -> drive folder (multi-account path)
      /open?id=<id>&resourcekey -> drive generic
    """
    if not is_google_url(url):
        return None
    parsed = urlparse(str(url).strip())
    path = parsed.path
    query = parse_qs(parsed.query)
    fragment = parsed.fragment  # sheets uses #gid=123

    gid = None
    if fragment.startswith("gid="):
        gid = fragment[4:]
    elif "gid" in query:
        gid = query["gid"][0]

    resource_key = query.get("resourcekey", [None])[0]

    for prefix, service, kind in (
        ("/document/d/", "docs", "document"),
        ("/spreadsheets/d/", "sheets", "spreadsheet"),
        ("/presentation/d/", "slides", "presentation"),
        ("/file/d/", "drive", "file"),
        ("/drive/folders/", "drive", "folder"),
    ):
        if prefix in path:
            tail = path.split(prefix, 1)[1]
            resource_id = tail.split("/", 1)[0]
            if not resource_id:
                return None
            return GoogleResource(service, resource_id, kind, gid, resource_key)

    if path.startswith("/drive/u/") and "/folders/" in path:
        tail = path.rsplit("/folders/", 1)[1]
        resource_id = tail.split("/", 1)[0]
        if resource_id:
            return GoogleResource("drive", resource_id, "folder", gid, resource_key)

    if path in ("/open", "/file", "/d") or path.startswith("/open"):
        generic_id = query.get("id", [None])[0]
        if generic_id:
            return GoogleResource("drive", generic_id, "file", gid, resource_key)

    return None


def extract_google_links(text: str) -> list[str]:
    """Extract candidate Google URLs from free-form user text."""
    if not text:
        return []
    candidates: list[str] = []
    for token in str(text).replace("<", " ").replace(">", " ").split():
        candidate = token.strip().rstrip(".,;:!?)]}\"'")
        if is_google_url(candidate):
            candidates.append(candidate)
    return candidates
