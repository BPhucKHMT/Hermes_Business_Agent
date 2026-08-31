from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from tools.social_browser.contracts import (
    MediaItem,
    RunStatus,
    SocialActionManifest,
)


_ALLOWED_TRANSITIONS = {
    RunStatus.REQUESTED: {
        RunStatus.PREPARING,
        RunStatus.CANCELLED,
        RunStatus.EXPIRED,
    },
    RunStatus.PREPARING: {
        RunStatus.READY_FOR_HUMAN,
        RunStatus.BLOCKED_LOGIN,
        RunStatus.BLOCKED_ACCOUNT_MISMATCH,
        RunStatus.BLOCKED_CHALLENGE,
        RunStatus.FAILED_UI_DRIFT,
        RunStatus.CANCELLED,
    },
    RunStatus.READY_FOR_HUMAN: {
        RunStatus.PUBLISHED,
        RunStatus.CANCELLED,
        RunStatus.EXPIRED,
    },
}


@dataclass(frozen=True)
class StoredRun:
    manifest: SocialActionManifest
    status: RunStatus
    updated_at: str
    failure_code: str | None = None
    verified_post_id: str | None = None

    @property
    def run_id(self) -> str:
        return self.manifest.run_id

    @property
    def idempotency_key(self) -> str:
        return self.manifest.idempotency_key


class SocialBrowserStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS action_runs (
                    run_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL,
                    account_label TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    media_json TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    failure_code TEXT,
                    verified_post_id TEXT
                );
                CREATE TABLE IF NOT EXISTS evidence_artifacts (
                    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES action_runs(run_id),
                    evidence_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    path TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    UNIQUE(run_id, evidence_type, sha256)
                );
                """
            )

    def create_or_get(self, manifest: SocialActionManifest) -> StoredRun:
        media_json = json.dumps(
            [item.__dict__ for item in manifest.media],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO action_runs (
                    run_id, idempotency_key, platform, account_label,
                    text_content, media_json, audience, status, created_at,
                    updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.run_id,
                    manifest.idempotency_key,
                    manifest.platform,
                    manifest.account_label,
                    manifest.text,
                    media_json,
                    manifest.audience,
                    manifest.status.value,
                    manifest.created_at,
                    manifest.created_at,
                    manifest.expires_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM action_runs WHERE idempotency_key = ?",
                (manifest.idempotency_key,),
            ).fetchone()
        if row is None:
            raise RuntimeError("action_run_not_persisted")
        return self._from_row(row)

    def get_run(self, run_id: str) -> StoredRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM action_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError("social_run_not_found")
        return self._from_row(row)

    def transition(
        self,
        run_id: str,
        expected: RunStatus,
        target: RunStatus,
        failure_code: str | None = None,
        verified_post_id: str | None = None,
    ) -> StoredRun:
        if target not in _ALLOWED_TRANSITIONS.get(expected, set()):
            raise ValueError("invalid_status_transition")
        if target is RunStatus.PUBLISHED and not verified_post_id:
            raise ValueError("verified_post_id_required")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE action_runs
                SET status = ?, updated_at = ?, failure_code = ?,
                    verified_post_id = ?
                WHERE run_id = ? AND status = ?
                """,
                (
                    target.value,
                    now,
                    failure_code,
                    verified_post_id,
                    run_id,
                    expected.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("unexpected_run_status")
        return self.get_run(run_id)

    def add_evidence(
        self,
        run_id: str,
        evidence_type: str,
        sha256: str,
        path: Path,
        observed_at: str,
    ) -> None:
        evidence_path = Path(path).resolve()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence_artifacts (
                    run_id, evidence_type, sha256, path, observed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    evidence_type,
                    sha256,
                    str(evidence_path),
                    observed_at,
                ),
            )

    def _from_row(self, row: sqlite3.Row) -> StoredRun:
        media = tuple(MediaItem(**item) for item in json.loads(row["media_json"]))
        status = RunStatus(row["status"])
        manifest = SocialActionManifest(
            run_id=row["run_id"],
            idempotency_key=row["idempotency_key"],
            platform=row["platform"],
            account_label=row["account_label"],
            text=row["text_content"],
            media=media,
            audience=row["audience"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            status=status,
        )
        return StoredRun(
            manifest=manifest,
            status=status,
            updated_at=row["updated_at"],
            failure_code=row["failure_code"],
            verified_post_id=row["verified_post_id"],
        )
