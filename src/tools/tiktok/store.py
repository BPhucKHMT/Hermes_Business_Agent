from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4

from tools.tiktok.contracts import (
    TikTokCreatorInfo,
    TikTokPostDraft,
    TikTokPostDraftStatus,
    TikTokPrivacyLevel,
)


class TikTokStore:
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
                CREATE TABLE IF NOT EXISTS tiktok_connections (
                    connection_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL UNIQUE,
                    open_id TEXT NOT NULL,
                    creator_nickname TEXT NOT NULL,
                    creator_username TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tiktok_post_drafts (
                    draft_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    principal_id TEXT NOT NULL,
                    open_id TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    video_file_path TEXT NOT NULL,
                    privacy_level TEXT NOT NULL,
                    disable_comment INTEGER NOT NULL,
                    disable_duet INTEGER NOT NULL,
                    disable_stitch INTEGER NOT NULL,
                    brand_content_toggle INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    publish_id TEXT,
                    published_post_id TEXT
                );

                CREATE TABLE IF NOT EXISTS tiktok_audit (
                    audit_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )

    def upsert_connection(self, principal_id: str, open_id: str, nickname: str, username: str) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conn_id = f"tt-conn-{uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tiktok_connections (
                    connection_id, principal_id, open_id, creator_nickname, creator_username, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(principal_id) DO UPDATE SET
                    open_id = excluded.open_id,
                    creator_nickname = excluded.creator_nickname,
                    creator_username = excluded.creator_username,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (conn_id, principal_id, open_id, nickname, username, "connected", now, now),
            )

    def get_connection(self, principal_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tiktok_connections WHERE principal_id = ?;", (principal_id,)
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def create_or_get_draft(self, draft: TikTokPostDraft) -> TikTokPostDraft:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        status_str = draft.status.value if hasattr(draft.status, "value") else str(draft.status)
        priv_str = draft.privacy_level.value if hasattr(draft.privacy_level, "value") else str(draft.privacy_level)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tiktok_post_drafts (
                    draft_id, idempotency_key, principal_id, open_id, caption,
                    video_file_path, privacy_level, disable_comment, disable_duet,
                    disable_stitch, brand_content_toggle, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    draft.draft_id,
                    draft.idempotency_key,
                    draft.principal_id,
                    draft.open_id,
                    draft.caption,
                    draft.video_file_path,
                    priv_str,
                    1 if draft.disable_comment else 0,
                    1 if draft.disable_duet else 0,
                    1 if draft.disable_stitch else 0,
                    1 if draft.brand_content_toggle else 0,
                    status_str,
                    draft.created_at or now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM tiktok_post_drafts WHERE idempotency_key = ?;", (draft.idempotency_key,)
            ).fetchone()
            if not row:
                raise RuntimeError("failed_to_persist_tiktok_draft")
            return self._row_to_draft(row)

    def get_draft(self, draft_id: str) -> Optional[TikTokPostDraft]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tiktok_post_drafts WHERE draft_id = ?;", (draft_id,)).fetchone()
            if not row:
                return None
            return self._row_to_draft(row)

    def transition_draft_status(
        self,
        draft_id: str,
        from_status: TikTokPostDraftStatus,
        to_status: TikTokPostDraftStatus,
        publish_id: Optional[str] = None,
        published_post_id: Optional[str] = None,
    ) -> TikTokPostDraft:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE tiktok_post_drafts
                SET status = ?, updated_at = ?, publish_id = COALESCE(?, publish_id),
                    published_post_id = COALESCE(?, published_post_id)
                WHERE draft_id = ? AND status = ?;
                """,
                (
                    to_status.value,
                    now,
                    publish_id,
                    published_post_id,
                    draft_id,
                    from_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"invalid_tiktok_draft_transition_from_{from_status.value}_to_{to_status.value}")
        res = self.get_draft(draft_id)
        if res is None:
            raise RuntimeError("draft_missing_after_update")
        return res

    def record_audit(self, principal_id: str, action: str, target_id: str, details: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        audit_id = f"aud-tt-{uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tiktok_audit (audit_id, timestamp, principal_id, action, target_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (audit_id, now, principal_id, action, target_id, json.dumps(details, ensure_ascii=False)),
            )

    def _row_to_draft(self, row: sqlite3.Row) -> TikTokPostDraft:
        return TikTokPostDraft(
            draft_id=row["draft_id"],
            idempotency_key=row["idempotency_key"],
            principal_id=row["principal_id"],
            open_id=row["open_id"],
            caption=row["caption"],
            video_file_path=row["video_file_path"],
            privacy_level=TikTokPrivacyLevel(row["privacy_level"]),
            disable_comment=bool(row["disable_comment"]),
            disable_duet=bool(row["disable_duet"]),
            disable_stitch=bool(row["disable_stitch"]),
            brand_content_toggle=bool(row["brand_content_toggle"]),
            created_at=row["created_at"],
            status=TikTokPostDraftStatus(row["status"]),
            publish_id=row["publish_id"],
            published_post_id=row["published_post_id"],
        )
