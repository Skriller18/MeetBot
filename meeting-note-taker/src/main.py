"""CLI entry point: python -m src.main <meet-url> --duration 1800"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .bot import MeetBot
from .transcribe import transcribe

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Join a Google Meet, record, transcribe.")
    p.add_argument("meet_url")
    p.add_argument("--duration", type=int, default=1800,
                   help="Max meeting duration in seconds (default: 30 min)")
    p.add_argument("--name", default=None,
                   help="Display name for the bot (default: $BOT_DISPLAY_NAME or 'Notetaker')")
    p.add_argument("--no-transcribe", action="store_true",
                   help="Skip the Whisper step (just produce the .webm)")
    return p.parse_args()


async def amain() -> None:
    load_dotenv(ROOT / ".env")
    args = parse_args()
    name = args.name or os.environ.get("BOT_DISPLAY_NAME", "Notetaker")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    webm = ROOT / "recordings" / f"{stamp}.webm"
    txt = ROOT / "transcripts" / f"{stamp}.txt"

    bot = MeetBot(args.meet_url, name, webm)
    await bot.run(args.duration)

    if args.no_transcribe:
        print(f"audio: {webm}")
        return

    print("[main] transcribing…", flush=True)
    text = transcribe(webm)
    txt.write_text(text)
    print(f"audio: {webm}\ntranscript: {txt}")


if __name__ == "__main__":
    asyncio.run(amain())
