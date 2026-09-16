"""Single-use, user/workspace-bound group-to-DM handoff tokens (H018 S4).

A group message that needs private Google tools creates an opaque, expiring,
single-use token. Only the initiating platform user, in DM, on the original
workspace can redeem it. Tokens carry no request content beyond the stored
payload; the URL never contains OAuth material.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 15 * 60
_MAX_ACTIVE_TOKENS_PER_USER = 5

_PURPOSE = "google-handoff-v1"


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".runtime" / "google" / "handoffs.db"


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    """Store only an HMAC of the token, never the raw value."""
    secret = os.environ.get("HERMES_HANDOFF_SECRET", "hermes-handoff-local")
    return hmac.new(
        secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class HandoffStore:
    """SQLite-backed store of pending group-to-DM continuations."""

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
                CREATE TABLE IF NOT EXISTS google_handoffs (
                    token_hash TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    chat_type TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    thread_id TEXT,
                    request_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    redeemed_at TEXT,
                    redeemed_by TEXT
                );
                """
            )

    def issue(
        self,
        *,
        platform: str,
        user_id: str,
        workspace: str,
        chat_type: str,
        chat_id: str,
        thread_id: str | None,
        request_text: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Create a handoff token for one group request. Returns the raw token."""
        now = _now()
        # Bound per-user pending tokens; oldest expires first.
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT token_hash FROM google_handoffs
                WHERE platform = ? AND user_id = ? AND redeemed_at IS NULL
                ORDER BY created_at ASC
                """,
                (platform, user_id),
            ).fetchall()
            if len(rows) >= _MAX_ACTIVE_TOKENS_PER_USER:
                stale = rows[0]["token_hash"]
                conn.execute(
                    "DELETE FROM google_handoffs WHERE token_hash = ?",
                    (stale,),
                )
        token = uuid4().hex + uuid4().hex
        token_hash = _hash_token(token)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO google_handoffs (
                    token_hash, platform, user_id, workspace, chat_type,
                    chat_id, thread_id, request_text, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_hash,
                    platform,
                    user_id,
                    workspace,
                    chat_type,
                    chat_id,
                    thread_id,
                    request_text,
                    now.isoformat(),
                    (now + timedelta(seconds=ttl_seconds)).isoformat(),
                ),
            )
        return token

    def redeem(
        self,
        token: str,
        *,
        platform: str,
        user_id: str,
        workspace: str,
    ) -> dict[str, Any] | None:
        """Atomically redeem a token; None when invalid/expired/mismatched.

        Verification: same platform user, same workspace, not expired, not
        already redeemed. Successful redemption is recorded before returning.
        """
        token_hash = _hash_token(str(token))
        now_iso = _now().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM google_handoffs WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if row["redeemed_at"] is not None:
                return None
            if row["expires_at"] <= now_iso:
                return None
            if row["platform"] != platform or row["user_id"] != str(user_id):
                return None
            if workspace and row["workspace"] != workspace:
                return None
            conn.execute(
                """
                UPDATE google_handoffs
                SET redeemed_at = ?, redeemed_by = ?
                WHERE token_hash = ? AND redeemed_at IS NULL
                """,
                (now_iso, f"{platform}:{user_id}", token_hash),
            )
            if conn.total_changes == 0:
                return None
            row = conn.execute(
                "SELECT * FROM google_handoffs WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        return dict(row) if row else None

    def purge_expired(self) -> int:
        """Delete expired or redeemed tokens. Returns rows removed."""
        cutoff = _now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM google_handoffs WHERE expires_at <= ? OR redeemed_at IS NOT NULL",
                (cutoff,),
            )
            return cursor.rowcount


def build_deep_link(username: str, token: str) -> str:
    """Build the Telegram deep link carrying only the opaque token."""
    safe_username = str(username).lstrip("@").strip()
    return f"https://t.me/{safe_username}?start={token}"


def handoff_notice(request_summary: str, deep_link: str) -> str:
    """Group-facing reply: neutral, no account/data disclosure."""
    return (
        "🔒 This request needs access to your private Google data. "
        "Tap the button/link below to continue in a private chat — "
        "your request is preserved; no need to type it again.\n"
        f"{deep_link}\n"
        f"Recorded request: {request_summary[:120]}"
    )
