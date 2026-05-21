"""FastAPI app: login + meetings CRUD + recording/transcript download."""
from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db, jobs
from .models import CreateMeetingRequest, LoginRequest, Meeting

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = REPO_ROOT / "web" / "dist"

load_dotenv(REPO_ROOT / ".env")
db.init_db()

app = FastAPI(title="meeting-note-taker", version="0.2.0")


# ---------- auth ----------

@app.post("/api/login")
def login(body: LoginRequest, response: Response) -> dict:
    if not auth.check_password(body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid password")
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.issue_token(),
        max_age=auth.MAX_AGE_S,
        httponly=True,
        samesite="lax",
        # secure=True in prod is set by the reverse proxy / can be added via env
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/api/me")
def me(user: str = Depends(auth.require_session)) -> dict:
    return {"user": user}


# ---------- meetings ----------

@app.post("/api/meetings", response_model=Meeting, status_code=201)
def create_meeting(
    body: CreateMeetingRequest,
    _user: str = Depends(auth.require_session),
) -> Meeting:
    if not jobs.can_start():
        raise HTTPException(status.HTTP_409_CONFLICT, "another meeting is in progress")
    meeting_id = uuid.uuid4().hex[:12]
    name = body.display_name or "Notetaker"
    row = db.insert_meeting(meeting_id, str(body.url), name, body.duration_cap_s)
    jobs.spawn_worker(meeting_id)
    return Meeting.from_row(row)


@app.get("/api/meetings", response_model=list[Meeting])
def list_meetings(_user: str = Depends(auth.require_session)) -> list[Meeting]:
    return [Meeting.from_row(r) for r in db.list_meetings()]


@app.get("/api/meetings/{meeting_id}", response_model=Meeting)
def get_meeting(meeting_id: str, _user: str = Depends(auth.require_session)) -> Meeting:
    row = db.get_meeting(meeting_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Meeting.from_row(row)


@app.get("/api/meetings/{meeting_id}/recording")
def get_recording(meeting_id: str, _user: str = Depends(auth.require_session)) -> FileResponse:
    row = db.get_meeting(meeting_id)
    if not row or not row.get("recording_path"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    path = Path(row["recording_path"])
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recording file missing")
    return FileResponse(path, media_type="audio/webm", filename=f"{meeting_id}.webm")


@app.get("/api/meetings/{meeting_id}/transcript", response_class=PlainTextResponse)
def get_transcript(meeting_id: str, _user: str = Depends(auth.require_session)) -> str:
    row = db.get_meeting(meeting_id)
    if not row or not row.get("transcript_path"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    path = Path(row["transcript_path"])
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transcript file missing")
    return path.read_text()


@app.post("/api/meetings/{meeting_id}/cancel")
def cancel_meeting(meeting_id: str, _user: str = Depends(auth.require_session)) -> dict:
    if not jobs.cancel(meeting_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no active job for that meeting")
    return {"ok": True}


# ---------- frontend ----------

# Serve the built SPA if present. In dev, run Vite separately.
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
