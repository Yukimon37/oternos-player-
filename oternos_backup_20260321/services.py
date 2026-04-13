"""
services.py — OTERNOS PLAYER
GlobalHotkeys, LastFmScrobbler, DiscordRPC, FolderWatcher.
"""

import sys
import os
import ctypes
import time
import json
import threading
import struct as _struct
import urllib.request
import urllib.parse
from pathlib import Path

if getattr(sys, "frozen", False):
    pass
else:
    pass


class GlobalHotkeys:
    """Register system-wide media key hotkeys via RegisterHotKey."""

    MOD_NOREPEAT = 0x4000
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_MEDIA_NEXT = 0xB0
    VK_MEDIA_PREV = 0xB1
    VK_MEDIA_STOP = 0xB2
    WM_HOTKEY = 0x0312

    def __init__(self, callbacks):
        """callbacks: dict of id -> callable, ids 1-4 for play/next/prev/stop"""
        self.callbacks = callbacks
        self._thread = None
        self._active = False

    def start(self):
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._active = False

    def _run(self):
        import ctypes.wintypes as _wintypes

        user32 = ctypes.WinDLL("user32")
        keys = [
            (1, self.MOD_NOREPEAT, self.VK_MEDIA_PLAY_PAUSE),
            (2, self.MOD_NOREPEAT, self.VK_MEDIA_NEXT),
            (3, self.MOD_NOREPEAT, self.VK_MEDIA_PREV),
            (4, self.MOD_NOREPEAT, self.VK_MEDIA_STOP),
        ]
        registered = []
        for hid, mod, vk in keys:
            if user32.RegisterHotKey(None, hid, mod, vk):
                registered.append(hid)

        msg = _wintypes.MSG()
        while self._active:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == self.WM_HOTKEY:
                    hid = msg.wParam
                    cb = self.callbacks.get(hid)
                    if cb:
                        cb()
            time.sleep(0.02)

        for hid in registered:
            user32.UnregisterHotKey(None, hid)


# ─────────────────────────────────────────
#  LAST.FM SCROBBLER
# ─────────────────────────────────────────
class LastFmScrobbler:
    """Handles Last.fm auth (md5-based) + scrobbling + now-playing."""

    ROOT = "https://ws.audioscrobbler.com/2.0/"

    def __init__(self, api_key="", api_secret="", session_key=""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session_key = session_key
        self._enabled = False
        self._current = None  # (artist, title, start_ts)

    @property
    def ready(self):
        return bool(self.api_key and self.api_secret and self.session_key)

    def _sign(self, params):
        import hashlib

        keys = sorted(k for k in params if k != "format")
        raw = "".join(k + params[k] for k in keys) + self.api_secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _call(self, params, post=False):
        params["api_key"] = self.api_key
        params["format"] = "json"
        params["api_sig"] = self._sign(params)
        data = urllib.parse.urlencode(params).encode()
        try:
            if post:
                req = urllib.request.Request(self.ROOT, data=data)
            else:
                req = urllib.request.Request(
                    self.ROOT + "?" + urllib.parse.urlencode(params)
                )
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def get_auth_url(self, token):
        return f"https://www.last.fm/api/auth/?api_key={self.api_key}&token={token}"

    def get_token(self):
        r = self._call({"method": "auth.getToken"})
        return r.get("token") if r else None

    def get_session(self, token):
        r = self._call({"method": "auth.getSession", "token": token})
        if r and "session" in r:
            self.session_key = r["session"]["key"]
            return self.session_key
        return None

    def now_playing(self, artist, title, album="", duration=0):
        if not self.ready:
            return
        params = {
            "method": "track.updateNowPlaying",
            "artist": artist,
            "track": title,
            "sk": self.session_key,
        }
        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(int(duration))
        threading.Thread(
            target=lambda: self._call(params, post=True), daemon=True
        ).start()

    def scrobble(self, artist, title, album="", duration=0, timestamp=None):
        if not self.ready:
            return
        ts = str(int(timestamp or time.time()))
        params = {
            "method": "track.scrobble",
            "artist": artist,
            "track": title,
            "timestamp": ts,
            "sk": self.session_key,
        }
        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(int(duration))
        threading.Thread(
            target=lambda: self._call(params, post=True), daemon=True
        ).start()

    def track_started(self, track):
        """Call when track begins playing."""
        self._current = (
            track.get("artist", ""),
            track.get("title", ""),
            track.get("album", ""),
            track.get("duration", 0),
            time.time(),
        )
        self.now_playing(
            track.get("artist", ""),
            track.get("title", ""),
            track.get("album", ""),
            track.get("duration", 0),
        )

    def track_maybe_scrobble(self):
        """Call periodically — scrobbles when >50% played or >4 min."""
        if not self._current:
            return
        artist, title, album, dur, start = self._current
        elapsed = time.time() - start
        threshold = min(dur * 0.5, 240) if dur > 30 else 0
        if threshold and elapsed >= threshold:
            self.scrobble(artist, title, album, dur, start)
            self._current = None


# ─────────────────────────────────────────
#  DISCORD RICH PRESENCE
# ─────────────────────────────────────────
class DiscordRPC:
    """Minimal Discord IPC Rich Presence — no external libs."""

    # Set DISCORD_CLIENT_ID in your environment, or replace the fallback below
    # with your own Discord application client ID from discord.com/developers
    CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")

    def __init__(self):
        self._sock = None
        self._active = False
        self._seq = 0
        self._thread = None

    def connect(self):
        try:
            for i in range(10):
                pipe = f"\\\\.\\pipe\\discord-ipc-{i}"
                try:
                    self._sock = open(pipe, "r+b", buffering=0)
                    break
                except OSError:
                    continue
            if not self._sock:
                return False
            # Handshake
            self._send(0, {"v": 1, "client_id": self.CLIENT_ID})
            resp = self._recv()
            self._active = resp is not None
            return self._active
        except Exception:
            return False

    def set_activity(self, title, artist, elapsed_s=0, duration_s=0):
        if not self._active:
            return
        try:
            now_ms = int(time.time() * 1000)
            payload = {
                "cmd": "SET_ACTIVITY",
                "args": {
                    "pid": os.getpid(),
                    "activity": {
                        "details": title[:128],
                        "state": f"by {artist}"[:128],
                        "assets": {
                            "large_image": "oternos_logo",
                            "large_text": "OTERNOS PLAYER",
                        },
                        "timestamps": {
                            "start": now_ms - int(elapsed_s * 1000),
                        },
                        "type": 2,  # Listening
                    },
                },
                "nonce": str(self._seq),
            }
            self._send(1, payload)
            self._recv()
        except Exception:
            self._active = False

    def clear(self):
        if not self._active:
            return
        try:
            self._send(
                1,
                {
                    "cmd": "SET_ACTIVITY",
                    "args": {"pid": os.getpid(), "activity": {}},
                    "nonce": str(self._seq),
                },
            )
            self._recv()
        except Exception:
            pass

    def _send(self, op, data):
        payload = json.dumps(data).encode()
        self._sock.write(_struct.pack("<II", op, len(payload)) + payload)
        self._seq += 1

    def _recv(self):
        try:
            header = self._sock.read(8)
            if not header or len(header) < 8:
                return None
            op, length = _struct.unpack("<II", header)
            body = self._sock.read(length)
            return json.loads(body)
        except Exception:
            return None


# ─────────────────────────────────────────
#  FOLDER WATCHER
# ─────────────────────────────────────────
class FolderWatcher:
    """Watches a directory for new audio files and calls on_new(path)."""

    AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"}

    def __init__(self, on_new):
        self.on_new = on_new
        self._paths = set()
        self._thread = None
        self._active = False
        self._watched = []  # list of dirs

    def watch(self, directory):
        d = str(Path(directory).resolve())
        if d in self._watched:
            return
        self._watched.append(d)
        if not self._active:
            self._active = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._active = False
        self._watched = []

    def _run(self):
        """Pure-Python polling fallback (no watchdog needed)."""
        seen = {}
        while self._active:
            for d in list(self._watched):
                try:
                    for f in Path(d).rglob("*"):
                        if f.suffix.lower() in self.AUDIO_EXT:
                            key = str(f)
                            mtime = f.stat().st_mtime
                            if key not in seen:
                                # Genuinely new file
                                seen[key] = mtime
                                self.on_new(key)
                            elif seen[key] != mtime:
                                # Existing file was modified
                                seen[key] = mtime
                                self.on_new(key)
                except Exception:
                    pass
            time.sleep(4)


# ─────────────────────────────────────────
#  AUDIO ENGINE — Windows MCI
# ─────────────────────────────────────────