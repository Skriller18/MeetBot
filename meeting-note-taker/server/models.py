from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class LoginRequest(BaseModel):
    password: str


class CreateMeetingRequest(BaseModel):
    url: HttpUrl
    display_name: Optional[str] = Field(default=None, max_length=80)
    duration_cap_s: int = Field(default=1800, ge=60, le=4 * 60 * 60)


class Meeting(BaseModel):
    id: str
    url: str
    display_name: str
    duration_cap_s: int
    status: str
    error: Optional[str] = None
    created_at: int
    started_at: Optional[int] = None
    ended_at: Optional[int] = None
    has_recording: bool = False
    has_transcript: bool = False

    @classmethod
    def from_row(cls, row: dict) -> "Meeting":
        return cls(
            id=row["id"],
            url=row["url"],
            display_name=row["display_name"],
            duration_cap_s=row["duration_cap_s"],
            status=row["status"],
            error=row.get("error"),
            created_at=row["created_at"],
            started_at=row.get("started_at"),
            ended_at=row.get("ended_at"),
            has_recording=bool(row.get("recording_path")),
            has_transcript=bool(row.get("transcript_path")),
        )
