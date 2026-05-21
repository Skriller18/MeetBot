"""Spawn the bot worker as a subprocess. v1: cap at 1 concurrent meeting."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from . import db

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_ROOT = Path(__file__).resolve().parent

MAX_CONCURRENT = 1


ACTIVE_STATUSES = ("queued", "joining", "waiting_admit", "recording", "transcribing")


def can_start() -> bool:
    busy = sum(1 for m in db.list_meetings(limit=50) if m["status"] in ACTIVE_STATUSES)
    return busy < MAX_CONCURRENT


def spawn_worker(meeting_id: str) -> int:
    env = os.environ.copy()
    # Worker is invoked as a module so relative imports resolve.
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.bot.worker", meeting_id],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    db.update_status(meeting_id, "queued", pid=proc.pid)
    return proc.pid


def cancel(meeting_id: str) -> bool:
    row = db.get_meeting(meeting_id)
    if not row or not row.get("pid"):
        return False
    try:
        os.killpg(row["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass
    db.update_status(meeting_id, "cancelled", error="cancelled by user", ended_at=db.now())
    return True
