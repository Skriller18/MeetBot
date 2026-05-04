"""Send a recorded webm to OpenAI Whisper and return a transcript."""
from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI


def transcribe(audio_path: Path) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with audio_path.open("rb") as f:
        # whisper-1 accepts webm/opus directly; up to 25 MB per request.
        # For longer meetings, split before calling — see README.
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
        )
    return result if isinstance(result, str) else result.text
