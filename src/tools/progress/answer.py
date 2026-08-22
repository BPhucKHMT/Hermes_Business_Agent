"""Compose current progress truth with optional matching KB citation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CurrentAnswer:
    text: str
    sync_status: str
    citation: str | None


def compose_current_answer(
    current_text: str,
    revision: str,
    evidence: Iterable[dict[str, Any]],
    display_name: str,
) -> CurrentAnswer:
    matching = next(
        (
            row
            for row in evidence
            if revision in str(row.get("content", ""))
            or row.get("document_version") == revision
        ),
        None,
    )
    if matching:
        source = matching.get("source_path")
        return CurrentAnswer(current_text, "verified", f"{display_name} — {source}")

    return CurrentAnswer(f"{current_text} Knowledge sync pending.", "pending", None)
