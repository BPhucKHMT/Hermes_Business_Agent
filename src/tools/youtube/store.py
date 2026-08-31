from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4

from tools.youtube.contracts import (
    ChannelInfo,
    VideoDraft,
    VideoDraftStatus,
    VideoPrivacyStatus,
)


class YouTubeStore:
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
                CREATE TABLE IF NOT EXISTS youtube_connections (
                    connection_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL UNIQUE,
                    channel_id TEXT NOT NULL,
                    channel_title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS video_drafts (
                    draft_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    principal_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    privacy_status TEXT NOT NULL,
                    video_file_path TEXT NOT NULL,
                    thumbnail_file_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    uploaded_video_id TEXT,
                    video_url TEXT
                );

                CREATE TABLE IF NOT EXISTS youtube_audit (
                    audit_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )

    def upsert_connection(self, principal_id: str, channel_id: str, channel_title: str) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conn_id = f"yt-conn-{uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO youtube_connections (
                    connection_id, principal_id, channel_id, channel_title, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(principal_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    channel_title = excluded.channel_title,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (conn_id, principal_id, channel_id, channel_title, "connected", now, now),
            )

    def get_connection(self, principal_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM youtube_connections WHERE principal_id = ?;", (principal_id,)
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def create_or_get_draft(self, draft: VideoDraft) -> VideoDraft:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        status_str = draft.status.value if hasattr(draft.status, "value") else str(draft.status)
        priv_str = draft.privacy_status.value if hasattr(draft.privacy_status, "value") else str(draft.privacy_status)
        tags_json = json.dumps(list(draft.tags), ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO video_drafts (
                    draft_id, idempotency_key, principal_id, channel_id, title, description,
                    tags_json, privacy_status, video_file_path, thumbnail_file_path, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    draft.draft_id,
                    draft.idempotency_key,
                    draft.principal_id,
                    draft.channel_id,
                    draft.title,
                    draft.description,
                    tags_json,
                    priv_str,
                    draft.video_file_path,
                    draft.thumbnail_file_path,
                    status_str,
                    draft.created_at or now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM video_drafts WHERE idempotency_key = ?;", (draft.idempotency_key,)
            ).fetchone()
            if not row:
                raise RuntimeError("failed_to_persist_video_draft")
            return self._row_to_draft(row)

    def get_draft(self, draft_id: str) -> Optional[VideoDraft]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM video_drafts WHERE draft_id = ?;", (draft_id,)).fetchone()
            if not row:
                return None
            return self._row_to_draft(row)

    def transition_draft_status(
        self,
        draft_id: str,
        from_status: VideoDraftStatus,
        to_status: VideoDraftStatus,
        uploaded_video_id: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> VideoDraft:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE video_drafts
                SET status = ?, updated_at = ?, uploaded_video_id = COALESCE(?, uploaded_video_id),
                    video_url = COALESCE(?, video_url)
                WHERE draft_id = ? AND status = ?;
                """,
                (
                    to_status.value,
                    now,
                    uploaded_video_id,
                    video_url,
                    draft_id,
                    from_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"invalid_video_draft_transition_from_{from_status.value}_to_{to_status.value}")
        res = self.get_draft(draft_id)
        if res is None:
            raise RuntimeError("draft_missing_after_update")
        return res

    def record_audit(self, principal_id: str, action: str, target_id: str, details: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        audit_id = f"aud-yt-{uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO youtube_audit (audit_id, timestamp, principal_id, action, target_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (audit_id, now, principal_id, action, target_id, json.dumps(details, ensure_ascii=False)),
            )

    def _row_to_draft(self, row: sqlite3.Row) -> VideoDraft:
        tags = tuple(json.loads(row["tags_json"]))
        return VideoDraft(
            draft_id=row["draft_id"],
            idempotency_key=row["idempotency_key"],
            principal_id=row["principal_id"],
            channel_id=row["channel_id"],
            title=row["title"],
            description=row["description"],
            tags=tags,
            privacy_status=VideoPrivacyStatus(row["privacy_status"]),
            video_file_path=row["video_file_path"],
            thumbnail_file_path=row["thumbnail_file_path"],
            created_at=row["created_at"],
            status=VideoDraftStatus(row["status"]),
            uploaded_video_id=row["uploaded_video_id"],
            video_url=row["video_url"],
        )
