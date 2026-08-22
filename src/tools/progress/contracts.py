"""Validated Flow A contracts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VALID_SOURCE_TYPES = {"telegram", "email", "task"}


@dataclass(frozen=True)
class SourceEvent:
    source_id: str
    workspace: str
    source_type: str
    occurred_at: str
    actor: str
    content_sha256: str
    locator: dict[str, str]

    def __post_init__(self) -> None:
        if not self.source_id or not self.workspace or self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError("invalid source")


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    workspace: str
    summary: str
    owner: str
    due_at: str


@dataclass(frozen=True)
class MutationProposal:
    proposal_id: str
    workspace: str
    target_id: str
    summary: str
    risk_tier: int = 2


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    output_path: Path
