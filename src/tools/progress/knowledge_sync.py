"""Project a verified progress report to Azure and prove indexed revision."""
from __future__ import annotations

from dataclasses import dataclass
import json
from time import monotonic, sleep
from typing import Any, Callable


@dataclass(frozen=True)
class KnowledgeSyncResult:
    status: str
    source_path: str
    revision: str


def _escape(value: str) -> str:
    return value.replace("'", "''")


def sync_verified_report(
    *,
    content: bytes | str,
    workspace: str,
    source_path: str,
    revision: str,
    text_container: Any,
    indexers: Any,
    text_indexer: str,
    wait: Callable[..., dict[str, Any]],
    search: Callable[..., Any],
    timeout_seconds: float = 60,
    interval_seconds: float = 2,
    clock: Callable[[], float] = monotonic,
    pause: Callable[[float], None] = sleep,
) -> KnowledgeSyncResult:
    if (
        not content
        or not workspace
        or not source_path.startswith(f"workspaces/{workspace}/progress/")
        or not revision
    ):
        raise ValueError("verified scoped report required")

    metadata = {
        "workspace": workspace,
        "source_path": source_path,
        "document_version": revision,
        "access_groups": json.dumps(["internal"], separators=(",", ":")),
    }
    text_container.upload_blob(source_path, content, overwrite=True, metadata=metadata)
    indexers.run_indexer(text_indexer)

    waited = wait(indexers, [text_indexer])
    if waited.get("status") != "success":
        return KnowledgeSyncResult("pending", source_path, revision)

    deadline = clock() + timeout_seconds
    filter_expr = (
        f"source_path eq '{_escape(source_path)}' "
        f"and search.ismatch('{_escape(workspace)}', 'source_path')"
    )

    while True:
        rows = list(
            search(
                search_text=revision,
                filter=filter_expr,
                select=["content", "source_path", "document_version"],
                top=8,
            )
        )
        if any(
            revision in str(row.get("content", "")) or row.get("document_version") == revision
            for row in rows
        ):
            return KnowledgeSyncResult("verified", source_path, revision)

        if clock() >= deadline:
            return KnowledgeSyncResult("pending", source_path, revision)

        pause(interval_seconds)
