"""Durable Google write-action lifecycle store with idempotency.

One logical user request maps to one operation ID. Duplicate delivery of the
same request key never repeats a write; a distinct intentional request gets a
distinct operation. State machine:

    pending -> executing -> {verified, failed, unknown}

``unknown`` marks a commit whose provider outcome is unproven (e.g. timeout
after the request left the process). Callers must reconcile read-only before
considering any retry; the store never re-executes by itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

_PENDING = "pending"
_EXECUTING = "executing"
_VERIFIED = "verified"
_FAILED = "failed"
_UNKNOWN = "unknown"

_TERMINAL = frozenset({_VERIFIED, _FAILED, _UNKNOWN})


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".runtime" / "google" / "actions.db"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ActionStore:
    """SQLite-backed record of Google write operations per caller."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS google_actions (
                    operation_id TEXT PRIMARY KEY,
                    request_key TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    workspace TEXT NOT NULL DEFAULT '',
                    service TEXT NOT NULL,
                    action TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    evidence_json TEXT,
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(request_key)
                );
                """
            )

    def begin(
        self,
        *,
        request_key: str,
        principal_id: str,
        service: str,
        action: str,
        params: dict[str, Any],
        workspace: str = "",
    ) -> dict[str, Any] | None:
        """Register a write attempt for a request key.

        Returns the existing record when this request key was already seen
        (duplicate delivery / restart replay), so the caller must not re-execute.
        Returns the fresh record when this is a genuinely new request.
        """
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO google_actions (
                    operation_id, request_key, principal_id, workspace,
                    service, action, params_json, state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_key) DO NOTHING
                """,
                (
                    str(uuid4()),
                    request_key,
                    principal_id,
                    workspace,
                    service,
                    action,
                    json.dumps(params, ensure_ascii=False, sort_keys=True),
                    _PENDING,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM google_actions WHERE request_key = ?",
                (request_key,),
            ).fetchone()
        return dict(row) if row else None

    def mark_executing(self, operation_id: str) -> None:
        self._transition(operation_id, _EXECUTING)

    def mark_verified(self, operation_id: str, evidence: dict[str, Any]) -> None:
        self._finish(operation_id, _VERIFIED, evidence=evidence)

    def mark_failed(self, operation_id: str, error_code: str) -> None:
        self._finish(operation_id, _FAILED, error_code=error_code)

    def mark_unknown(self, operation_id: str, detail: str) -> None:
        self._finish(operation_id, _UNKNOWN, error_code=detail)

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM google_actions WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_by_request_key(self, request_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM google_actions WHERE request_key = ?",
                (request_key,),
            ).fetchone()
        return dict(row) if row else None

    def _transition(self, operation_id: str, state: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE google_actions SET state = ?, updated_at = ? WHERE operation_id = ?",
                (state, _now(), operation_id),
            )

    def _finish(
        self,
        operation_id: str,
        state: str,
        *,
        evidence: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE google_actions
                SET state = ?, evidence_json = ?, error_code = ?, updated_at = ?
                WHERE operation_id = ?
                """,
                (
                    state,
                    json.dumps(evidence, ensure_ascii=False) if evidence else None,
                    error_code,
                    _now(),
                    operation_id,
                ),
            )
