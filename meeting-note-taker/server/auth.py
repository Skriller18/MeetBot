"""Single-user shared-password auth via signed session cookie."""
from __future__ import annotations

import os
import secrets

from fastapi import Cookie, HTTPException, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE_NAME = "mnt_session"
MAX_AGE_S = 60 * 60 * 24 * 14  # 14 days


def _serializer() -> URLSafeTimedSerializer:
    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        # Dev fallback so the app boots without env config; warn loudly.
        print("[auth] SESSION_SECRET not set — using random per-process secret", flush=True)
        secret = secrets.token_hex(32)
        os.environ["SESSION_SECRET"] = secret
    return URLSafeTimedSerializer(secret, salt="mnt-session")


def issue_token() -> str:
    return _serializer().dumps({"u": "default"})


def check_password(submitted: str) -> bool:
    expected = os.environ.get("APP_PASSWORD", "")
    if not expected:
        # Refuse to authenticate anyone if no password is configured.
        return False
    return secrets.compare_digest(submitted, expected)


def require_session(mnt_session: str | None = Cookie(default=None)) -> str:
    if not mnt_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        data = _serializer().loads(mnt_session, max_age=MAX_AGE_S)
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    return data["u"]
