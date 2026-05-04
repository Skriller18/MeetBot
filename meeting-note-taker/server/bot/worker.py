"""Subprocess entry: python -m server.bot.worker <meeting_id>

Each lifecycle change is persisted so the API can reflect progress.
Heavy imports (playwright, openai) live inside run() so a missing dep is
recorded against the meeting instead of dying silently.
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from .. import db

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RECORDINGS = REPO_ROOT / "data" / "recordings"
TRANSCRIPTS = REPO_ROOT / "data" / "transcripts"


async def run(meeting_id: str) -> int:
    db.init_db()
    row = db.get_meeting(meeting_id)
    if not row:
        print(f"[worker] no meeting {meeting_id}", file=sys.stderr)
        return 2

    try:
        from dotenv import load_dotenv
        from .bot import MeetBot
        from .transcribe import transcribe

        load_dotenv(REPO_ROOT / ".env")
        RECORDINGS.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        webm_path = RECORDINGS / f"{meeting_id}.webm"
        txt_path = TRANSCRIPTS / f"{meeting_id}.txt"

        async def on_status(s: str) -> None:
            fields = {"started_at": db.now()} if s == "joining" else {}
            db.update_status(meeting_id, s, **fields)

        bot = MeetBot(row["url"], row["display_name"], webm_path, on_status=on_status)
        await bot.run(row["duration_cap_s"])
        db.update_status(meeting_id, "transcribing", recording_path=str(webm_path))

        text = transcribe(webm_path)
        txt_path.write_text(text)
        db.update_status(
            meeting_id,
            "done",
            transcript_path=str(txt_path),
            ended_at=db.now(),
        )
        return 0
    except Exception as e:
        traceback.print_exc()
        db.update_status(
            meeting_id,
            "failed",
            error=f"{type(e).__name__}: {e}",
            ended_at=db.now(),
        )
        return 1


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m server.bot.worker <meeting_id>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(run(sys.argv[1])))


if __name__ == "__main__":
    main()
