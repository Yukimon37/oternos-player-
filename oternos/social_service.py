"""Hosted OTERNOS Friends service with Discord OAuth sign-in.

Run this as a separate web service. It deliberately does not handle Discord
passwords: Discord's OAuth page does that job and only returns public identity
data needed by the OTERNOS friend list.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import string
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field


DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
LOGIN_TTL_SECONDS = 10 * 60
SESSION_TTL_SECONDS = 90 * 24 * 60 * 60
PRESENCE_TTL_SECONDS = 90


class LoginStartPayload(BaseModel):
    device_id: str = Field(min_length=8, max_length=160)
    login_key: str = Field(min_length=24, max_length=200)


class FriendRequestPayload(BaseModel):
    friend_code: str = Field(min_length=5, max_length=32)


class PresencePayload(BaseModel):
    online: bool = True
    share_activity: bool = False
    track_title: str = Field(default="", max_length=180)
    track_artist: str = Field(default="", max_length=180)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _database_path() -> Path:
    return Path(_env("OTERNOS_SOCIAL_DATABASE", "./data/oternos-social.sqlite3")).expanduser()


def _public_url() -> str:
    return _env("OTERNOS_SOCIAL_PUBLIC_URL").rstrip("/")


def _discord_redirect_uri() -> str:
    base = _public_url()
    return f"{base}/v1/auth/discord/callback" if base else ""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> float:
    return time.time()


def _connection() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def initialise_database() -> None:
    with _connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                avatar_url TEXT NOT NULL DEFAULT '',
                friend_code TEXT NOT NULL UNIQUE,
                activity_sharing INTEGER NOT NULL DEFAULT 0,
                presence_online INTEGER NOT NULL DEFAULT 0,
                track_title TEXT NOT NULL DEFAULT '',
                track_artist TEXT NOT NULL DEFAULT '',
                last_seen REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                request_id TEXT PRIMARY KEY,
                login_key_hash TEXT NOT NULL,
                device_id TEXT NOT NULL,
                state TEXT NOT NULL,
                user_id TEXT,
                session_token TEXT,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS friend_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                to_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                state TEXT NOT NULL,
                created_at REAL NOT NULL,
                responded_at REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_friend_requests_to_state
            ON friend_requests(to_user_id, state, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_friend_requests_from_state
            ON friend_requests(from_user_id, state, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id, expires_at);
            """
        )


def _cleanup(conn: sqlite3.Connection) -> None:
    now = _now()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    conn.execute("DELETE FROM login_attempts WHERE expires_at < ?", (now,))


def _require_discord_config() -> tuple[str, str, str]:
    client_id = _env("DISCORD_CLIENT_ID")
    client_secret = _env("DISCORD_CLIENT_SECRET")
    redirect_uri = _discord_redirect_uri()
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=503,
            detail="Friends sign-in is not configured. Add Discord OAuth and public URL environment variables.",
        )
    return client_id, client_secret, redirect_uri


def _new_friend_code(conn: sqlite3.Connection) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(40):
        code = "OTR-" + "".join(secrets.choice(alphabet) for _ in range(6))
        existing = conn.execute("SELECT 1 FROM users WHERE friend_code = ?", (code,)).fetchone()
        if existing is None:
            return code
    raise RuntimeError("Could not generate a unique OTERNOS friend code.")


def _avatar_url(discord_user: dict[str, Any]) -> str:
    user_id = str(discord_user.get("id") or "").strip()
    avatar = str(discord_user.get("avatar") or "").strip()
    if user_id and avatar:
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png?size=128"
    return ""


def _profile_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "display_name": str(row["display_name"]),
        "avatar_url": str(row["avatar_url"] or ""),
        "friend_code": str(row["friend_code"]),
        "activity_sharing": bool(row["activity_sharing"]),
    }


def _friend_payload(row: sqlite3.Row, *, relationship: str, request_id: str = "") -> dict[str, Any]:
    online = bool(row["presence_online"]) and (_now() - float(row["last_seen"] or 0.0) <= PRESENCE_TTL_SECONDS)
    activity_visible = online and bool(row["activity_sharing"])
    title = str(row["track_title"] or "").strip() if activity_visible else ""
    artist = str(row["track_artist"] or "").strip() if activity_visible else ""
    now_playing = " - ".join(value for value in (title, artist) if value)
    return {
        "user_id": str(row["user_id"]),
        "display_name": str(row["display_name"]),
        "avatar_url": str(row["avatar_url"] or ""),
        "friend_code": str(row["friend_code"]),
        "relationship": relationship,
        "request_id": str(request_id),
        "presence": "LISTENING" if now_playing else ("ONLINE" if online else "OFFLINE"),
        "now_playing": now_playing,
    }


def _bearer_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in with Discord first.")
    token = value[7:].strip()
    if len(token) < 24:
        raise HTTPException(status_code=401, detail="Your Friends session is invalid.")
    return token


def _current_user(authorization: str | None) -> sqlite3.Row:
    token = _bearer_token(authorization)
    with _connection() as conn:
        _cleanup(conn)
        row = conn.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.user_id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at >= ?
            """,
            (_sha256(token), _now()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Your Friends session expired. Sign in again.")
    return row


def _discord_json(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=12.0) as response:
            raw = response.read(262144)
    except (urllib.error.URLError, OSError) as exc:
        raise HTTPException(status_code=502, detail="Could not reach Discord. Try signing in again.") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Discord returned an invalid sign-in response.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Discord returned an invalid sign-in response.")
    return payload


app = FastAPI(title="OTERNOS Friends", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    initialise_database()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "oternos-friends",
        "discord_configured": bool(_env("DISCORD_CLIENT_ID") and _env("DISCORD_CLIENT_SECRET") and _public_url()),
    }


@app.post("/v1/auth/start")
def start_auth(payload: LoginStartPayload) -> dict[str, Any]:
    client_id, _client_secret, _redirect_uri = _require_discord_config()
    request_id = secrets.token_urlsafe(32)
    expires_at = _now() + LOGIN_TTL_SECONDS
    with _connection() as conn:
        _cleanup(conn)
        conn.execute(
            """
            INSERT INTO login_attempts(request_id, login_key_hash, device_id, state, expires_at, created_at)
            VALUES (?, ?, ?, 'PENDING', ?, ?)
            """,
            (request_id, _sha256(payload.login_key), payload.device_id, expires_at, _now()),
        )
    query = urllib.parse.urlencode({"state": request_id})
    return {
        "request_id": request_id,
        "authorize_url": f"{_public_url()}/v1/auth/discord?{query}",
        "expires_at": expires_at,
        "client_id": client_id,
    }


@app.get("/v1/auth/discord")
def discord_auth(state: str = "") -> RedirectResponse:
    client_id, _client_secret, redirect_uri = _require_discord_config()
    with _connection() as conn:
        _cleanup(conn)
        attempt = conn.execute(
            "SELECT request_id FROM login_attempts WHERE request_id = ? AND state = 'PENDING' AND expires_at >= ?",
            (state, _now()),
        ).fetchone()
    if attempt is None:
        raise HTTPException(status_code=400, detail="This OTERNOS sign-in link has expired. Return to the app and try again.")
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify",
            "state": state,
            "prompt": "consent",
        }
    )
    return RedirectResponse(f"{DISCORD_AUTHORIZE_URL}?{query}", status_code=302)


@app.get("/v1/auth/discord/callback")
def discord_callback(code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    if error:
        return HTMLResponse("<h2>OTERNOS sign-in cancelled</h2><p>Return to the OTERNOS app and try again.</p>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h2>OTERNOS sign-in failed</h2><p>Missing Discord sign-in details.</p>", status_code=400)
    client_id, client_secret, redirect_uri = _require_discord_config()
    with _connection() as conn:
        _cleanup(conn)
        attempt = conn.execute(
            "SELECT * FROM login_attempts WHERE request_id = ? AND state = 'PENDING' AND expires_at >= ?",
            (state, _now()),
        ).fetchone()
    if attempt is None:
        return HTMLResponse("<h2>OTERNOS sign-in expired</h2><p>Return to the OTERNOS app and start again.</p>", status_code=400)
    token_body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    token_response = _discord_json(
        DISCORD_TOKEN_URL,
        data=token_body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    access_token = str(token_response.get("access_token") or "").strip()
    if not access_token:
        return HTMLResponse("<h2>OTERNOS sign-in failed</h2><p>Discord did not return an access token.</p>", status_code=502)
    discord_user = _discord_json(DISCORD_USER_URL, headers={"Authorization": f"Bearer {access_token}"})
    user_id = str(discord_user.get("id") or "").strip()
    display_name = str(discord_user.get("global_name") or discord_user.get("username") or "").strip()[:80]
    if not user_id or not display_name:
        return HTMLResponse("<h2>OTERNOS sign-in failed</h2><p>Discord did not return a usable profile.</p>", status_code=502)
    session_token = secrets.token_urlsafe(40)
    now = _now()
    with _connection() as conn:
        existing = conn.execute("SELECT friend_code FROM users WHERE user_id = ?", (user_id,)).fetchone()
        friend_code = str(existing["friend_code"]) if existing is not None else _new_friend_code(conn)
        conn.execute(
            """
            INSERT INTO users(user_id, display_name, avatar_url, friend_code, last_seen, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET display_name = excluded.display_name, avatar_url = excluded.avatar_url
            """,
            (user_id, display_name, _avatar_url(discord_user), friend_code, now, now),
        )
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (_sha256(session_token), user_id, now + SESSION_TTL_SECONDS, now),
        )
        conn.execute(
            "UPDATE login_attempts SET state = 'COMPLETE', user_id = ?, session_token = ? WHERE request_id = ?",
            (user_id, session_token, state),
        )
    return HTMLResponse(
        "<h2>OTERNOS is connected</h2><p>You can close this page and return to the OTERNOS app.</p>",
        status_code=200,
    )


@app.get("/v1/auth/status")
def auth_status(request_id: str = "", x_oternos_login_key: str | None = Header(default=None)) -> dict[str, Any]:
    if not request_id or not x_oternos_login_key:
        raise HTTPException(status_code=400, detail="This sign-in request is incomplete.")
    with _connection() as conn:
        _cleanup(conn)
        attempt = conn.execute("SELECT * FROM login_attempts WHERE request_id = ?", (request_id,)).fetchone()
        if attempt is None or not secrets.compare_digest(str(attempt["login_key_hash"]), _sha256(x_oternos_login_key)):
            raise HTTPException(status_code=404, detail="This sign-in request is no longer available.")
        if str(attempt["state"]) == "PENDING":
            return {"state": "PENDING"}
        if str(attempt["state"]) != "COMPLETE" or not attempt["user_id"] or not attempt["session_token"]:
            raise HTTPException(status_code=400, detail="Discord sign-in did not complete.")
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (str(attempt["user_id"]),)).fetchone()
        response = {"state": "COMPLETE", "session_token": str(attempt["session_token"]), "profile": _profile_payload(user)}
        conn.execute("DELETE FROM login_attempts WHERE request_id = ?", (request_id,))
        return response


@app.post("/v1/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    token = _bearer_token(authorization)
    with _connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_sha256(token),))
    return {"ok": True}


@app.get("/v1/friends")
def list_friends(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = str(user["user_id"])
    with _connection() as conn:
        friend_rows = conn.execute(
            """
            SELECT users.* FROM friend_requests
            JOIN users ON users.user_id = CASE
                WHEN friend_requests.from_user_id = ? THEN friend_requests.to_user_id
                ELSE friend_requests.from_user_id
            END
            WHERE friend_requests.state = 'ACCEPTED'
              AND (friend_requests.from_user_id = ? OR friend_requests.to_user_id = ?)
            ORDER BY lower(users.display_name)
            """,
            (user_id, user_id, user_id),
        ).fetchall()
        incoming_rows = conn.execute(
            """
            SELECT friend_requests.request_id, users.* FROM friend_requests
            JOIN users ON users.user_id = friend_requests.from_user_id
            WHERE friend_requests.to_user_id = ? AND friend_requests.state = 'PENDING'
            ORDER BY friend_requests.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return {
        "profile": _profile_payload(user),
        "friends": [_friend_payload(row, relationship="FRIEND") for row in friend_rows],
        "incoming_requests": [
            _friend_payload(row, relationship="INCOMING", request_id=str(row["request_id"])) for row in incoming_rows
        ],
    }


@app.post("/v1/friends/requests")
def create_friend_request(payload: FriendRequestPayload, authorization: str | None = Header(default=None)) -> dict[str, bool]:
    user = _current_user(authorization)
    friend_code = str(payload.friend_code).strip().upper()
    with _connection() as conn:
        target = conn.execute("SELECT * FROM users WHERE friend_code = ?", (friend_code,)).fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="No OTERNOS user has that friend code.")
        if str(target["user_id"]) == str(user["user_id"]):
            raise HTTPException(status_code=400, detail="You cannot add yourself.")
        existing = conn.execute(
            """
            SELECT * FROM friend_requests
            WHERE (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?)
            ORDER BY request_id DESC LIMIT 1
            """,
            (str(user["user_id"]), str(target["user_id"]), str(target["user_id"]), str(user["user_id"])),
        ).fetchone()
        if existing is not None and str(existing["state"]) == "ACCEPTED":
            raise HTTPException(status_code=400, detail="You are already friends.")
        if existing is not None and str(existing["state"]) == "PENDING":
            if str(existing["to_user_id"]) == str(user["user_id"]):
                raise HTTPException(status_code=400, detail="This person already sent you a request. Accept it in Friends.")
            raise HTTPException(status_code=400, detail="That friend request is already pending.")
        conn.execute(
            "INSERT INTO friend_requests(from_user_id, to_user_id, state, created_at) VALUES (?, ?, 'PENDING', ?)",
            (str(user["user_id"]), str(target["user_id"]), _now()),
        )
    return {"ok": True}


@app.post("/v1/friends/requests/{request_id}/accept")
def accept_friend_request(request_id: int, authorization: str | None = Header(default=None)) -> dict[str, bool]:
    user = _current_user(authorization)
    with _connection() as conn:
        updated = conn.execute(
            """
            UPDATE friend_requests SET state = 'ACCEPTED', responded_at = ?
            WHERE request_id = ? AND to_user_id = ? AND state = 'PENDING'
            """,
            (_now(), int(request_id), str(user["user_id"])),
        ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="That friend request is no longer pending.")
    return {"ok": True}


@app.delete("/v1/friends/{friend_id}")
def remove_friend(friend_id: str, authorization: str | None = Header(default=None)) -> dict[str, bool]:
    user = _current_user(authorization)
    user_id = str(user["user_id"])
    with _connection() as conn:
        updated = conn.execute(
            """
            UPDATE friend_requests SET state = 'REMOVED', responded_at = ?
            WHERE state = 'ACCEPTED' AND (
                (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?)
            )
            """,
            (_now(), user_id, friend_id, friend_id, user_id),
        ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="That friend connection does not exist.")
    return {"ok": True}


@app.put("/v1/presence")
def update_presence(payload: PresencePayload, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = str(user["user_id"])
    title = str(payload.track_title or "").strip() if payload.share_activity else ""
    artist = str(payload.track_artist or "").strip() if payload.share_activity else ""
    with _connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET activity_sharing = ?, presence_online = ?, track_title = ?, track_artist = ?, last_seen = ?
            WHERE user_id = ?
            """,
            (int(payload.share_activity), int(payload.online), title, artist, _now(), user_id),
        )
        fresh = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return {"profile": _profile_payload(fresh)}
