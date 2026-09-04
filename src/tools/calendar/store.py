from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, List, Optional
from uuid import uuid4

from tools.calendar.contracts import (
    CalendarConnection,
    CalendarConnectionStatus,
    EventDraft,
    EventDraftStatus,
)


class CalendarStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS calendar_connections (
                    connection_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    calendar_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS event_drafts (
                    draft_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    principal_id TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    description TEXT NOT NULL,
                    location TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    attendees_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    committed_event_id TEXT,
                    account_email TEXT
                );
                CREATE TABLE IF NOT EXISTS calendar_audit (
                    audit_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )
            try:
                conn.execute("ALTER TABLE event_drafts ADD COLUMN account_email TEXT;")
            except sqlite3.OperationalError:
                pass

    def upsert_connection(self, conn_record: CalendarConnection) -> CalendarConnection:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        created_at = conn_record.created_at or now
        status_str = conn_record.status.value if hasattr(conn_record.status, "value") else str(conn_record.status)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO calendar_connections (
                    connection_id, principal_id, email, calendar_id, calendar_name, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(principal_id) DO UPDATE SET
                    email = excluded.email,
                    calendar_id = excluded.calendar_id,
                    calendar_name = excluded.calendar_name,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    conn_record.connection_id,
                    conn_record.principal_id,
                    conn_record.email,
                    conn_record.calendar_id,
                    conn_record.calendar_name,
                    status_str,
                    created_at,
                    now,
                ),
            )
        return self.get_connection_by_principal(conn_record.principal_id)  # type: ignore

    def get_connection_by_principal(self, principal_id: str) -> Optional[CalendarConnection]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM calendar_connections WHERE principal_id = ?;", (principal_id,)
            ).fetchone()
            if not row:
                return None
            return CalendarConnection(
                connection_id=row["connection_id"],
                principal_id=row["principal_id"],
                email=row["email"],
                calendar_id=row["calendar_id"],
                calendar_name=row["calendar_name"],
                status=CalendarConnectionStatus(row["status"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def create_or_get_draft(self, draft: EventDraft) -> EventDraft:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        status_str = draft.status.value if hasattr(draft.status, "value") else str(draft.status)
        attendees_json = json.dumps(list(draft.attendees), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO event_drafts (
                    draft_id, idempotency_key, principal_id, calendar_id, summary, description,
                    location, start_time, end_time, attendees_json, status, created_at, updated_at, account_email
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    draft.draft_id,
                    draft.idempotency_key,
                    draft.principal_id,
                    draft.calendar_id,
                    draft.summary,
                    draft.description,
                    draft.location,
                    draft.start_time,
                    draft.end_time,
                    attendees_json,
                    status_str,
                    draft.created_at or now,
                    now,
                    draft.account_email,
                ),
            )
            row = conn.execute(
                "SELECT * FROM event_drafts WHERE idempotency_key = ?;", (draft.idempotency_key,)
            ).fetchone()
            if not row:
                raise RuntimeError("failed_to_persist_draft")
            return self._row_to_draft(row)

    def get_draft(self, draft_id: str) -> Optional[EventDraft]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM event_drafts WHERE draft_id = ?;", (draft_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_draft(row)

    def transition_draft_status(
        self,
        draft_id: str,
        from_status: EventDraftStatus,
        to_status: EventDraftStatus,
        committed_event_id: Optional[str] = None,
    ) -> EventDraft:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE event_drafts
                SET status = ?, updated_at = ?, committed_event_id = COALESCE(?, committed_event_id)
                WHERE draft_id = ? AND status = ?;
                """,
                (
                    to_status.value,
                    now,
                    committed_event_id,
                    draft_id,
                    from_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"invalid_draft_transition_from_{from_status.value}_to_{to_status.value}")
        res = self.get_draft(draft_id)
        if res is None:
            raise RuntimeError("draft_missing_after_update")
        return res

    def record_audit(self, principal_id: str, action: str, target_id: str, details: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        audit_id = f"aud-{uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO calendar_audit (audit_id, timestamp, principal_id, action, target_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (audit_id, now, principal_id, action, target_id, json.dumps(details, ensure_ascii=False)),
            )

    def _row_to_draft(self, row: sqlite3.Row) -> EventDraft:
        attendees = tuple(json.loads(row["attendees_json"]))
        keys = row.keys() if hasattr(row, "keys") else []
        account_email = row["account_email"] if "account_email" in keys else None
        return EventDraft(
            draft_id=row["draft_id"],
            idempotency_key=row["idempotency_key"],
            principal_id=row["principal_id"],
            calendar_id=row["calendar_id"],
            summary=row["summary"],
            description=row["description"],
            location=row["location"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            attendees=attendees,
            created_at=row["created_at"],
            status=EventDraftStatus(row["status"]),
            committed_event_id=row["committed_event_id"],
            account_email=account_email,
        )
