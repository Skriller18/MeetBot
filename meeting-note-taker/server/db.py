"""SQLite access. One connection per request — SQLite handles concurrency fine here."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "meetings.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    url TEXT NOT NULL,
    display_name TEXT NOT NULL,
    duration_cap_s INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    ended_at INTEGER,
    recording_path TEXT,
    transcript_path TEXT,
    pid INTEGER
);
CREATE INDEX IF NOT EXISTS idx_meetings_created ON meetings(created_at DESC);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def now() -> int:
    return int(time.time())


def insert_meeting(meeting_id: str, url: str, display_name: str, duration_cap_s: int) -> dict:
    with connect() as conn:
        conn.execute(
            """INSERT INTO meetings (id, url, display_name, duration_cap_s, status, created_at)
               VALUES (?, ?, ?, ?, 'queued', ?)""",
            (meeting_id, url, display_name, duration_cap_s, now()),
        )
        return get_meeting(meeting_id)  # type: ignore[return-value]


def get_meeting(meeting_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    return dict(row) if row else None


def list_meetings(limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_status(meeting_id: str, status: str, **fields) -> None:
    cols = ["status = ?"]
    vals: list = [status]
    for k, v in fields.items():
        cols.append(f"{k} = ?")
        vals.append(v)
    vals.append(meeting_id)
    with connect() as conn:
        conn.execute(f"UPDATE meetings SET {', '.join(cols)} WHERE id = ?", vals)
