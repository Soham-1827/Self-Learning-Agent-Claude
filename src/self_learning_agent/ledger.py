"""Record of what has been processed, so re-runs skip old sources."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed (
    source_type  TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    title        TEXT,
    url          TEXT,
    processed_at TEXT NOT NULL,
    note_path    TEXT,
    status       TEXT NOT NULL DEFAULT 'pending-review',
    PRIMARY KEY (source_type, source_id)
);
"""


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def seen(self, source_type: str, source_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed WHERE source_type=? AND source_id=?",
                (source_type, source_id),
            ).fetchone()
        return row is not None

    def unseen(self, source_type: str, source_ids: list[str]) -> list[str]:
        """Filter to source_ids not yet processed, preserving order."""
        return [sid for sid in source_ids if not self.seen(source_type, sid)]

    def record(
        self,
        source_type: str,
        source_id: str,
        *,
        title: str | None = None,
        url: str | None = None,
        note_path: str | None = None,
        status: str = "pending-review",
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO processed"
                " (source_type, source_id, title, url, processed_at, note_path, status)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(source_type, source_id) DO UPDATE SET"
                "   title=excluded.title, url=excluded.url,"
                "   processed_at=excluded.processed_at,"
                "   note_path=excluded.note_path, status=excluded.status",
                (
                    source_type,
                    source_id,
                    title,
                    url,
                    datetime.now(timezone.utc).isoformat(),
                    note_path,
                    status,
                ),
            )

    def all(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM processed ORDER BY processed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def read_rows(path: Path) -> list[dict]:
    """Every ledger row, read without creating, migrating or writing the ledger.

    Triage and digests only look. Opening through `Ledger` would create the file
    and schema when absent, so this goes through a read-only SQLite URI instead.
    """
    path = Path(path)
    if not path.exists():
        return []
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM processed").fetchall()
    except sqlite3.OperationalError:  # the file exists but holds no ledger table
        return []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def processed_ids(path: Path, source_type: str) -> frozenset[str]:
    return frozenset(
        row["source_id"] for row in read_rows(path) if row["source_type"] == source_type
    )

