# meeting-note-taker

A self-hosted Google Meet notetaker. A headless-Chromium bot joins as a guest,
captures every remote participant's audio in-page via WebRTC, and Whisper
transcribes it. A small FastAPI + React app lets you submit Meet URLs and
browse past recordings + transcripts.

## Layout

```
meeting-note-taker/
├── server/                 FastAPI backend + bot worker
│   ├── api.py              endpoints (login, meetings CRUD, recording/transcript)
│   ├── auth.py             single-user shared-password sessions
│   ├── db.py               SQLite (data/meetings.db)
│   ├── jobs.py             subprocess spawning (1 concurrent meeting)
│   ├── models.py
│   └── bot/
│       ├── bot.py          Playwright join + lifecycle
│       ├── worker.py       subprocess entry: python -m server.bot.worker <id>
│       ├── transcribe.py   OpenAI Whisper call
│       ├── inject_capture.js   in-page WebRTC audio capture
│       └── cli.py          standalone CLI for manual testing
├── web/                    Vite + React + Tailwind SPA
│   └── src/{App,api,pages,components}
├── data/                   gitignored — SQLite + recordings/ + transcripts/
└── .env.example
```

## How audio capture works

An init script (`server/bot/inject_capture.js`) runs *before* Meet's own JS,
monkey-patches `RTCPeerConnection` to grab every remote audio track, mixes
them into a single `MediaStream` via `AudioContext`, and records with
`MediaRecorder` (audio/webm; opus). Chunks are base64'd back to Python via
`page.expose_function` and concatenated into one `.webm`.

No PulseAudio, no OS-level audio routing — fully in-page.

## Local dev

### Backend

```bash
cd meeting-note-taker
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
playwright install chromium
cp .env.example .env   # set OPENAI_API_KEY, APP_PASSWORD, SESSION_SECRET
uvicorn server.api:app --reload --port 8000
```

### Frontend

```bash
cd web
npm install
npm run dev   # http://localhost:5173 (proxies /api to :8000)
```

For a single-port run: `cd web && npm run build`, then start uvicorn — the
backend serves `web/dist` at `/`.

### Manual CLI (no API/UI)

```bash
python -m server.bot.cli "https://meet.google.com/abc-defg-hij" --duration 600
```

## API quick reference

All endpoints under `/api/*`. All except `/api/login` require the session cookie.

| method | path                                | purpose                       |
|--------|-------------------------------------|-------------------------------|
| POST   | `/api/login`                        | `{password}` → cookie         |
| POST   | `/api/logout`                       | clear cookie                  |
| GET    | `/api/me`                           | session check                 |
| POST   | `/api/meetings`                     | `{url, display_name?, duration_cap_s?}` → spawns bot |
| GET    | `/api/meetings`                     | list (newest first)           |
| GET    | `/api/meetings/{id}`                | detail (incl. status)         |
| GET    | `/api/meetings/{id}/recording`      | streams `.webm`               |
| GET    | `/api/meetings/{id}/transcript`     | text                          |
| POST   | `/api/meetings/{id}/cancel`         | SIGTERM the worker            |

## Status lifecycle

`queued → joining → waiting_admit → recording → transcribing → done`
(or `failed` / `cancelled` at any point — error message stored on the row.)

## Known limits

- **Whisper `whisper-1` has a 25 MB upload cap** (~25 min of opus). Longer
  meetings need ffmpeg-chunking before the API call — *todo*.
- **Selectors are brittle.** Meet's DOM changes; join-flow selectors in
  `bot.py::_enter_name_and_request` may need updating after a UI revision.
- **One concurrent meeting** on v1 (Chromium ~400 MB). Bumping the cap means
  introducing a real queue (RQ + Redis) and watching VPS RAM.
- **Single combined audio track.** No per-speaker diarization. Swap in
  Deepgram (live) or pyannote (offline) if needed.
- **Detection.** Google may flag headless joins on the VPS. Mitigation:
  run non-headless under `xvfb-run`, or use a real Chrome profile.
- **No HTTPS in this repo.** Deploy behind Caddy / a reverse proxy that
  terminates TLS — *todo (Phase 5)*.
