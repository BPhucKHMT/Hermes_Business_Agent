from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.email.contracts import (
    AuditEvent,
    MAX_CONNECTIONS_PER_PRINCIPAL,
    ConnectionStatus,
    Destination,
    GrantRequestStatus,
    MailConnection,
    MailboxType,
    OAuthLinkRequest,
    SharedGrant,
    SharedGrantRequest,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(expires_at: str) -> bool:
    parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)


class MailStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mail_connections (
                    connection_id TEXT PRIMARY KEY,
                    owner_principal_id TEXT NOT NULL,
                    mailbox_type TEXT NOT NULL CHECK (mailbox_type IN ('personal', 'shared')),
                    masked_address TEXT NOT NULL,
                    provider_subject_hash TEXT NOT NULL,
                    secret_ref TEXT NOT NULL UNIQUE,
                    granted_scopes_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('connected', 'reconnect_required', 'revoked')
                    ),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS oauth_link_requests (
                    request_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    nonce_hash TEXT NOT NULL,
                    pkce_secret_ref TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                );

                CREATE TABLE IF NOT EXISTS shared_grant_requests (
                    request_id TEXT PRIMARY KEY,
                    connection_id TEXT NOT NULL REFERENCES mail_connections(connection_id),
                    requested_by TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    thread_id TEXT,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'approved', 'denied', 'expired')
                    ),
                    expires_at TEXT NOT NULL,
                    decided_by TEXT,
                    decided_at TEXT
                );

                CREATE TABLE IF NOT EXISTS shared_grants (
                    request_id TEXT PRIMARY KEY REFERENCES shared_grant_requests(request_id),
                    connection_id TEXT NOT NULL REFERENCES mail_connections(connection_id),
                    platform TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    thread_id TEXT,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS email_audit (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    connection_id TEXT,
                    destination_hash TEXT,
                    query_hash TEXT,
                    occurred_at TEXT NOT NULL,
                    outcome TEXT NOT NULL
                );
                """
            )

    def add_connection(self, conn_record: MailConnection) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            # 1. If an active connection for the exact same mailbox exists, revoke it to replace cleanly
            existing = conn.execute(
                """
                SELECT connection_id FROM mail_connections
                WHERE owner_principal_id = ? AND provider_subject_hash = ? AND status != 'revoked';
                """,
                (conn_record.owner_principal_id, conn_record.provider_subject_hash),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE mail_connections
                    SET status = 'revoked', revoked_at = ?
                    WHERE connection_id = ?;
                    """,
                    (_utc_now_iso(), existing["connection_id"]),
                )

            # 2. Check remaining active count
            cur = conn.execute(
                """
                SELECT COUNT(*) AS active_count FROM mail_connections
                WHERE owner_principal_id = ? AND status != 'revoked';
                """,
                (conn_record.owner_principal_id,),
            )
            count = cur.fetchone()["active_count"]
            if count >= MAX_CONNECTIONS_PER_PRINCIPAL:
                raise ValueError(
                    "connection_limit_exceeded: maximum 3 active connections allowed"
                )

            conn.execute(
                """
                INSERT INTO mail_connections (
                    connection_id, owner_principal_id, mailbox_type, masked_address,
                    provider_subject_hash, secret_ref, granted_scopes_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    conn_record.connection_id,
                    conn_record.owner_principal_id,
                    (
                        conn_record.mailbox_type.value
                        if hasattr(conn_record.mailbox_type, "value")
                        else str(conn_record.mailbox_type)
                    ),
                    conn_record.masked_address,
                    conn_record.provider_subject_hash,
                    conn_record.secret_ref,
                    json.dumps(list(conn_record.granted_scopes)),
                    (
                        conn_record.status.value
                        if hasattr(conn_record.status, "value")
                        else str(conn_record.status)
                    ),
                    _utc_now_iso(),
                ),
            )

    def list_connections(self, principal_id: str) -> tuple[MailConnection, ...]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM mail_connections
                WHERE owner_principal_id = ? AND status != 'revoked'
                ORDER BY created_at ASC;
                """,
                (principal_id,),
            )
            rows = cur.fetchall()
            return tuple(
                MailConnection(
                    connection_id=r["connection_id"],
                    owner_principal_id=r["owner_principal_id"],
                    mailbox_type=MailboxType(r["mailbox_type"]),
                    masked_address=r["masked_address"],
                    provider_subject_hash=r["provider_subject_hash"],
                    secret_ref=r["secret_ref"],
                    granted_scopes=tuple(json.loads(r["granted_scopes_json"])),
                    status=ConnectionStatus(r["status"]),
                )
                for r in rows
            )

    def get_authorized_connection(
        self, principal_id: str, connection_id: str
    ) -> MailConnection:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM mail_connections
                WHERE connection_id = ? AND status != 'revoked';
                """,
                (connection_id,),
            )
            r = cur.fetchone()
            if not r:
                raise FileNotFoundError(f"connection not found: {connection_id}")
            if (
                r["owner_principal_id"] != principal_id
                and r["mailbox_type"] != "shared"
            ):
                raise PermissionError(
                    f"principal not authorized for connection {connection_id}"
                )
            return MailConnection(
                connection_id=r["connection_id"],
                owner_principal_id=r["owner_principal_id"],
                mailbox_type=MailboxType(r["mailbox_type"]),
                masked_address=r["masked_address"],
                provider_subject_hash=r["provider_subject_hash"],
                secret_ref=r["secret_ref"],
                granted_scopes=tuple(json.loads(r["granted_scopes_json"])),
                status=ConnectionStatus(r["status"]),
            )

    def create_link_request(self, req: OAuthLinkRequest) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oauth_link_requests (
                    request_id, principal_id, nonce_hash, pkce_secret_ref, expires_at
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (
                    req.request_id,
                    req.principal_id,
                    req.nonce_hash,
                    req.pkce_secret_ref,
                    req.expires_at,
                ),
            )

    def get_link_request(self, request_id: str) -> OAuthLinkRequest:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM oauth_link_requests WHERE request_id = ?;",
                (request_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError("oauth_request_not_found")
        return OAuthLinkRequest(
            request_id=row["request_id"],
            principal_id=row["principal_id"],
            nonce_hash=row["nonce_hash"],
            pkce_secret_ref=row["pkce_secret_ref"],
            expires_at=row["expires_at"],
            used_at=row["used_at"],
        )

    def consume_link_request(
        self, request_id: str, nonce_hash: str, principal_id: str
    ) -> OAuthLinkRequest:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                "SELECT * FROM oauth_link_requests WHERE request_id = ?;", (request_id,)
            )
            r = cur.fetchone()
            if not r:
                raise FileNotFoundError("oauth_request_not_found")
            if r["used_at"] is not None:
                raise PermissionError("oauth_request_already_used")
            if r["nonce_hash"] != nonce_hash:
                raise PermissionError("oauth_nonce_mismatch")
            if r["principal_id"] != principal_id:
                raise PermissionError("oauth_principal_mismatch")
            if _is_expired(r["expires_at"]):
                raise PermissionError("oauth_request_expired")

            now = _utc_now_iso()
            conn.execute(
                "UPDATE oauth_link_requests SET used_at = ? WHERE request_id = ?;",
                (now, request_id),
            )
            return OAuthLinkRequest(
                request_id=r["request_id"],
                principal_id=r["principal_id"],
                nonce_hash=r["nonce_hash"],
                pkce_secret_ref=r["pkce_secret_ref"],
                expires_at=r["expires_at"],
                used_at=now,
            )

    def create_grant_request(self, req: SharedGrantRequest) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO shared_grant_requests (
                    request_id, connection_id, requested_by, platform, chat_id, thread_id,
                    status, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    req.request_id,
                    req.connection_id,
                    req.requested_by,
                    req.destination.platform,
                    req.destination.chat_id,
                    req.destination.thread_id,
                    (
                        req.status.value
                        if hasattr(req.status, "value")
                        else str(req.status)
                    ),
                    req.expires_at,
                ),
            )

    def decide_grant_request(
        self,
        request_id: str,
        operator_principal_id: str,
        operator_allowlist: tuple[str, ...],
        approve: bool,
    ) -> SharedGrantRequest:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                "SELECT * FROM shared_grant_requests WHERE request_id = ?;",
                (request_id,),
            )
            r = cur.fetchone()
            if not r:
                raise FileNotFoundError("grant_request_not_found")
            if r["status"] != "pending":
                raise ValueError(f"grant_request_not_pending: {r['status']}")

            if operator_principal_id not in operator_allowlist:
                raise PermissionError(
                    "operator_required: principal is not a configured operator"
                )
            if operator_principal_id == r["requested_by"]:
                raise PermissionError(
                    "operator_required: mailbox owner cannot self-approve shared grant"
                )
            if _is_expired(r["expires_at"]):
                conn.execute(
                    "UPDATE shared_grant_requests SET status = 'expired' WHERE request_id = ?;",
                    (request_id,),
                )
                conn.commit()
                raise ValueError("grant_request_expired")

            now = _utc_now_iso()
            new_status = (
                GrantRequestStatus.APPROVED if approve else GrantRequestStatus.DENIED
            )

            conn.execute(
                """
                UPDATE shared_grant_requests
                SET status = ?, decided_by = ?, decided_at = ?
                WHERE request_id = ?;
                """,
                (new_status.value, operator_principal_id, now, request_id),
            )

            if approve:
                conn.execute(
                    """
                    INSERT INTO shared_grants (
                        request_id, connection_id, platform, chat_id, thread_id
                    )
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        request_id,
                        r["connection_id"],
                        r["platform"],
                        r["chat_id"],
                        r["thread_id"],
                    ),
                )
                conn.execute(
                    "UPDATE mail_connections SET mailbox_type = 'shared' WHERE connection_id = ?;",
                    (r["connection_id"],),
                )

            return SharedGrantRequest(
                request_id=r["request_id"],
                connection_id=r["connection_id"],
                requested_by=r["requested_by"],
                destination=Destination(
                    platform=r["platform"],
                    chat_id=r["chat_id"],
                    thread_id=r["thread_id"],
                ),
                status=new_status,
                expires_at=r["expires_at"],
                decided_by=operator_principal_id,
                decided_at=now,
            )

    def destination_grant(
        self, connection_id: str, destination: Destination
    ) -> Optional[SharedGrant]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM shared_grants
                WHERE connection_id = ? AND platform = ? AND chat_id = ?
                  AND (thread_id IS ? OR thread_id = ?)
                  AND revoked_at IS NULL;
                """,
                (
                    connection_id,
                    destination.platform,
                    destination.chat_id,
                    destination.thread_id,
                    destination.thread_id,
                ),
            )
            r = cur.fetchone()
            if not r:
                return None
            return SharedGrant(
                request_id=r["request_id"],
                connection_id=r["connection_id"],
                destination=Destination(
                    platform=r["platform"],
                    chat_id=r["chat_id"],
                    thread_id=r["thread_id"],
                ),
                revoked_at=r["revoked_at"],
            )

    def revoke_connection(
        self, principal_id: str, connection_id: str
    ) -> MailConnection:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                "SELECT * FROM mail_connections WHERE connection_id = ?;",
                (connection_id,),
            )
            r = cur.fetchone()
            if not r:
                raise FileNotFoundError("connection_not_found")
            if r["owner_principal_id"] != principal_id:
                raise PermissionError("only_owner_can_revoke")

            now = _utc_now_iso()
            conn.execute(
                "UPDATE mail_connections SET status = 'revoked', "
                "revoked_at = ? WHERE connection_id = ?;",
                (now, connection_id),
            )
            conn.execute(
                "UPDATE shared_grants SET revoked_at = ? WHERE connection_id = ?;",
                (now, connection_id),
            )
            return MailConnection(
                connection_id=r["connection_id"],
                owner_principal_id=r["owner_principal_id"],
                mailbox_type=MailboxType(r["mailbox_type"]),
                masked_address=r["masked_address"],
                provider_subject_hash=r["provider_subject_hash"],
                secret_ref=r["secret_ref"],
                granted_scopes=tuple(json.loads(r["granted_scopes_json"])),
                status=ConnectionStatus.REVOKED,
            )

    def append_audit(self, event: AuditEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO email_audit (
                    event_id, event_type, principal_id, connection_id,
                    destination_hash, query_hash, occurred_at, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.principal_id,
                    event.connection_id,
                    event.destination_hash,
                    event.query_hash,
                    event.occurred_at,
                    event.outcome,
                ),
            )

    def list_audit_events(self) -> tuple[AuditEvent, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM email_audit ORDER BY occurred_at, event_id;"
            ).fetchall()
        return tuple(
            AuditEvent(
                event_id=row["event_id"],
                event_type=row["event_type"],
                principal_id=row["principal_id"],
                connection_id=row["connection_id"],
                destination_hash=row["destination_hash"],
                query_hash=row["query_hash"],
                occurred_at=row["occurred_at"],
                outcome=row["outcome"],
            )
            for row in rows
        )

    def update_connection_status(
        self, connection_id: str, status: ConnectionStatus | str
    ) -> None:
        status_val = status.value if hasattr(status, "value") else str(status)
        with self._connect() as conn:
            conn.execute(
                "UPDATE mail_connections SET status = ? WHERE connection_id = ?;",
                (status_val, connection_id),
            )
