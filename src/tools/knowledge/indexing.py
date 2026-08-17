from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic, sleep
from typing import Callable, Iterable, Mapping


def run_indexers(client, indexer_names: Iterable[str]) -> Mapping[str, object]:
    names = [name.strip() for name in indexer_names if name and name.strip()]
    if not names:
        raise ValueError("at least one indexer name is required")
    submitted_at = datetime.now(timezone.utc)
    for name in names:
        client.run_indexer(name)
    return {"status": "submitted", "indexers": names, "submitted_at": submitted_at.isoformat()}


def indexer_status(client, indexer_name: str) -> Mapping[str, object]:
    if not indexer_name.strip():
        raise ValueError("indexer name is required")
    latest = client.get_indexer_status(indexer_name).last_result
    if latest is None:
        return {"status": "never_run", "error": None}
    value = str(getattr(latest.status, "value", latest.status)).lower()
    return {"status": value, "error": "indexer_failed" if value in {"error", "transientfailure"} else None}


def _literal(value: str) -> str:
    return value.replace("'", "''")


def website_readiness(search_client, website_id: str, generation: str, pages: Iterable[Mapping[str, str]]) -> Mapping[str, object]:
    pages = list(pages)
    expected = {str(page["page_id"]): str(page["canonical_url"]) for page in pages}
    expected_assets = {str(asset["asset_id"]) for page in pages for asset in page.get("assets", [])}
    if not website_id.strip() or not generation.strip() or not expected:
        raise ValueError("website, generation, and expected pages are required")
    rows = search_client.search(
        search_text="*",
        filter="website_id eq '%s' and generation eq '%s'" % (_literal(website_id), _literal(generation)),
        select=["page_id", "source_url", "asset_id", "evidence_type"],
        top=max((len(expected) + len(expected_assets)) * 2, 1),
    )
    rows = list(rows)
    actual = {(str(row.get("page_id", "")), str(row.get("source_url", ""))) for row in rows if row.get("evidence_type") == "page_text" or not row.get("asset_id")}
    actual_assets = {str(row.get("asset_id")) for row in rows if row.get("asset_id") and row.get("evidence_type") in {"image_ocr", "image_description"}}
    ready = sorted(page_id for page_id, source_url in expected.items() if (page_id, source_url) in actual)
    missing = sorted(set(expected) - set(ready))
    ready_assets = sorted(expected_assets & actual_assets)
    missing_assets = sorted(expected_assets - actual_assets)
    return {
        "status": "ready" if not missing and not missing_assets else "partial",
        "selected_url_count": len(expected),
        "ready_url_count": len(ready),
        "ready_page_ids": ready,
        "missing_page_ids": missing,
        "selected_asset_count": len(expected_assets),
        "ready_asset_count": len(ready_assets),
        "ready_asset_ids": ready_assets,
        "missing_asset_ids": missing_assets,
    }


def website_absent(search_client, website_id: str) -> bool:
    if not website_id.strip():
        raise ValueError("website id is required")
    rows = search_client.search(
        search_text="*",
        filter="website_id eq '%s'" % _literal(website_id),
        select=["page_id"],
        top=1,
    )
    return next(iter(rows), None) is None


def wait_for_website_absent(search_client, website_id: str, timeout_seconds: float = 300, interval_seconds: float = 2,
                            clock: Callable[[], float] = monotonic, pause: Callable[[float], None] = sleep) -> bool:
    if timeout_seconds <= 0 or interval_seconds < 0:
        raise ValueError("positive timeout and non-negative interval are required")
    deadline = clock() + timeout_seconds
    while True:
        if website_absent(search_client, website_id):
            return True
        if clock() >= deadline:
            return False
        pause(interval_seconds)


def wait_for_indexers(client, indexer_names: Iterable[str], timeout_seconds: float = 300, interval_seconds: float = 2,
                      submitted_at: str | None = None, clock: Callable[[], float] = monotonic,
                      pause: Callable[[float], None] = sleep) -> Mapping[str, object]:
    names = tuple(dict.fromkeys(name.strip() for name in indexer_names if name and name.strip()))
    if not names or timeout_seconds <= 0 or interval_seconds < 0:
        raise ValueError("indexer names, positive timeout, and non-negative interval are required")
    boundary = datetime.fromisoformat(submitted_at) if submitted_at else None
    deadline = clock() + timeout_seconds
    while True:
        statuses, fresh = {}, True
        for name in names:
            raw = client.get_indexer_status(name).last_result
            status = indexer_status(client, name)
            started = getattr(raw, "start_time", None) if raw else None
            status["start_time"] = started.isoformat() if started else None
            statuses[name] = status
            fresh = fresh and (boundary is None or (started is not None and started >= boundary))
        if fresh and any(item["error"] for item in statuses.values()):
            return {"status": "failed", "indexers": statuses}
        if fresh and all(item["status"] == "success" for item in statuses.values()):
            return {"status": "success", "indexers": statuses}
        if clock() >= deadline:
            return {"status": "timeout", "indexers": statuses}
        pause(interval_seconds)
