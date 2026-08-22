"""Exact approval and restart-safe execution."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .contracts import ExecutionResult, MutationProposal
from .documents import ReportTarget, apply_markdown, preview_markdown
from .store import open_store, request_knowledge_sync


def record_approval(
    connection: sqlite3.Connection,
    proposal_id: str,
    approval_id: str,
    actor: str,
    expires_at: datetime,
) -> None:
    row = connection.execute("SELECT workspace FROM events WHERE id=?", (proposal_id,)).fetchone()
    if not row:
        raise ValueError("unknown proposal")
    with connection:
        connection.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,?,?)",
            (approval_id, row["workspace"], proposal_id, actor, expires_at.isoformat(), "approved"),
        )


def approve_and_execute(
    db_path: Path,
    target: ReportTarget,
    proposal_id: str,
    approval_id: str,
    actor: str,
    output_dir: Path,
) -> ExecutionResult:
    connection = open_store(db_path)
    try:
        prior = connection.execute(
            "SELECT payload FROM evidence WHERE id=?",
            (f"output:{proposal_id}",),
        ).fetchone()
        if prior:
            payload = json.loads(prior["payload"])
            return ExecutionResult("verified", Path(payload["path"]))

        query = (
            "SELECT a.*, e.payload FROM approvals a "
            "JOIN events e ON e.id = a.proposal_id "
            "WHERE a.id = ? AND a.proposal_id = ?"
        )
        row = connection.execute(query, (approval_id, proposal_id)).fetchone()

        if (
            not row
            or row["actor"] != actor
            or row["status"] != "approved"
            or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc)
        ):
            raise PermissionError("exact live approval required")

        payload = json.loads(row["payload"])
        proposal = MutationProposal(
            payload["proposal_id"],
            payload["workspace"],
            payload["target_id"],
            payload["summary"],
            payload["risk_tier"],
        )
        preview = preview_markdown(target, proposal)
        path = apply_markdown(target, preview, output_dir, proposal_id)

        if proposal.summary not in path.read_text(encoding="utf-8"):
            raise RuntimeError("read-back failed")

        evidence_payload = {
            "path": str(path.resolve()),
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        evidence_json = json.dumps(evidence_payload, sort_keys=True)

        with connection:
            connection.execute(
                "INSERT INTO evidence VALUES(?,?,?,?)",
                (f"output:{proposal_id}", proposal.workspace, "report_output", evidence_json),
            )
            request_knowledge_sync(
                connection,
                proposal_id,
                proposal.workspace,
                f"output:{proposal_id}",
                f"workspaces/{proposal.workspace}/progress/{target.target_id}.md",
                evidence_payload["sha256"],
            )

        return ExecutionResult("verified", path)
    finally:
        connection.close()
