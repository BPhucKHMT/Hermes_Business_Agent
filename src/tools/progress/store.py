"""SQLite state using customer-owned nine-table model."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Any

from .contracts import SourceEvent

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    proposal_id TEXT UNIQUE NOT NULL,
    actor TEXT,
    expires_at TEXT,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    workspace TEXT NOT NULL,
    event TEXT NOT NULL
);
"""


def open_store(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def append_source(connection: sqlite3.Connection, source: SourceEvent) -> tuple[str, bool]:
    row = connection.execute("SELECT id FROM events WHERE id = ?", (source.source_id,)).fetchone()
    if row:
        return row["id"], False

    payload = json.dumps(asdict(source), sort_keys=True)
    connection.execute(
        "INSERT INTO events VALUES(?,?,?)",
        (source.source_id, source.workspace, payload),
    )
    connection.commit()
    return source.source_id, True


def save_flow_result(connection: sqlite3.Connection, result: Any) -> None:
    with connection:
        if result.task:
            task_payload = json.dumps(asdict(result.task), sort_keys=True)
            connection.execute(
                "INSERT OR IGNORE INTO tasks VALUES(?,?,?)",
                (result.task.task_id, result.task.workspace, task_payload),
            )
        if result.proposal:
            proposal_data = {"kind": "proposal", **asdict(result.proposal)}
            proposal_payload = json.dumps(proposal_data, sort_keys=True)
            connection.execute(
                "INSERT OR IGNORE INTO events VALUES(?,?,?)",
                (result.proposal.proposal_id, result.proposal.workspace, proposal_payload),
            )


def request_knowledge_sync(
    connection: sqlite3.Connection,
    proposal_id: str,
    workspace: str,
    evidence_id: str,
    source_path: str,
    revision: str,
) -> tuple[int, bool]:
    idempotency_key = f"knowledge-sync:{proposal_id}:{revision}"
    rows = connection.execute(
        "SELECT id, event FROM audit_log WHERE workspace = ?",
        (workspace,),
    ).fetchall()

    for row in rows:
        try:
            event_data = json.loads(row["event"])
            if event_data.get("idempotency_key") == idempotency_key:
                return row["id"], False
        except (ValueError, TypeError):
            continue

    payload = json.dumps(
        {
            "idempotency_key": idempotency_key,
            "status": "requested",
            "proposal_id": proposal_id,
            "evidence_id": evidence_id,
            "source_path": source_path,
            "revision": revision,
        },
        sort_keys=True,
    )
    cursor = connection.execute(
        "INSERT INTO audit_log(workspace, event) VALUES(?,?)",
        (workspace, payload),
    )
    return cursor.lastrowid, True


def pending_knowledge_sync(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    pending = []
    for row in connection.execute("SELECT * FROM audit_log ORDER BY id"):
        try:
            status = json.loads(row["event"]).get("status")
            if status in {"requested", "failed"}:
                pending.append(dict(row))
        except (ValueError, TypeError):
            continue
    return pending
