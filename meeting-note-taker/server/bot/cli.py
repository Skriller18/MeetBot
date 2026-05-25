"""Standalone CLI for manual testing: python -m server.bot.cli <meet-url>"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .bot import MeetBot
from .transcribe import transcribe

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RECORDINGS = REPO_ROOT / "data" / "recordings"
TRANSCRIPTS = REPO_ROOT / "data" / "transcripts"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Join a Google Meet, record, transcribe.")
    p.add_argument("meet_url")
    p.add_argument("--duration", type=int, default=1800)
    p.add_argument("--name", default=None)
    p.add_argument("--no-transcribe", action="store_true")
    p.add_argument("--debug-dir", type=Path, default=REPO_ROOT / "debug")
    p.add_argument("--headful", action="store_true", help="Run with visible browser window")
    p.add_argument("--real-chrome", action="store_true", help="Use real Google Chrome instead of Playwright Chromium")
    return p.parse_args()


async def amain() -> None:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    name = args.name or os.environ.get("BOT_DISPLAY_NAME", "Notetaker")

    RECORDINGS.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    webm = RECORDINGS / f"{stamp}.webm"
    txt = TRANSCRIPTS / f"{stamp}.txt"

    # Determine if we should run headless
    headless = not args.headful
    use_real_chrome = args.real_chrome
    
    bot = MeetBot(args.meet_url, name, webm, debug_dir=args.debug_dir, headless=headless, use_real_chrome=use_real_chrome)
    
    print("=" * 60)
    print("Google Meet Bot - Test Run")
    print("=" * 60)
    print(f"URL: {args.meet_url}")
    print(f"Name: {name}")
    print(f"Duration: {args.duration}s")
    print(f"Headless: {headless}")
    print(f"Real Chrome: {use_real_chrome}")
    print()
    print("Note: If Google blocks guest access, try:")
    print("  1. Use --real-chrome flag (launches your actual Chrome)")
    print("  2. Set GOOGLE_CHROME_USER_DATA_DIR in .env")
    print("  3. Run with --headful flag (manual sign-in)")
    print("=" * 60)
    
    await bot.run(args.duration)
    print(f"audio: {webm}")

    if args.no_transcribe:
        return
    text = transcribe(webm)
    txt.write_text(text)
    print(f"transcript: {txt}")


if __name__ == "__main__":
    asyncio.run(amain())
