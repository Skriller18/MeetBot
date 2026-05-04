# meet-notetaker

A self-hosted Google Meet bot that joins as a guest, captures the audio of every
remote participant, and produces a Whisper transcript when the meeting ends.

## How it works

1. **Playwright** launches headless Chromium with fake mic/cam devices and opens the Meet URL.
2. The bot fills in a display name, mutes mic + camera, and clicks **Ask to join**.
3. An init script (`src/inject_capture.js`) monkey-patches `RTCPeerConnection`
   so every incoming remote audio track is mixed into one `MediaStream` and
   recorded with `MediaRecorder` (audio/webm; opus).
4. Recorded chunks stream back to Python via `page.expose_function` and are
   appended to a single `.webm` file.
5. After the call (or the `--duration` budget), the file is sent to OpenAI
   **Whisper** and written to `transcripts/`.

No PulseAudio, no OS-level audio routing — capture happens in-page.

## Setup

```bash
cd meet-notetaker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # then put your OPENAI_API_KEY in
```

## Run

```bash
python -m src.main "https://meet.google.com/abc-defg-hij" --duration 1800
```

A human host still has to admit the bot from the lobby (Meet's guest flow).
The `--duration` is a hard cap; default 30 min.

## Known caveats / next steps

- **Selectors are brittle.** Meet's DOM changes; the join-flow selectors in
  `bot.py::_enter_name_and_request` may need updating after a UI revision.
- **Whisper `whisper-1` has a 25 MB upload cap** — long meetings need
  chunking with ffmpeg before the API call. Not implemented yet.
- **Single combined audio track.** No per-speaker diarization. Add via
  Deepgram (live) or pyannote (offline) if you need it.
- **Real-time transcripts** would mean swapping the `MediaRecorder` for a
  streaming ASR (Deepgram WebSocket from inside the page, or pipe chunks to
  AssemblyAI as they arrive).
- **Detection.** Google may flag headless joins. If you hit issues, run
  with `headless=False` under Xvfb, or use a real Chrome profile.
