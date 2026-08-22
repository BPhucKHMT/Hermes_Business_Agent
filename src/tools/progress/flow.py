"""Small explicit Flow A resolver."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .contracts import MutationProposal, SourceEvent, TaskRecord

REQUIRED_FIELDS = (
    ("summary", "change"),
    ("task_summary", "task"),
    ("due_at", "due_at"),
    ("draft", "draft"),
)


@dataclass(frozen=True)
class ResolutionContext:
    workspace: str
    suppliers: dict[str, str]
    report_target_id: str
    default_owner: str


@dataclass(frozen=True)
class FlowAResult:
    observation: dict | None
    task: TaskRecord | None
    proposal: MutationProposal | None
    draft: str | None
    draft_sent: bool
    missing_field: str | None


def build_flow_a(
    source: SourceEvent,
    extracted: dict,
    context: ResolutionContext,
) -> FlowAResult:
    if source.workspace != context.workspace:
        return FlowAResult(None, None, None, None, False, "workspace")

    key = extracted.get("supplier_key")
    if not key or key not in context.suppliers:
        return FlowAResult(None, None, None, None, False, "entity")

    for field, reason in REQUIRED_FIELDS:
        if not extracted.get(field):
            return FlowAResult(None, None, None, None, False, reason)

    seed = sha256((source.source_id + key).encode()).hexdigest()[:20]
    task = TaskRecord(
        f"task-{seed}",
        source.workspace,
        extracted["task_summary"],
        context.default_owner,
        extracted["due_at"],
    )
    proposal = MutationProposal(
        f"proposal-{seed}",
        source.workspace,
        context.report_target_id,
        extracted["summary"],
    )
    observation = {"type": "progress", "summary": extracted["summary"]}
    return FlowAResult(
        observation,
        task,
        proposal,
        extracted["draft"],
        False,
        None,
    )
