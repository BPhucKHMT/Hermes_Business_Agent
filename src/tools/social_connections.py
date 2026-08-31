from __future__ import annotations

from pathlib import Path
import sqlite3


class SocialConnectionStore:
    """Persist host-owned caller connection state without storing credentials."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def status(self, principal_id: str) -> tuple[str, str | None]:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS social_connections ("
                "principal_id TEXT PRIMARY KEY, connection_status TEXT NOT NULL, "
                "connection_id TEXT)"
            )
            row = connection.execute(
                "SELECT connection_status, connection_id FROM social_connections "
                "WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        return (row[0], row[1]) if row else ("unsupported", None)
