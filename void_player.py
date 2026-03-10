"""
O T E R N O S  P L A Y E R
Cybercore Music Player — White Void Edition
Requires: pip install mutagen
Uses Windows built-in MCI audio — no pygame needed!
Run: python void_player.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import time
import math
import json
import random
import ctypes
from pathlib import Path

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    import numpy as _np
    import scipy.signal as _sig
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import watchdog.observers as _wdo
    import watchdog.events   as _wde
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# ── Last.fm credentials (user fills these in Settings) ──
LASTFM_API_KEY    = ""
LASTFM_API_SECRET = ""
LASTFM_API_ROOT   = "https://ws.audioscrobbler.com/2.0/"

# ── Spotify imports (stdlib only — no spotipy needed) ──
import urllib.request
import urllib.parse
import urllib.error
import base64
import hashlib
import os
import struct as _struct
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Windows MCI audio (built into Windows, zero install) ──
winmm = ctypes.WinDLL("winmm")

def mci(cmd):
    buf = ctypes.create_unicode_buffer(512)
    winmm.mciSendStringW(cmd, buf, 512, 0)
    return buf.value

# ─────────────────────────────────────────
#  PALETTE — White Void Cybercore
# ─────────────────────────────────────────
C = {
    "bg":      "#050505",       # near-black void
    "panel":   "#0c0c0c",       # surface
    "panel2":  "#131313",       # alt row — subtly lighter than panel
    "border":  "#1f1f1f",       # hairline separator
    "border2": "#2e2e2e",       # slightly brighter border
    "white":   "#e8e8e8",       # primary text
    "white2":  "#9a9a9a",       # secondary text
    "white3":  "#424242",       # muted / disabled
    "glow":    "#ffffff",       # hover / active
    "select":  "#1e1e1e",       # selection bg — clearly visible
    "select2": "#242424",       # deeper select
    "red":     "#cc2222",       # error / warning
}

# ─────────────────────────────────────────
#  HARDWARE ACCELERATOR FLAG
#  When True: GPU rendering hints, higher FPS, lower CPU overhead
#  When False: all animations throttled, poll rate halved
# ─────────────────────────────────────────
HW_ACCEL = True   # default on — user can toggle in settings

def hw_fps(hi, lo=8):
    """Return frame interval (ms) based on HW_ACCEL state."""
    return hi if HW_ACCEL else lo * 16

FM  = ("Courier New", 9)
FMS = ("Courier New", 8)
FML = ("Courier New", 10, "bold")
FMX = ("Courier New", 13, "bold")

DATA_FILE = Path.home() / ".voidplayer.json"
YT_CACHE  = Path.home() / ".voidplayer_cache"
YT_CACHE.mkdir(exist_ok=True)

# Embedded app icon (hex-O emblem, 64x64 PNG, base64)
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEMElEQVR4nO1bubHjMAzF"
    "92ykEpTKZagOBarDZagOBarDZdipS1C8wQ48NAQSB0HbM39fsp6/EgQ8gjh4/MCb0HXd"
    "zfL8vu/nVrqk+Gkl2GqwhFaEnKIFdl130xq/LMvQQq4Ff6IEtVCu9J0oj6ieAl7DH4"
    "/Hc/T7vr97v19LhJuAmhFPjUfUkADgJ8IVA6KMX9eV/fs7dTJ7QAvjAQDmeX7+fueU"
    "UHtAbRQuGQ/wanSNN1j1VBFQG+E1AW9ZliGKBAC9zmIajBh1i0tzJHinRNd1N2lKiDHA"
    "Q0BJcan4uVwuh3dqiJAIKHqA1/jalEaB8jyyJS/IeoDV+Fp3bf2dHAksARbjOYUsNb4F"
    "6fTwEMGR4O4FcgosyzJw8zgCqex0WnB6aHEgQBr9d7m6FhYiuHiQrQOoGz8ej0HKzS1H"
    "H+DfFJCmF6dn6Z0XD0hH/3K53KmgdV3ZNPUNwJFflmWY5zlbfFEveAmC1P1RCFe6psCR"
    "0ZKDcqdpgm3bDkZIwG9J3oD9BZWbEvD0AG/FZzXa8oxEiIYEDqkXFHsBVCDt1DhIoz+O"
    "48EwlI2/OWNzpNWMPsUJoN3oY0Datg2maQJq6PV6fXnfQoJWhxzQZnU7nPtQbvRpEKLG"
    "5pB6Bicr1SfnBRZSRAJSRVLB2sDnqRc4EjhwOqS/Nd82L4lp2I0sllAGjSNe3Sh+NPOf"
    "68I0rg8QQ8I4jgOmy1yLTXXRdo7hGyMUtSs7AMdgGQkXAZa5/46ewVsPAAR7AJ37kvGY"
    "JjVeQpueKJgJiGp4qCG1hnm9IGxv0IKcsaXANY7jME1TuC6mLGApeUuBqzTapWmjSa+o"
    "Y5MsILnZtm2wbVvTqF2CZ3o2T4McciPziVUmVyWY8wJLpKbG5oxHWZL7e4PzR4IgQpMm"
    "039bwDUFNClHU7tLsK4Qeb5x8hwsKC1J9X1/p0tdNUhJKPUBnhpg3/ezqxCSnsEsEOG6"
    "ls7SQ4JIQGpE+gEt8zXzWLsMT/XSvg9giAFWdrkVHS0J4zi+9AfW9GjR9QTgP2AkeYFm"
    "jS8NltIaouXbElSrwtp9gRJyJKRdINcR1laTqLPkdc86YN/3s2d1OB2JXCqiJOSUit4Y"
    "ycG8M4SQtsZa7w1qvoFbYylUO0P4H0gCd2hpnmeY5/mrdocRpbXIlDQa7w4HJGq3x993"
    "PsCqF4IScOgFpFgQdTAhChY9uGz364/I/D8kVXqpxTE5zzlBrewcSoVecT3AUxv0fX+P"
    "9oaWByWbnBRFlE6Scc9z21vc+xZUnRRFAV4SuCUy7SqQ5lkJmh5H1Q3WXkuhBZWUy+k7"
    "Hmh1VrfD+76fa4iQDjxEXpiw6Om6MxR5f2Bd14/dFgH40KUpgPiLU17v/Ni1OYCYOV8b"
    "n6p3hmpiQ9/393Vd3fk94vJk2MYIKtP6Bmn0HeJff3m6GQEU33p9/i+ic9mwtWarfgAA"
    "AABJRU5ErkJggg=="
)


# ─────────────────────────────────────────
#  SMOOTH ANIMATION UTILITIES
# ─────────────────────────────────────────
def _ease_out(t):
    """Cubic ease-out: fast start, smooth stop."""
    return 1 - (1 - t) ** 3

def _ease_in_out(t):
    """Smooth S-curve easing."""
    return t * t * (3 - 2 * t)

def _lerp(a, b, t):
    return a + (b - a) * t

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def _lerp_color(c1, c2, t):
    """Smoothly interpolate between two hex colors."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(_lerp(r1,r2,t), _lerp(g1,g2,t), _lerp(b1,b2,t))


class ColorAnim:
    """Animate a widget fg or bg color smoothly."""
    _jobs = {}

    @classmethod
    def run(cls, root, widget, attr, from_col, to_col,
            duration_ms=120, fps=60, ease_fn=_ease_out, on_done=None):
        wid = id(widget)
        if wid in cls._jobs:
            try: root.after_cancel(cls._jobs[wid])
            except: pass
        steps = max(1, int(duration_ms / (1000 / fps)))
        delay = max(8, int(1000 / fps))

        def _step(i=0):
            if i > steps:
                try: widget.config(**{attr: to_col})
                except: pass
                cls._jobs.pop(wid, None)
                if on_done: on_done()
                return
            t   = ease_fn(i / steps)
            col = _lerp_color(from_col, to_col, t)
            try: widget.config(**{attr: col})
            except: pass
            cls._jobs[wid] = root.after(delay, lambda: _step(i + 1))

        _step()


class FadeOverlay:
    """Stub — just calls the midpoint callback immediately. No canvas placement."""
    def __init__(self, root, content_frame):
        self.root  = root
        self.frame = content_frame
        self._active = False

    def flash(self, on_midpoint, duration_ms=50):
        on_midpoint()


# ─────────────────────────────────────────
#  EQ PROCESSOR  — real biquad IIR filters
# ─────────────────────────────────────────
class EQProcessor:
    """
    Applies a real 8-band parametric EQ to an MP3 file,
    writing a processed temp WAV. Uses scipy biquad filters.
    Falls back to passthrough if scipy unavailable.
    """
    EQ_PRESETS = {
        "flat":         [0,  0,  0,  0,  0,  0,  0,  0],
        "bass boost":   [7,  6,  4,  1,  0,  0,  0,  0],
        "treble boost": [0,  0,  0,  0,  1,  3,  6,  7],
        "vocal":        [-2,-1,  2,  5,  5,  2, -1, -2],
        "electronic":   [5,  4,  0, -2, -1,  2,  4,  4],
        "rock":         [4,  3,  1,  0,  0,  1,  3,  4],
        "classical":    [3,  2,  0,  0,  0,  0,  2,  3],
        "podcast":      [-1,-1,  2,  5,  4,  1,  0, -1],
    }
    BAND_FREQS = [60, 150, 400, 1000, 2400, 6000, 12000, 16000]

    @classmethod
    def process(cls, src_path, preset, out_path):
        """Process src_path MP3 with EQ preset, write WAV to out_path.
        Returns True on success."""
        if not SCIPY_AVAILABLE or not MUTAGEN_AVAILABLE:
            return False
        gains = cls.EQ_PRESETS.get(preset, [0]*8)
        if all(g == 0 for g in gains):
            return False   # flat — no processing needed
        try:
            import wave, struct, array
            # Decode MP3 → raw PCM via mutagen header + ctypes MCI trick
            # Use Windows MCI to convert to WAV first
            import ctypes, tempfile
            winmm2 = ctypes.WinDLL("winmm")
            buf    = ctypes.create_unicode_buffer(512)
            alias  = "eqtmp1"
            sp     = str(src_path).replace("\\", "/")
            r = winmm2.mciSendStringW(
                f'open "{sp}" type mpegvideo alias {alias}',
                buf, 512, 0)
            if r != 0:
                r = winmm2.mciSendStringW(
                    f'open "{sp}" alias {alias}',
                    buf, 512, 0)
            if r != 0:
                return False
            # Save as WAV
            raw_wav = out_path.replace(".wav", "_raw.wav")
            winmm2.mciSendStringW(
                f'set {alias} time format milliseconds', buf, 512, 0)
            winmm2.mciSendStringW(
                f'copy {alias} "{raw_wav}"', buf, 512, 0)
            winmm2.mciSendStringW(f'close {alias}', buf, 512, 0)

            # If MCI copy failed, try waveOutOpen approach via subprocess
            if not Path(raw_wav).exists():
                return False

            # Read WAV
            with wave.open(raw_wav, 'rb') as wf:
                n_ch    = wf.getnchannels()
                sampw   = wf.getsampwidth()
                rate    = wf.getframerate()
                frames  = wf.readframes(wf.getnframes())

            if sampw != 2:
                return False   # only handle 16-bit

            # Convert to float numpy array
            pcm = _np.frombuffer(frames, dtype=_np.int16).astype(_np.float32) / 32768.0
            if n_ch == 2:
                pcm = pcm.reshape(-1, 2)

            # Apply biquad peaking EQ filters per band
            for freq, gain_db in zip(cls.BAND_FREQS, gains):
                if abs(gain_db) < 0.1:
                    continue
                Q  = 1.4
                b, a = cls._peaking_eq(freq, gain_db, Q, rate)
                if n_ch == 2:
                    pcm[:, 0] = _sig.lfilter(b, a, pcm[:, 0])
                    pcm[:, 1] = _sig.lfilter(b, a, pcm[:, 1])
                else:
                    pcm = _sig.lfilter(b, a, pcm)

            # Soft clip + convert back to int16
            pcm = _np.tanh(pcm)   # gentle limiting
            pcm_int = (pcm * 32767).astype(_np.int16)
            out_bytes = pcm_int.tobytes()

            # Write processed WAV
            with wave.open(out_path, 'wb') as wf:
                wf.setnchannels(n_ch)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(out_bytes)

            try: Path(raw_wav).unlink()
            except: pass
            return True

        except Exception as ex:
            return False

    @staticmethod
    def _peaking_eq(freq, gain_db, Q, fs):
        """Compute biquad peaking EQ coefficients."""
        A  = 10 ** (gain_db / 40.0)
        w0 = 2 * _np.pi * freq / fs
        alpha = _np.sin(w0) / (2 * Q)
        b0 =  1 + alpha * A
        b1 = -2 * _np.cos(w0)
        b2 =  1 - alpha * A
        a0 =  1 + alpha / A
        a1 = -2 * _np.cos(w0)
        a2 =  1 - alpha / A
        return [b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0]


# ─────────────────────────────────────────
#  GLOBAL HOTKEY MANAGER  (Windows)
# ─────────────────────────────────────────
class GlobalHotkeys:
    """Register system-wide media key hotkeys via RegisterHotKey."""
    MOD_NOREPEAT = 0x4000
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_MEDIA_NEXT       = 0xB0
    VK_MEDIA_PREV       = 0xB1
    VK_MEDIA_STOP       = 0xB2
    WM_HOTKEY           = 0x0312

    def __init__(self, callbacks):
        """callbacks: dict of id -> callable, ids 1-4 for play/next/prev/stop"""
        self.callbacks = callbacks
        self._thread   = None
        self._active   = False

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
                    cb  = self.callbacks.get(hid)
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
        self.api_key     = api_key
        self.api_secret  = api_secret
        self.session_key = session_key
        self._enabled    = False
        self._current    = None     # (artist, title, start_ts)

    @property
    def ready(self):
        return bool(self.api_key and self.api_secret and self.session_key)

    def _sign(self, params):
        import hashlib
        keys = sorted(k for k in params if k != "format")
        raw  = "".join(k + params[k] for k in keys) + self.api_secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _call(self, params, post=False):
        params["api_key"] = self.api_key
        params["format"]  = "json"
        params["api_sig"] = self._sign(params)
        data = urllib.parse.urlencode(params).encode()
        try:
            if post:
                req = urllib.request.Request(self.ROOT, data=data)
            else:
                req = urllib.request.Request(
                    self.ROOT + "?" + urllib.parse.urlencode(params))
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
        if not self.ready: return
        params = {
            "method":   "track.updateNowPlaying",
            "artist":   artist,
            "track":    title,
            "sk":       self.session_key,
        }
        if album:    params["album"]    = album
        if duration: params["duration"] = str(int(duration))
        threading.Thread(target=lambda: self._call(params, post=True),
                         daemon=True).start()

    def scrobble(self, artist, title, album="", duration=0, timestamp=None):
        if not self.ready: return
        ts = str(int(timestamp or time.time()))
        params = {
            "method":    "track.scrobble",
            "artist":    artist,
            "track":     title,
            "timestamp": ts,
            "sk":        self.session_key,
        }
        if album:    params["album"]    = album
        if duration: params["duration"] = str(int(duration))
        threading.Thread(target=lambda: self._call(params, post=True),
                         daemon=True).start()

    def track_started(self, track):
        """Call when track begins playing."""
        self._current = (
            track.get("artist",""),
            track.get("title",""),
            track.get("album",""),
            track.get("duration", 0),
            time.time(),
        )
        self.now_playing(
            track.get("artist",""), track.get("title",""),
            track.get("album",""),  track.get("duration",0))

    def track_maybe_scrobble(self):
        """Call periodically — scrobbles when >50% played or >4 min."""
        if not self._current: return
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
        self._sock   = None
        self._active = False
        self._seq    = 0
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
        if not self._active: return
        try:
            now_ms  = int(time.time() * 1000)
            payload = {
                "cmd":   "SET_ACTIVITY",
                "args":  {
                    "pid": os.getpid(),
                    "activity": {
                        "details": title[:128],
                        "state":   f"by {artist}"[:128],
                        "assets":  {
                            "large_image": "oternos_logo",
                            "large_text":  "OTERNOS PLAYER",
                        },
                        "timestamps": {
                            "start": now_ms - int(elapsed_s * 1000),
                        },
                        "type": 2,   # Listening
                    }
                },
                "nonce": str(self._seq),
            }
            self._send(1, payload)
            self._recv()
        except Exception:
            self._active = False

    def clear(self):
        if not self._active: return
        try:
            self._send(1, {"cmd":"SET_ACTIVITY","args":{"pid":os.getpid(),"activity":{}},"nonce":str(self._seq)})
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
            if not header or len(header) < 8: return None
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
        self.on_new   = on_new
        self._paths   = set()
        self._thread  = None
        self._active  = False
        self._watched = []   # list of dirs

    def watch(self, directory):
        d = str(Path(directory).resolve())
        if d in self._watched: return
        self._watched.append(d)
        if not self._active:
            self._active = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._active  = False
        self._watched = []

    def _run(self):
        """Pure-Python polling fallback (no watchdog needed)."""
        seen = {}
        while self._active:
            for d in list(self._watched):
                try:
                    for f in Path(d).rglob("*"):
                        if f.suffix.lower() in self.AUDIO_EXT:
                            key   = str(f)
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
class AudioEngine:
    """
    Pygame-based audio engine — replaces the MCI backend which fails in
    PyInstaller exes due to MCI initialisation errors (error 277).
    Keeps exactly the same public API so no other code needs changing.
    """

    def __init__(self):
        self.current_track = None
        self.is_playing    = False
        self.is_paused     = False
        self.volume        = 0.7
        self.duration      = 0.0
        self._pos_cache    = 0.0
        self._play_start   = 0.0   # wall-clock time when play began
        self._seek_offset  = 0.0   # seconds already elapsed before current play
        self._mci_tmp      = None  # unused, kept for API compat

        # Initialise pygame mixer once
        try:
            import pygame
            if not pygame.get_init():
                pygame.init()
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            self._pygame = pygame
        except Exception as _e:
            self._pygame = None

    # ── internal ──────────────────────────
    def _v(self):
        return self.volume

    def _bg(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _get_dur(self, path):
        if MUTAGEN_AVAILABLE:
            try:
                from mutagen import File as _MFile
                f = _MFile(path)
                if f and f.info and hasattr(f.info, "length"):
                    return float(f.info.length)
            except Exception:
                pass
        return 0.0

    # ── public API ────────────────────────
    def load(self, path):
        import os as _os
        self.stop()
        if not self._pygame:
            return False
        if not _os.path.exists(str(path)):
            return False
        try:
            self._pygame.mixer.music.load(str(path))
            self.current_track = path
            self.duration      = self._get_dur(path)
            self._pos_cache    = 0.0
            self._seek_offset  = 0.0
            self._play_start   = 0.0
            self._open         = True
            return True
        except Exception as _e:
            self._last_error = str(_e)
            return False

    def play(self, start_ms=0):
        if not self._pygame or not self._open:
            return False
        try:
            self._seek_offset = start_ms / 1000.0
            self._pygame.mixer.music.play(start=self._seek_offset)
            self._pygame.mixer.music.set_volume(self.volume)
            self._play_start = time.time()
            self._pos_cache  = self._seek_offset
            self.is_playing  = True
            self.is_paused   = False
            return True
        except Exception as e:
            self._last_error = str(e)
            self.is_playing  = False
            self._open       = False
            return False

    def pause(self):
        if not self._pygame or not self.is_playing:
            return
        try:
            self._pos_cache = self.get_position()
            self._pygame.mixer.music.pause()
            self.is_playing = False
            self.is_paused  = True
        except Exception:
            pass

    def unpause(self):
        if not self._pygame or not self.is_paused:
            return
        try:
            paused_pos = self._pos_cache
            self._pygame.mixer.music.unpause()
            self._seek_offset = paused_pos - (self._pygame.mixer.music.get_pos() / 1000.0)
            self.is_playing  = True
            self.is_paused   = False
        except Exception:
            pass

    def stop(self):
        if not self._pygame:
            return
        try:
            self._pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_playing    = False
        self.is_paused     = False
        self._pos_cache    = 0.0
        self._open         = False

    def seek(self, pos_sec):
        if not self._pygame or not self._open:
            return
        was_playing = self.is_playing
        try:
            self._pygame.mixer.music.play(start=float(pos_sec))
            self._pygame.mixer.music.set_volume(self.volume)
            self._seek_offset = pos_sec
            self._play_start  = time.time()
            self._pos_cache   = pos_sec
            self.is_playing   = True
            self.is_paused    = False
            if not was_playing:
                self._pygame.mixer.music.pause()
                self.is_playing = False
                self.is_paused  = True
        except Exception:
            pass

    def get_position(self):
        if not self._pygame:
            return self._pos_cache
        if self.is_playing:
            try:
                ms = self._pygame.mixer.music.get_pos()
                if ms >= 0:
                    self._pos_cache = self._seek_offset + ms / 1000.0
            except Exception:
                pass
        return self._pos_cache

    def set_volume(self, vol):
        self.volume = max(0.0, min(1.0, vol / 100.0 if vol > 1 else vol))
        if self._pygame:
            try:
                self._pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def is_done(self):
        if not self._pygame or not self.is_playing:
            return False
        if time.time() - self._play_start < 0.5:
            return False
        try:
            return not self._pygame.mixer.music.get_busy()
        except Exception:
            return False

    def get_metadata(self, path):
        m = {"title": Path(path).stem, "artist": "Unknown", "album": "Unknown"}
        if not MUTAGEN_AVAILABLE:
            return m
        try:
            from mutagen import File as _MF
            f = _MF(path)
            if f is None:
                return m
            tags = f.tags or {}
            def _get(keys, default):
                for k in keys:
                    v = tags.get(k)
                    if v:
                        return str(v[0]) if isinstance(v, list) else str(v)
                return default
            if hasattr(f, "tags") and f.tags and hasattr(f.tags, "getall"):
                t = f.tags
                def _id3(k, d):
                    v = t.get(k)
                    return str(v) if v else d
                m["title"]  = _id3("TIT2", m["title"])
                m["artist"] = _id3("TPE1", m["artist"])
                m["album"]  = _id3("TALB", m["album"])
            else:
                m["title"]  = _get(["title",  "TITLE"],  m["title"])
                m["artist"] = _get(["artist", "ARTIST", "albumartist"], m["artist"])
                m["album"]  = _get(["album",  "ALBUM"],  m["album"])
        except Exception:
            pass
        return m

    # kept for API compat with old MCI code
    _open = False
    def _ensure_time_fmt(self): pass
    def _bg_vol(self): pass

# ─────────────────────────────────────────
#  WAVEFORM VISUALIZER
# ─────────────────────────────────────────
class WaveVisualizer(tk.Canvas):
    def __init__(self, parent, **kw):
        # Match the panel background so there's no hard box edge
        super().__init__(parent, bg=C["panel"], highlightthickness=0, **kw)
        self.bars   = 48
        self.phases = [random.uniform(0, math.pi*2) for _ in range(self.bars)]
        self.speeds = [random.uniform(0.03, 0.09)   for _ in range(self.bars)]
        self.t      = 0
        self.active = False
        self._draw()

    def set_active(self, v):
        self.active = v

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 1 and h > 1:
            bw = w / self.bars
            # Derive panel background brightness from current theme
            try:
                ph = C["panel"].lstrip("#")
                PBG = int(ph[0:2], 16)
            except Exception:
                PBG = 17
            for i in range(self.bars):
                # Edge fade: bars near the sides fade toward the panel bg colour
                edge = abs(i - self.bars / 2) / (self.bars / 2)  # 0=center, 1=edge
                edge_fade = 1.0 - edge ** 1.6  # softer roll-off

                if self.active:
                    amp = (math.sin(self.t * self.speeds[i]*10 + self.phases[i])*0.5+0.5)**1.5
                    amp = max(0.04, amp)
                    # Active: bright center bars, fade to panel at edges
                    peak = int(200 * edge_fade + 30)
                    br = int(PBG + (peak - PBG) * amp * edge_fade)
                else:
                    amp = 0.03 + 0.015 * math.sin(self.t * 0.5 + i * 0.3)
                    # Idle: very subtle, barely above panel colour
                    peak = int(48 * edge_fade + PBG)
                    br = int(PBG + (peak - PBG) * amp * 18)

                br = max(PBG, min(255, br))
                bh = amp * h * 0.80
                x1, x2 = i*bw+1, i*bw+bw-2
                y1, y2 = (h-bh)/2, (h+bh)/2
                self.create_rectangle(x1, y1, x2, y2,
                                      fill=f"#{br:02x}{br:02x}{br:02x}", outline="")
        self.t += 1
        self.after(30 if HW_ACCEL else 120, self._draw)


# ─────────────────────────────────────────
#  OTERNOS LOGO  — Arasaka-style hex emblem
# ─────────────────────────────────────────
class OternosLogo(tk.Canvas):
    """
    Layered cyberpunk hex emblem:
      • Outer hex ring with angular notch cuts at each vertex
      • Mid hex — slightly smaller, counter-rotates slowly
      • Six sharp spike fins radiating outward at each vertex
      • Inner O ring with 12 tick marks around it
      • Centre dot
    Animates: slow idle drift, pulses when is_playing=True.
    """
    def __init__(self, parent, size=54, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self.size      = size
        self._bg       = bg
        self.t         = 0
        self.is_playing = False
        self._draw()

    # ── helpers ──────────────────────────
    def _hex_pts(self, cx, cy, r, rot, flat=False):
        pts = []
        offset = math.pi / 6 if flat else 0
        for i in range(6):
            a = i / 6 * math.pi * 2 + rot + offset
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    def _notched_hex(self, cx, cy, r, rot, notch=0.13):
        """Hex with small angular notches cut inward at each vertex."""
        pts = []
        for i in range(6):
            a0 = i / 6 * math.pi * 2 + rot
            a1 = (i + 1) / 6 * math.pi * 2 + rot
            # approach vertex from previous edge
            pts += [cx + r * math.cos(a0 - notch), cy + r * math.sin(a0 - notch)]
            # notch dip inward
            pts += [cx + r * 0.88 * math.cos(a0),  cy + r * 0.88 * math.sin(a0)]
            # leave vertex toward next edge
            pts += [cx + r * math.cos(a0 + notch), cy + r * math.sin(a0 + notch)]
        return pts

    def _draw(self):
        try:
            self.delete("all")
            S  = self.size
            cx, cy = S / 2, S / 2
            R  = S * 0.46
            t  = self.t
            pl = self.is_playing

            pulse = (math.sin(t * 0.07) * 0.5 + 0.5) if pl else 0.0
            hi    = min(255, int(190 + pulse * 65))
            mid   = min(255, int(95  + pulse * 55))
            dim   = min(255, int(42  + pulse * 20))
            hc    = f"#{hi:02x}{hi:02x}{hi:02x}"
            mc    = f"#{mid:02x}{mid:02x}{mid:02x}"
            dc    = f"#{dim:02x}{dim:02x}{dim:02x}"
            rot_outer = t * 0.006
            rot_mid   = -t * 0.009 + math.pi / 6

            pad = R * 0.06
            self.create_oval(cx-R-pad, cy-R-pad, cx+R+pad, cy+R+pad,
                             fill=C["bg"], outline="")

            for i in range(6):
                a  = i / 6 * math.pi * 2 + rot_outer
                bw = math.pi / 18
                tx = cx + R * math.cos(a);          ty = cy + R * math.sin(a)
                lx = cx + R*0.68*math.cos(a-bw);    ly = cy + R*0.68*math.sin(a-bw)
                rx = cx + R*0.68*math.cos(a+bw);    ry = cy + R*0.68*math.sin(a+bw)
                self.create_polygon(lx,ly,tx,ty,rx,ry, fill=mc, outline="")

            op_flat = self._notched_hex(cx, cy, R*0.92, rot_outer, notch=0.18)
            self.create_polygon(op_flat, outline=hc, fill="", width=2)

            mp_flat = [c for pt in self._hex_pts(cx, cy, R*0.70, rot_mid) for c in pt]
            self.create_polygon(mp_flat, outline=mc, fill="", width=1)

            for i in range(6):
                a  = i/6*math.pi*2 + rot_outer + math.pi/6
                self.create_line(cx+R*0.74*math.cos(a), cy+R*0.74*math.sin(a),
                                 cx+R*0.62*math.cos(a), cy+R*0.62*math.sin(a),
                                 fill=dc, width=1)

            rO = R * 0.42;  rOi = R * 0.28
            self.create_oval(cx-rO, cy-rO, cx+rO, cy+rO, outline=hc, fill="", width=2)
            self.create_oval(cx-rOi, cy-rOi, cx+rOi, cy+rOi, outline=dc, fill="", width=1)

            for i in range(12):
                a    = i/12*math.pi*2 + rot_outer*0.4
                long = (i % 3 == 0)
                r2   = rO * (0.78 if long else 0.87)
                self.create_line(cx+rO*math.cos(a), cy+rO*math.sin(a),
                                 cx+r2*math.cos(a), cy+r2*math.sin(a),
                                 fill=(mc if long else dc), width=(2 if long else 1))

            cr = 2 + pulse * 2
            self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr, fill=hc, outline="")
        except Exception:
            pass
        self.t += 1
        self.after(30 if HW_ACCEL else 150, self._draw)


# keep old name as alias so sidebar still works
GeoAccent = OternosLogo


# ─────────────────────────────────────────
#  MIKU LOGO — proper twin-tail silhouette
# ─────────────────────────────────────────
class MikuLogo(tk.Canvas):
    """
    Animated Miku emblem:
      • Head silhouette with twin ponytail bases
      • Two long flowing twin-tails that sway independently
      • ♪ note at centre of head
      • Soft teal glow halo, pink pulse ring when playing
      • Tiny floating sparkles ✦ around the emblem
    """
    def __init__(self, parent, size=54, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self.size = size
        self._bg  = bg
        self.t    = 0
        self.is_playing = False
        # Sparkle positions: (angle_offset, radius_frac, speed, phase)
        self._sparkles = [
            (i * math.pi * 2 / 6, 0.44 + (i % 2) * 0.06,
             0.012 + i * 0.003, i * 1.1)
            for i in range(6)
        ]
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            S  = self.size
            cx = S / 2
            t  = self.t
            pl = self.is_playing
            pulse  = (math.sin(t * 0.07) * 0.5 + 0.5) if pl else 0.15
            sway_l = math.sin(t * 0.038) * 0.22
            sway_r = math.sin(t * 0.031 + 0.8) * 0.20

            # ── outer glow halo ──
            hr  = S * 0.46
            cy  = S * 0.50
            if pl:
                gv = int(30 + pulse * 50)
                self.create_oval(cx-hr-2, cy-hr-2, cx+hr+2, cy+hr+2,
                                 outline=f"#0a{gv+10:02x}{gv:02x}", fill="", width=3)
            self.create_oval(cx-hr, cy-hr, cx+hr, cy+hr,
                             outline="#0d4a5e", fill="", width=1)

            # ── twin-tail LEFT (flows down-left, brighter teal) ──
            tail_base_lx = cx - S * 0.20
            tail_base_ly = S * 0.30
            pts_l = []
            for i in range(28):
                frac  = i / 27
                # curve: starts near head, sweeps left and down
                angle = math.pi * (0.70 + frac * 0.75) + sway_l * (frac ** 0.6)
                r     = S * (0.04 + frac * 0.42)
                px    = tail_base_lx + r * math.cos(angle)
                py    = tail_base_ly + r * math.sin(angle) * 1.1
                pts_l.extend([px, py])
            if len(pts_l) >= 4:
                # draw thick base tapering to thin tip — two passes
                self.create_line(pts_l, fill="#1e8a84", width=4,
                                 smooth=True, capstyle="round")
                self.create_line(pts_l, fill="#39c5bb", width=2,
                                 smooth=True, capstyle="round")

            # ── twin-tail RIGHT (flows down-right, slightly lighter) ──
            tail_base_rx = cx + S * 0.20
            tail_base_ry = S * 0.28
            pts_r = []
            for i in range(28):
                frac  = i / 27
                angle = math.pi * (0.30 - frac * 0.75) + sway_r * (frac ** 0.6)
                r     = S * (0.04 + frac * 0.40)
                px    = tail_base_rx + r * math.cos(angle)
                py    = tail_base_ry + r * math.sin(angle) * 1.1
                pts_r.extend([px, py])
            if len(pts_r) >= 4:
                self.create_line(pts_r, fill="#1e8a84", width=4,
                                 smooth=True, capstyle="round")
                self.create_line(pts_r, fill="#4dd8d0", width=2,
                                 smooth=True, capstyle="round")

            # ── head silhouette (small rounded oval) ──
            hy  = S * 0.34
            hrx = S * 0.17
            hry = S * 0.15
            head_fill = "#071a28" if not pl else f"#07{int(0x1a+pulse*8):02x}{int(0x28+pulse*10):02x}"
            self.create_oval(cx-hrx, hy-hry, cx+hrx, hy+hry,
                             fill=head_fill, outline="#39c5bb", width=1)

            # ── twin-tail bun circles at top of head ──
            bun_r = S * 0.055
            for bx in (cx - S*0.13, cx + S*0.13):
                self.create_oval(bx-bun_r, hy-hry-bun_r*0.6,
                                 bx+bun_r, hy-hry+bun_r*0.8,
                                 fill="#0a2535", outline="#39c5bb", width=1)

            # ── ♪ note inside head ──
            note_br = int(180 + pulse * 75) if pl else 130
            note_br = min(255, note_br)
            note_col = f"#{note_br:02x}{min(255,note_br+40):02x}{min(255,note_br+38):02x}"
            self.create_text(cx, hy + S*0.01, text="♪",
                             font=("Consolas", max(6, int(S*0.18))),
                             fill=note_col, anchor="center")

            # ── floating sparkles ✦ ──
            for a_off, r_frac, spd, phase in self._sparkles:
                angle = a_off + t * spd + phase
                r     = S * r_frac
                sx    = cx + r * math.cos(angle)
                sy    = S*0.50 + r * math.sin(angle) * 0.85
                spark_v = (math.sin(t * spd * 3 + phase) * 0.5 + 0.5)
                # alternate teal and pink sparkles
                if int(phase) % 2 == 0:
                    sv = int(20 + spark_v * 57)
                    sc = f"#{sv:02x}{min(255,sv*4+30):02x}{min(255,sv*4+25):02x}"
                else:
                    sv = int(20 + spark_v * 60)
                    sc = f"#{min(255,sv*4+50):02x}{sv:02x}{min(255,sv*3+40):02x}"
                self.create_text(sx, sy, text="✦",
                                 font=("Consolas", max(5, int(S*0.10))),
                                 fill=sc, anchor="center")

            # ── pink pulse ring when playing ──
            if pl:
                pr  = S * (0.46 + pulse * 0.04)
                pv  = int(40 + pulse * 80)
                self.create_oval(cx-pr, cy-pr, cx+pr, cy+pr,
                                 outline=f"#{min(255,pv+160):02x}{pv//3:02x}{min(255,pv+100):02x}",
                                 fill="", width=1)

        except Exception:
            pass
        self.t += 1
        self.after(28 if HW_ACCEL else 150, self._draw)


# ─────────────────────────────────────────
#  MIKU CORNER DECO — sakura petals + stars
# ─────────────────────────────────────────
class MikuCornerDeco(tk.Canvas):
    """
    Animated corner deco for Miku theme:
      • Soft rounded sakura-petal corners in teal/pink
      • A tiny spinning ♫ or ✦ at each corner tip
      • Gentle twinkle animation
    """
    def __init__(self, parent, size=28, bg=None, **kw):
        bg = bg or "#03080f"
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._bg  = bg
        self.size = size
        self.t    = 0
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            S     = self.size
            t     = self.t
            pulse = (math.sin(t * 0.055) * 0.5 + 0.5)
            p2    = (math.sin(t * 0.040 + 1.2) * 0.5 + 0.5)

            tv = int(25 + pulse * 52)
            pv = int(20 + p2    * 55)
            teal = f"#{tv:02x}{min(255,tv*4+10):02x}{min(255,tv*4+5):02x}"
            pink = f"#{min(255,pv*3+80):02x}{pv//2:02x}{min(255,pv*2+60):02x}"

            M = 2
            L = int(S * 0.40)

            # ── rounded corner arcs (two lines per corner with curved feel) ──
            #    teal: top-left, bottom-right  |  pink: top-right, bottom-left
            def _corner(ox, oy, dx, dy, col):
                # main arm
                self.create_line(ox, oy, ox + dx*L, oy,        fill=col, width=2, capstyle="round")
                self.create_line(ox, oy, ox,        oy + dy*L, fill=col, width=2, capstyle="round")
                # inner accent line (shorter, dimmer)
                dim = _dim(col, 0.45)
                self.create_line(ox + dx*2, oy + dy*2,
                                 ox + dx*(L-2), oy + dy*2,    fill=dim, width=1)
                self.create_line(ox + dx*2, oy + dy*2,
                                 ox + dx*2, oy + dy*(L-2),    fill=dim, width=1)

            def _dim(hexcol, factor):
                r,g,b = int(hexcol[1:3],16), int(hexcol[3:5],16), int(hexcol[5:7],16)
                return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

            _corner(M,   M,   +1, +1, teal)
            _corner(S-M, M,   -1, +1, pink)
            _corner(M,   S-M, +1, -1, pink)
            _corner(S-M, S-M, -1, -1, teal)

            # ── centre: alternating ♪ / ✦ that fades in/out ──
            sym   = "♪" if (t // 40) % 2 == 0 else "✦"
            sym_v = int(15 + pulse * 45)
            sym_c = f"#{sym_v:02x}{min(255,sym_v*4):02x}{min(255,sym_v*4-3):02x}"
            self.create_text(S//2, S//2, text=sym,
                             font=("Consolas", max(5, S//4)),
                             fill=sym_c, anchor="center")

        except Exception:
            pass
        self.t += 1
        self.after(38 if HW_ACCEL else 200, self._draw)


# ─────────────────────────────────────────
#  MIKU DATA TICKER — notes, JP, lyrics snippets
# ─────────────────────────────────────────
class MikuTicker(tk.Canvas):
    """
    Scrolling Miku ticker:
      • Music notes (♪ ♫ ♩ ♬) and Vocaloid JP characters
      • Short lyric/phrase fragments
      • Alternating teal and pink coloring per token
      • Occasional ✦ sparkle bursts
    """
    # Tokens: notes, JP chars, short phrases
    _TOKENS = [
        "♪", "♫", "♩", "♬", "✦", "✧",
        "ミ", "ク", "初", "音", "歌", "声", "楽", "夢",
        "MIKU", "VOCA", "39♪", "歌声", "音楽",
        "♪ ♫", "✦ ✦",
    ]

    def __init__(self, parent, width=200, height=12, bg=None, **kw):
        bg = bg or "#071520"
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._width  = width
        self._height = height
        self.t       = 0
        self._scroll = 0.0
        self._data   = self._gen()  # list of (token, color_mode) tuples
        self._draw()

    def _gen(self):
        import random
        result = []
        for _ in range(self._width // 18 + 8):
            tok   = random.choice(self._TOKENS)
            mode  = random.choice(("teal", "pink", "dim"))
            result.append((tok, mode))
        return result

    def _draw(self):
        try:
            self.delete("all")
            import random
            self.t       += 1
            self._scroll += 0.28
            step = 18
            if self._scroll >= step:
                self._scroll -= step
                self._data.pop(0)
                tok  = random.choice(self._TOKENS)
                mode = random.choice(("teal", "pink", "dim"))
                self._data.append((tok, mode))
            if self.t % 10 == 0:
                idx  = random.randint(0, len(self._data)-1)
                tok  = random.choice(self._TOKENS)
                mode = random.choice(("teal", "pink", "dim"))
                self._data[idx] = (tok, mode)

            t = self.t
            off = -self._scroll
            for i, (tok, mode) in enumerate(self._data):
                x = off + i * step
                if x > self._width: break
                fade = max(0.0, min(1.0, x / max(1, self._width * 0.15)))
                flicker = (math.sin(t * 0.08 + i * 0.7) * 0.5 + 0.5)
                if mode == "teal":
                    v = int((18 + fade * 38) * (0.6 + flicker * 0.4))
                    col = f"#{v:02x}{min(255,v*4+10):02x}{min(255,v*4+5):02x}"
                elif mode == "pink":
                    v = int((15 + fade * 35) * (0.6 + flicker * 0.4))
                    col = f"#{min(255,v*3+50):02x}{v//2:02x}{min(255,v*2+40):02x}"
                else:
                    v = int(12 + fade * 22)
                    col = f"#{v:02x}{min(255,v+18):02x}{min(255,v+16):02x}"
                self.create_text(x + 2, self._height // 2, text=tok,
                    font=("Consolas", 6), fill=col, anchor="w")
        except Exception:
            pass
        self.after(48 if HW_ACCEL else 999, self._draw)


class CornerBrackets(tk.Canvas):
    """
    Animated corner bracket decoration.
    Draws L-shaped corner marks that pulse and occasionally glitch.
    """
    def __init__(self, parent, size=60, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._bg  = bg
        self.size = size
        self.t    = 0
        self._glitch_t = 0
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            S = self.size
            t = self.t
            L = int(S * 0.35)   # bracket arm length
            W = 2               # line width
            M = 3               # margin from edge
            pulse = (math.sin(t * 0.05) * 0.5 + 0.5)
            base = int(38 + pulse * 28)
            col  = f"#{base:02x}{base:02x}{base:02x}"
            # Glitch: occasionally offset one corner
            gx, gy = 0, 0
            if self.t % 47 < 3:
                gx = (self.t % 3) - 1
                gy = (self.t % 2)
            # Top-left
            self.create_line(M,       M,       M+L,     M,       fill=col, width=W)
            self.create_line(M,       M,       M,       M+L,     fill=col, width=W)
            # Top-right
            self.create_line(S-M,     M+gx,    S-M-L,   M+gx,    fill=col, width=W)
            self.create_line(S-M,     M+gx,    S-M,     M+L+gx,  fill=col, width=W)
            # Bottom-left
            self.create_line(M+gy,    S-M,     M+L+gy,  S-M,     fill=col, width=W)
            self.create_line(M+gy,    S-M,     M+gy,    S-M-L,   fill=col, width=W)
            # Bottom-right
            self.create_line(S-M,     S-M,     S-M-L,   S-M,     fill=col, width=W)
            self.create_line(S-M,     S-M,     S-M,     S-M-L,   fill=col, width=W)
            # Centre crosshair — faint
            cx_col = f"#{int(base*0.4):02x}{int(base*0.4):02x}{int(base*0.4):02x}"
            cx = S // 2
            cy = S // 2
            self.create_line(cx-4, cy, cx+4, cy, fill=cx_col, width=1)
            self.create_line(cx, cy-4, cx, cy+4, fill=cx_col, width=1)
        except Exception:
            pass
        self.t += 1
        self.after(40 if HW_ACCEL else 200, self._draw)


class DataTicker(tk.Canvas):
    """
    Scrolling hex data ticker strip — Signalis-style ambient UI decoration.
    Renders a horizontal strip of slowly scrolling fake hex/binary values.
    """
    _CHARS = "0123456789ABCDEF"
    def __init__(self, parent, width=200, height=14, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._width  = width
        self._height = height
        self.t       = 0
        self._cols   = max(1, width // 22)
        self._data   = self._gen()
        self._scroll = 0.0
        self._draw()

    def _gen(self):
        import random
        return [
            f"{random.randint(0,0xFFFF):04X}"
            for _ in range(self._cols + 4)
        ]

    def _draw(self):
        try:
            self.delete("all")
            import random
            self.t += 1
            self._scroll += 0.18
            if self._scroll >= 22:
                self._scroll -= 22
                self._data.pop(0)
                self._data.append(f"{random.randint(0,0xFFFF):04X}")
            # Occasionally mutate a cell
            if self.t % 8 == 0:
                idx = random.randint(0, len(self._data)-1)
                self._data[idx] = f"{random.randint(0,0xFFFF):04X}"
            off = -self._scroll
            for i, val in enumerate(self._data):
                x = off + i * 22
                if x > self._width: break
                fade = max(0, min(1, (x / max(1, self._width))))
                brightness = int(22 + fade * 20)
                col = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
                self.create_text(x + 2, self._height // 2, text=val,
                    font=("Courier New", 6), fill=col, anchor="w")
        except Exception:
            pass
        self.after(60 if HW_ACCEL else 999, self._draw)


# ─────────────────────────────────────────
#  PLAYLIST MOSAIC ART GENERATOR
# ─────────────────────────────────────────
class MosaicArt:
    """Generates a 2×2 mosaic thumbnail from up to 4 album art images."""

    @staticmethod
    def from_tracks(tracks, size=64):
        """Return a PhotoImage mosaic from a list of track dicts (need 'art_url' or 'path')."""
        try:
            from PIL import Image as PILImage
        except ImportError:
            return MosaicArt._placeholder(size)

        imgs = []
        seen_paths = set()
        for t in tracks:
            if len(imgs) >= 4:
                break
            src = t.get("art_path") or t.get("path", "")
            if src and src not in seen_paths:
                seen_paths.add(src)
                try:
                    img = MosaicArt._extract_art(src, size // 2)
                    if img:
                        imgs.append(img)
                except Exception:
                    pass

        if not imgs:
            return MosaicArt._placeholder(size)

        canvas = PILImage.new("RGB", (size, size), (17, 17, 17))
        half = size // 2
        positions = [(0, 0), (half, 0), (0, half), (half, half)]
        for i, pos in enumerate(positions):
            img = imgs[i % len(imgs)].resize((half, half), PILImage.LANCZOS)
            canvas.paste(img, pos)

        import io
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        import base64
        b64 = base64.b64encode(buf.read()).decode()
        return tk.PhotoImage(data=b64)

    @staticmethod
    def _extract_art(path, size):
        """Try to extract embedded album art from an audio file."""
        try:
            from PIL import Image as PILImage
            import io
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3
                tags = ID3(path)
                for tag in tags.values():
                    if hasattr(tag, "data"):
                        return PILImage.open(io.BytesIO(tag.data)).convert("RGB")
            except Exception:
                pass
        except ImportError:
            pass
        return None

    @staticmethod
    def _placeholder(size):
        """Return a simple dark placeholder PhotoImage."""
        data = f"P6\n{size} {size}\n255\n" + bytes([17, 17, 17] * size * size)
        try:
            import tempfile, os
            f = tempfile.NamedTemporaryFile(suffix=".ppm", delete=False)
            f.write(f"P6\n{size} {size}\n255\n".encode())
            f.write(bytes([17, 17, 17] * size * size))
            f.close()
            img = tk.PhotoImage(file=f.name)
            os.unlink(f.name)
            return img
        except Exception:
            return None


# ─────────────────────────────────────────
#  TRACK RECOMMENDER
# ─────────────────────────────────────────
class TrackRecommender:
    """Simple content-based recommender using listening history + metadata similarity."""

    def __init__(self, library, history):
        self.library = library
        self.history = history  # list of {title, artist, album, ts}

    def recommend(self, n=20):
        """Return list of library indices scored by similarity to recent listening."""
        if not self.history or not self.library:
            return list(range(min(n, len(self.library))))

        # Build frequency map of artists/albums from recent 50 plays
        from collections import Counter
        recent = self.history[-50:]
        artists = Counter(e.get("artist","").lower() for e in recent)
        albums  = Counter(e.get("album","").lower()  for e in recent)
        played  = {(e.get("artist","").lower(), e.get("title","").lower())
                   for e in recent}

        scores = []
        for i, t in enumerate(self.library):
            a  = t.get("artist","").lower()
            al = t.get("album","").lower()
            ti = t.get("title","").lower()
            # Skip recently played
            if (a, ti) in played:
                continue
            score = artists.get(a, 0) * 3 + albums.get(al, 0) * 1.5
            scores.append((score, i))

        scores.sort(key=lambda x: -x[0])
        # Mix top-scored with some random discovery
        top    = [i for _, i in scores[:n*2]]
        result = top[:n//2]
        if len(top) > n//2:
            result += random.sample(top[n//2:], min(n//2, len(top)-n//2))
        if len(result) < n:
            # Pad with random unplayed tracks
            remaining = [i for i in range(len(self.library))
                         if i not in result and
                         (self.library[i].get("artist","").lower(),
                          self.library[i].get("title","").lower()) not in played]
            random.shuffle(remaining)
            result += remaining[:n - len(result)]
        return result[:n]


# ─────────────────────────────────────────
#  NORMALIZATION METER
# ─────────────────────────────────────────
class NormMeter:
    """Real-time RMS loudness meter drawn as a segmented bar."""

    def __init__(self, parent, width=180, height=8):
        self.cv     = tk.Canvas(parent, bg=C["panel"], width=width, height=height,
                                highlightthickness=0)
        self._w     = width
        self._h     = height
        self._rms   = 0.0   # 0.0 – 1.0
        self._peak  = 0.0
        self._peak_hold = 0
        self._draw()

    def pack(self, **kw):
        self.cv.pack(**kw)

    def update(self, rms, peak=None):
        self._rms = min(1.0, max(0.0, rms))
        if peak is not None:
            if peak >= self._peak:
                self._peak = min(1.0, peak)
                self._peak_hold = 30
            else:
                if self._peak_hold > 0:
                    self._peak_hold -= 1
                else:
                    self._peak -= 0.008
                    self._peak = max(0.0, self._peak)
        self._draw()

    def _draw(self):
        self.cv.delete("all")
        w, h = self._w, self._h
        segs  = 24
        gap   = 2
        sw    = (w - gap * (segs - 1)) / segs
        fill  = self._rms * segs
        for i in range(segs):
            x0 = i * (sw + gap)
            x1 = x0 + sw
            lit = i < fill
            # Color zones: green → yellow → red
            frac = i / segs
            if frac < 0.6:
                col = C["white3"] if not lit else C["white2"]
            elif frac < 0.85:
                col = "#404040" if not lit else C["white"]
            else:
                col = "#333333" if not lit else C["glow"]
            self.cv.create_rectangle(x0, 0, x1, h, fill=col, outline="")
        # Peak marker
        if self._peak > 0:
            px = int(self._peak * w)
            self.cv.create_line(px, 0, px, h, fill=C["glow"], width=1)


# ─────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────
class VoidPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("OTERNOS PLAYER  //  v1.1")
        self.root.configure(bg=C["bg"])
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        # Set taskbar / window icon
        try:
            import base64, tempfile
            _ico_data = base64.b64decode(_ICON_B64)
            _ico_tmp  = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            _ico_tmp.write(_ico_data); _ico_tmp.close()
            _ico_img  = tk.PhotoImage(file=_ico_tmp.name)
            self.root.iconphoto(True, _ico_img)
            self._icon_img = _ico_img  # prevent GC
        except Exception:
            pass

        self.engine   = AudioEngine()
        self.library  = []
        self.playlists = {}
        self.queue     = []
        self.queue_pos = -1
        self.current_idx     = -1
        self._skip_counts    = {}
        self._flow_mode      = False
        self._smart_skip_on  = False
        self._voice_on       = False
        self._ambient_win    = None
        self._lyric_ticker_job = None
        self.shuffle         = False
        self.repeat_mode     = "off"
        self.seeking         = False
        self.active_playlist = None
        self.view            = "library"
        self._display_indices = []
        self._dx = self._dy = 0

        # Spotify
        self.sp_auth    = SpotifyAuth()
        self.sp_api     = SpotifyAPI(self.sp_auth)
        self._sp_tracks = []   # current spotify track list shown
        self._sp_view   = "home"  # home | liked | playlist | search

        self._sp_mode    = False   # True when Spotify is the active audio source
        self._active_source = "none"   # "spotify" | "youtube" | "soundcloud" | "library" | "none"
        self._sp_pos_ms  = 0
        self._sp_dur_ms  = 0
        self._sp_playing = False

        # SoundCloud
        self.sc_api         = SoundCloudAPI()
        self._sc_tracks     = []
        self._sc_view       = "search"   # search | likes | favorites
        self._sc_favorites  = []         # list of saved track dicts

        # YouTube
        self.yt_api         = YouTubeAPI()
        self._yt_tracks     = []
        self._yt_view       = "search"   # search only

        # Sleep timer
        self._sleep_minutes  = 0
        self._sleep_end_time = None
        self._sleep_job      = None

        # Mini player
        self._mini_win = None

        # Lyrics
        self._lyrics_cache       = {}   # key -> plain text string
        self._synced_cache       = {}   # key -> [(ms, line), ...]
        self._lyrics_job         = None
        self._lyrics_sync_job    = None
        self._lyrics_lines       = []   # current list of (ms, line_label_widget)
        self._lyrics_active_line = -1

        # Recently played history  (loaded from disk below)
        self._history     = []
        self._history_max = 200

        # Last.fm scrobbler (credentials loaded after _load_data)
        self._scrobbler    = None
        self._scrobble_job = None

        # Discord RPC
        self._discord         = DiscordRPC()
        self._discord_enabled = False

        # Folder watcher
        self._watcher = FolderWatcher(self._on_watcher_new_file)

        # Crossfade
        self._xfade_job    = None
        self._xfade_active = False

        # Playback speed
        self._playback_speed = 1.0

        # A-B loop
        self._ab_a   = None   # seconds
        self._ab_b   = None
        self._ab_active = False

        # Bookmarks  {lib_idx: [(seconds, label), ...]}
        self._bookmarks = {}

        # BPM / mood analysis caches
        self._bpm_cache  = {}   # path -> bpm float
        self._mood_cache = {}   # path -> mood string

        # Album art dedup
        self._art_url_last = None

        # Normalization meter state
        self._norm_rms  = 0.0
        self._norm_peak = 0.0

        # Command palette
        self._palette_win = None

        # Theme editor
        self._theme_presets = {
            "VOID":     {"bg":"#050505","panel":"#0c0c0c","border":"#1f1f1f","border2":"#2e2e2e",
                         "white":"#e8e8e8","white2":"#9a9a9a","white3":"#424242",
                         "glow":"#ffffff","select":"#1e1e1e","select2":"#242424","red":"#cc2222"},
            "CRIMSON":  {"bg":"#0d0508","panel":"#160a0c","border":"#3a1520","border2":"#502030",
                         "white":"#f0d0d8","white2":"#b07080","white3":"#603040",
                         "glow":"#e05070","select":"#1a0810","select2":"#220c14","red":"#e05070"},
            "EMERALD":  {"bg":"#050d08","panel":"#0a1610","border":"#153025","border2":"#1e4030",
                         "white":"#d0f0e0","white2":"#70b090","white3":"#305040",
                         "glow":"#40c070","select":"#081408","select2":"#0c1c10","red":"#c04040"},
            "COBALT":   {"bg":"#05080d","panel":"#0a1020","border":"#152540","border2":"#1e3558",
                         "white":"#c8d8f8","white2":"#6890c0","white3":"#2a4060",
                         "glow":"#4080e0","select":"#080c18","select2":"#0c1220","red":"#c04040"},
            "AMBER":    {"bg":"#0d0a05","panel":"#161208","border":"#352808","border2":"#4a380a",
                         "white":"#f8e8c0","white2":"#c0a060","white3":"#604820",
                         "glow":"#d0a030","select":"#181008","select2":"#20160a","red":"#c04030"},
            "VIOLET":   {"bg":"#0a0510","panel":"#120a18","border":"#251040","border2":"#341858",
                         "white":"#e0d0f8","white2":"#9070c0","white3":"#402860",
                         "glow":"#9060d0","select":"#0e0818","select2":"#160c20","red":"#c04080"},
            "GHOST":    {"bg":"#f8f8f8","panel":"#eeeeee","border":"#cccccc","border2":"#bbbbbb",
                         "white":"#111111","white2":"#444444","white3":"#999999",
                         "glow":"#000000","select":"#e8e8e8","select2":"#e0e0e0","red":"#cc2222"},
            "MILITARY": {"bg":"#080c06","panel":"#0e1209","border":"#1a2210","border2":"#243016",
                         "white":"#c8d4a0","white2":"#7a9050","white3":"#3a4820",
                         "glow":"#a0c040","select":"#0c1008","select2":"#101408","red":"#c06020"},
            "MIKU":     {"bg":"#03080f","panel":"#071520","border":"#0a3040","border2":"#0d4a5e",
                         "white":"#cff8f4","white2":"#5ecfca","white3":"#1e6068",
                         "glow":"#39c5bb","select":"#071a24","select2":"#0c2535","red":"#ff6eb4"},
            "NERV":     {"bg":"#000000","panel":"#0a0000","border":"#3a0000","border2":"#550000",
                         "white":"#f0f0f0","white2":"#cc0000","white3":"#660000",
                         "glow":"#ff0000","select":"#140000","select2":"#1e0000","red":"#ff0000"},
        }

        self._load_data()

        # Init scrobbler with loaded credentials
        self._scrobbler = LastFmScrobbler(
            api_key    = self.settings.get("lastfm_api_key",    ""),
            api_secret = self.settings.get("lastfm_api_secret", ""),
            session_key= self.settings.get("lastfm_session_key",""),
        )

        self._build_ui()
        self._poll()
        self._start_audio_capture()
        self._apply_settings()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Discord RPC — delay so it doesn't slow startup
        self.root.after(3000, lambda: threading.Thread(target=self._discord_connect, daemon=True).start())

        # Start folder watchers for any saved watch dirs
        for d in self.settings.get("watch_dirs", []):
            if Path(d).is_dir():
                self._watcher.watch(d)

        # Global media key hotkeys
        try:
            self._hotkeys = GlobalHotkeys({
                1: lambda: self.root.after(0, self._toggle_play),
                2: lambda: self.root.after(0, self._next),
                3: lambda: self.root.after(0, self._prev),
                4: lambda: self.root.after(0, self._toggle_play),
            })
            self._hotkeys.start()
        except Exception:
            self._hotkeys = None        # Auto-start Spotify poll if we already have a valid token
        if self.sp_auth.is_authenticated():
            self.root.after(4000, lambda: self._sp_poll_np() if self._sp_np_job is None else None)

        # Global keyboard shortcuts
        self.root.bind("<Control-p>", lambda e: self._open_palette())
        self.root.bind("<Control-k>", lambda e: self._open_palette())

    def _on_close(self):
        self._fft_active = False
        if getattr(self, "_hotkeys", None):
            self._hotkeys.stop()
        if getattr(self, "_mini_win", None):
            try: self._mini_win.destroy()
            except: pass
        try:
            if self.root.overrideredirect():
                self.root.overrideredirect(False)
        except Exception:
            pass
        self.root.destroy()

    # ── PERSISTENCE ───────────────────────
    def _load_data(self):
        self.settings = {
            "crossfade_sec":      0,
            "eq_preset":          "flat",
            "normalize":          False,
            "viz_sensitivity":    1.0,
            "viz_smoothing":      0.18,
            "output_device":      "default",
            "spotify_quality":    "high",
            "spotify_crossfade":  False,
            "spotify_normalize":  True,
            "autoplay":           True,
            "show_notifications": True,
            "theme_accent":       "white",
            "borderless_fullscreen": False,
            # New
            "lastfm_api_key":     "",
            "lastfm_api_secret":  "",
            "lastfm_session_key": "",
            "lastfm_enabled":     False,
            "discord_enabled":    False,
            "watch_dirs":         [],
            "hotkeys":            {},
            "playback_speed":     1.0,
            "active_theme":       "void",
        }
        if DATA_FILE.exists():
            try:
                d = json.loads(DATA_FILE.read_text())
                self.library   = [t for t in d.get("library",   []) if Path(t["path"]).exists()]
                self.playlists = d.get("playlists", {})
                self.settings.update(d.get("settings", {}))
                self._history  = d.get("history",   [])[-self._history_max:]
                self._bookmarks = {int(k): v for k, v in d.get("bookmarks", {}).items()}
                self._sc_favorites = d.get("sc_favorites", [])
            except:
                pass

    def _save(self):
        try:
            DATA_FILE.write_text(json.dumps(
                {"library":   self.library,
                 "playlists": self.playlists,
                 "settings":  self.settings,
                 "history":   self._history[-self._history_max:],
                 "bookmarks": {str(k): v for k, v in self._bookmarks.items()},
                 "sc_favorites": getattr(self, "_sc_favorites", [])},
                indent=2))
        except:
            pass

    # ── SETTINGS ──────────────────────────
    def _open_settings(self):
        if hasattr(self, "_settings_win") and self._settings_win and \
                self._settings_win.winfo_exists():
            self._settings_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("OTERNOS // SETTINGS")
        win.configure(bg=C["bg"])
        win.geometry("600x700")
        win.resizable(False, False)
        self._settings_win = win

        # ── scanline header canvas ───────────────────────────────────────
        hdr_cv = tk.Canvas(win, bg=C["panel"], height=56, highlightthickness=0)
        hdr_cv.pack(fill="x")
        def _draw_settings_hdr(e=None):
            hdr_cv.delete("all")
            W = hdr_cv.winfo_width() or 600
            # scanlines
            for y in range(0, 56, 3):
                hdr_cv.create_line(0, y, W, y, fill="#0a0a0a", width=1)
            # bottom borders
            hdr_cv.create_line(0, 54, W, 54, fill=C["border2"], width=2)
            hdr_cv.create_line(0, 56, W, 56, fill=C["border"],  width=1)
            # bracket title
            hdr_cv.create_text(20, 28, text="[", font=("Courier New", 14, "bold"),
                               fill=C["white3"], anchor="w")
            hdr_cv.create_text(34, 28, text="SYS::CONFIG", font=("Courier New", 12, "bold"),
                               fill=C["white"], anchor="w")
            hdr_cv.create_text(168, 28, text="]", font=("Courier New", 14, "bold"),
                               fill=C["white3"], anchor="w")
            hdr_cv.create_text(W - 20, 28, text="v1.1", font=("Courier New", 8),
                               fill=C["white3"], anchor="e")
        hdr_cv.bind("<Configure>", lambda e: _draw_settings_hdr())
        win.after(10, _draw_settings_hdr)

        cl = tk.Label(hdr_cv, text="[ ✕ ]", font=("Courier New", 10), fg=C["white3"],
                      bg=C["panel"], cursor="hand2", padx=10)
        cl.place(relx=1.0, rely=0.5, anchor="e", x=-8)
        cl.bind("<Button-1>", lambda e: win.destroy())
        cl.bind("<Enter>",    lambda e: cl.config(fg=C["white"]))
        cl.bind("<Leave>",    lambda e: cl.config(fg=C["white3"]))

        # ── scrollable body ─────────────────────────────────────────────
        body_outer = tk.Frame(win, bg=C["bg"])
        body_outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(body_outer, bg=C["bg"], highlightthickness=0)
        sb = tk.Scrollbar(body_outer, orient="vertical", command=canvas.yview,
                          bg=C["panel"], troughcolor=C["bg"], width=8,
                          relief="flat", bd=0)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=C["bg"])
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            body_id, width=e.width))
        def _settings_scroll(e):
            canvas.yview_scroll(int(-1*(e.delta/120))*3, "units")
        canvas.bind("<MouseWheel>", _settings_scroll)
        body.bind("<MouseWheel>", _settings_scroll)
        # Rebind all children whenever body resizes (new widgets added)
        def _bind_children(w):
            w.bind("<MouseWheel>", _settings_scroll)
            for child in w.winfo_children():
                _bind_children(child)
        body.bind("<Configure>", lambda e: (_bind_children(body),
            canvas.configure(scrollregion=canvas.bbox("all"))))

        # ── footer ──────────────────────────────────────────────────────
        foot = tk.Frame(win, bg=C["panel"], height=48)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        tk.Frame(foot, bg=C["border2"], height=2).pack(fill="x")
        tk.Frame(foot, bg=C["border"],  height=1).pack(fill="x")
        save_btn = tk.Label(foot, text="▸ WRITE CONFIG", font=("Courier New", 9, "bold"),
                            fg=C["white3"], bg=C["panel"], cursor="hand2", padx=18)
        save_btn.pack(side="right", pady=10)
        save_btn.bind("<Button-1>", lambda e: self._save_settings(vars_map, win))
        save_btn.bind("<Enter>",    lambda e: save_btn.config(fg=C["glow"]))
        save_btn.bind("<Leave>",    lambda e: save_btn.config(fg=C["white3"]))
        reset_btn = tk.Label(foot, text="[ RESET ]", font=FM,
                             fg=C["white3"], bg=C["panel"], cursor="hand2", padx=18)
        reset_btn.pack(side="left", pady=10)
        reset_btn.bind("<Button-1>", lambda e: self._open_settings())
        reset_btn.bind("<Enter>",    lambda e: reset_btn.config(fg=C["white"]))
        reset_btn.bind("<Leave>",    lambda e: reset_btn.config(fg=C["white3"]))

        # ── helper builders ─────────────────────────────────────────────
        vars_map = {}
        s = self.settings

        _SECTION_ICONS = {
            ">> PLAYBACK":    "▶",
            ">> EQUALIZER":   "◈",
            ">> INTERFACE":   "□",
            ">> LIBRARY":     "▪",
            ">> INTEGRATIONS":"◉",
            ">> ADVANCED":    "△",
        }

        def section(title):
            tk.Frame(body, bg=C["bg"], height=10).pack(fill="x")
            hf = tk.Frame(body, bg=C["bg"])
            hf.pack(fill="x", padx=20)
            icon = _SECTION_ICONS.get(title, "▸")
            tk.Label(hf, text=icon, font=("Courier New", 9, "bold"),
                     fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(0, 6))
            tk.Label(hf, text=title.lstrip("> ").upper(),
                     font=("Courier New", 8, "bold"),
                     fg=C["white3"], bg=C["bg"]).pack(side="left")
            tk.Frame(body, bg=C["border2"], height=1).pack(fill="x", padx=20, pady=(3, 0))
            tk.Frame(body, bg=C["border"],  height=1).pack(fill="x", padx=20, pady=(1, 3))

        def row(label, widget_fn, key, hint=""):
            rf = tk.Frame(body, bg=C["bg"])
            rf.pack(fill="x", padx=28, pady=(4, 0))
            lf = tk.Frame(rf, bg=C["bg"])
            lf.pack(side="left", padx=(0, 16))
            tk.Label(lf, text=label, font=("Courier New", 9), fg=C["white2"],
                     bg=C["bg"], anchor="w", width=24, justify="left").pack(anchor="w")
            if hint:
                tk.Label(lf, text=hint, font=("Courier New", 7),
                         fg=C["white3"], bg=C["bg"], anchor="w").pack(anchor="w")
            wf = tk.Frame(rf, bg=C["bg"])
            wf.pack(side="left", fill="x", expand=True)
            var = widget_fn(wf, key)
            vars_map[key] = var
            tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=28)
            return var

        def make_toggle(parent, key):
            var = tk.BooleanVar(value=s.get(key, False))
            tf = tk.Frame(parent, bg=C["bg"])
            tf.pack(side="left")
            def _toggle():
                var.set(not var.get())
                lbl.config(text="[ ON  ]" if var.get() else "[ OFF ]",
                           fg=C["white"] if var.get() else C["white3"])
            lbl = tk.Label(tf, text="[ ON  ]" if var.get() else "[ OFF ]",
                           font=FM, fg=C["white"] if var.get() else C["white3"],
                           bg=C["bg"], cursor="hand2")
            lbl.pack()
            lbl.bind("<Button-1>", lambda e: _toggle())
            return var

        def make_dropdown(parent, key, options):
            var = tk.StringVar(value=s.get(key, options[0]))
            frame = tk.Frame(parent, bg=C["bg"])
            frame.pack(side="left")
            lbl = tk.Label(frame, text=f"[ {var.get().upper()} ]",
                           font=FM, fg=C["white2"], bg=C["bg"],
                           cursor="hand2")
            lbl.pack()
            def _cycle(e=None):
                idx = options.index(var.get()) if var.get() in options else 0
                var.set(options[(idx + 1) % len(options)])
                lbl.config(text=f"[ {var.get().upper()} ]")
            lbl.bind("<Button-1>", _cycle)
            return var

        def make_slider(parent, key, mn, mx, step, fmt="{:.2f}"):
            val = s.get(key, mn)
            var = tk.DoubleVar(value=val)
            sf = tk.Frame(parent, bg=C["bg"])
            sf.pack(side="left", fill="x", expand=True)
            disp = tk.Label(sf, text=fmt.format(val), font=FM,
                            fg=C["white2"], bg=C["bg"], width=6)
            disp.pack(side="right")
            cv = tk.Canvas(sf, bg=C["border"], height=4, width=130,
                           highlightthickness=0, cursor="hand2")
            cv.pack(side="left", padx=(0, 8), pady=8)
            fill_id = cv.create_rectangle(0, 0, 0, 4, fill=C["white"], outline="")
            dot_id  = cv.create_oval(-4, -2, 4, 6, fill=C["glow"], outline="")

            def _draw(v):
                frac = (v - mn) / (mx - mn)
                x = int(frac * 130)
                cv.coords(fill_id, 0, 0, max(1, x), 4)
                cv.coords(dot_id, x-4, -2, x+4, 6)
                disp.config(text=fmt.format(v))

            def _set(x):
                frac = max(0.0, min(1.0, x / 130))
                v = mn + round((frac * (mx - mn)) / step) * step
                var.set(v)
                _draw(v)

            cv.bind("<ButtonPress-1>", lambda e: _set(e.x))
            cv.bind("<B1-Motion>",     lambda e: _set(e.x))
            _draw(val)
            return var

        def make_int_slider(parent, key, mn, mx):
            val = int(s.get(key, mn))
            var = tk.IntVar(value=val)
            sf = tk.Frame(parent, bg=C["bg"])
            sf.pack(side="left", fill="x", expand=True)
            disp = tk.Label(sf, text=str(val), font=FM,
                            fg=C["white2"], bg=C["bg"], width=4)
            disp.pack(side="right")
            cv = tk.Canvas(sf, bg=C["border"], height=4, width=130,
                           highlightthickness=0, cursor="hand2")
            cv.pack(side="left", padx=(0, 8), pady=8)
            fill_id = cv.create_rectangle(0, 0, 0, 4, fill=C["white"], outline="")
            dot_id  = cv.create_oval(-4, -2, 4, 6, fill=C["glow"], outline="")

            def _draw(v):
                frac = (v - mn) / (mx - mn)
                x = int(frac * 130)
                cv.coords(fill_id, 0, 0, max(1, x), 4)
                cv.coords(dot_id, x-4, -2, x+4, 6)
                disp.config(text=str(v))

            def _set(x):
                frac = max(0.0, min(1.0, x / 160))
                v = mn + round(frac * (mx - mn))
                var.set(v)
                _draw(v)

            cv.bind("<ButtonPress-1>", lambda e: _set(e.x))
            cv.bind("<B1-Motion>",     lambda e: _set(e.x))
            _draw(val)
            return var

        def make_entry(parent, key):
            var = tk.StringVar(value=s.get(key,""))
            e = tk.Entry(parent, textvariable=var, font=FM, bg=C["panel"],
                         fg=C["white"], insertbackground=C["white"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=C["border"], width=28)
            e.pack(side="left", ipady=3)
            return var
        section(">> PLAYBACK")
        row("Autoplay next track",    make_toggle,   "autoplay")
        row("Crossfade",
            lambda p, k: make_int_slider(p, k, 0, 12),
            "crossfade_sec",
            hint="seconds  (0 = off)")
        row("Normalize volume",       make_toggle,   "normalize",
            hint="level-match tracks")
        row("Output device",
            lambda p, k: make_dropdown(p, k, ["default", "hdmi", "speakers", "headphones", "aux"]),
            "output_device")

        # ════════════════════════════════════════════════════════════════
        #  EQUALIZER
        # ════════════════════════════════════════════════════════════════
        section(">> EQUALIZER")
        row("EQ preset",
            lambda p, k: make_dropdown(p, k,
                ["flat", "bass boost", "treble boost", "vocal",
                 "electronic", "rock", "classical", "podcast"]),
            "eq_preset")

        # EQ band display (visual only — shows what each preset does)
        eq_frame = tk.Frame(body, bg=C["bg"])
        eq_frame.pack(fill="x", padx=24, pady=(2, 10))
        EQ_PRESETS = {
            "flat":         [0]*8,
            "bass boost":   [6, 5, 3, 1, 0, 0, 0, 0],
            "treble boost": [0, 0, 0, 0, 1, 3, 5, 6],
            "vocal":        [-2,-1, 2, 4, 4, 2,-1,-2],
            "electronic":   [4, 3, 0,-2,-1, 2, 4, 3],
            "rock":         [3, 2, 1, 0, 0, 1, 2, 3],
            "classical":    [3, 2, 0, 0, 0, 0, 2, 3],
            "podcast":      [-1,-1, 2, 4, 3, 1, 0,-1],
        }
        BANDS = ["60", "150", "400", "1k", "2.4k", "6k", "12k", "16k"]
        eq_cv = tk.Canvas(eq_frame, bg=C["panel2"], height=70, width=460,
                          highlightthickness=1,
                          highlightbackground=C["border"])
        eq_cv.pack()

        def _draw_eq(preset="flat"):
            eq_cv.delete("all")
            bands = EQ_PRESETS.get(preset, [0]*8)
            W2, H2 = 460, 70
            bw = W2 / len(bands)
            mid = H2 / 2
            for i, db in enumerate(bands):
                x1 = i * bw + 4
                x2 = (i+1) * bw - 4
                bar_h = (db / 12.0) * (H2/2 - 6)
                y1 = mid - bar_h
                y2 = mid
                if db >= 0:
                    br = 120 + int(db / 12 * 135)
                    col = f"#{br:02x}{br:02x}{br:02x}"
                else:
                    br = 80 + int(abs(db) / 12 * 60)
                    col = f"#{br//2:02x}{br//2:02x}{br:02x}"
                eq_cv.create_rectangle(x1, min(y1,y2), x2, max(y1,y2),
                                       fill=col, outline="")
                eq_cv.create_text((x1+x2)/2, H2-6, text=BANDS[i],
                                  font=("Courier New",6), fill=C["white3"], anchor="s")
            # centre line
            eq_cv.create_line(0, mid, W2, mid, fill=C["border"], width=1)

        _draw_eq(s.get("eq_preset", "flat"))
        # hook dropdown to redraw eq
        eq_var = vars_map.get("eq_preset")
        if eq_var:
            eq_var.trace("w", lambda *a: _draw_eq(eq_var.get()))

        # ════════════════════════════════════════════════════════════════
        #  VISUALIZER
        # ════════════════════════════════════════════════════════════════
        section(">> VISUALIZER")
        row("FFT sensitivity",
            lambda p, k: make_slider(p, k, 0.5, 3.0, 0.1, fmt="{:.1f}x"),
            "viz_sensitivity",
            hint="scales bar heights")
        row("Smoothing",
            lambda p, k: make_slider(p, k, 0.05, 0.6, 0.01, fmt="{:.2f}"),
            "viz_smoothing",
            hint="lower = smoother")

        # ════════════════════════════════════════════════════════════════
        #  SPOTIFY
        # ════════════════════════════════════════════════════════════════
        section(">> SPOTIFY")
        row("Streaming quality",
            lambda p, k: make_dropdown(p, k,
                ["low", "normal", "high", "very high"]),
            "spotify_quality",
            hint="requires Spotify Premium for very high")
        row("Crossfade",          make_toggle, "spotify_crossfade",
            hint="blend between tracks")
        row("Normalize volume",   make_toggle, "spotify_normalize",
            hint="loud normalization on/off")

        # ════════════════════════════════════════════════════════════════
        #  INTERFACE
        # ════════════════════════════════════════════════════════════════
        section(">> PERFORMANCE")
        row("Hardware Accelerator", make_toggle, "hw_accel",
            hint="high FPS animations, GPU rendering hints, fast poll rate")
        row("Viz bars (HW off: 12)", make_toggle, "hw_accel_viz_reduce",
            hint="reduce visualizer bars when HW off for lower CPU use")

        section(">> INTERFACE")
        row("Desktop notifications", make_toggle, "show_notifications",
            hint="show track change popups")
        row("Borderless fullscreen", make_toggle, "borderless_fullscreen",
            hint="fills screen, no title bar or taskbar")
        row("Accent colour",
            lambda p, k: make_dropdown(p, k,
                ["white", "cyan", "green", "amber", "red", "purple"]),
            "theme_accent")

        # ════════════════════════════════════════════════════════════════
        #  LAST.FM
        # ════════════════════════════════════════════════════════════════
        section(">> LAST.FM SCROBBLING")
        row("Enable scrobbling",  make_toggle, "lastfm_enabled",
            hint="send played tracks to Last.fm")
        row("API Key",
            lambda p, k: make_entry(p, k),
            "lastfm_api_key", hint="from last.fm/api/accounts")
        row("API Secret",
            lambda p, k: make_entry(p, k),
            "lastfm_api_secret")

        # Auth button
        auth_f = tk.Frame(body, bg=C["bg"])
        auth_f.pack(fill="x", padx=24, pady=(2,8))
        ab = tk.Label(auth_f, text="[ CONNECT LAST.FM ]", font=FM,
                      fg=C["white3"], bg=C["panel"], cursor="hand2", padx=8, pady=4)
        ab.pack(side="left")
        ab.bind("<Button-1>", lambda e: (win.destroy(), self._open_lastfm_auth()))
        ab.bind("<Enter>",    lambda e: ab.config(fg=C["white"]))
        ab.bind("<Leave>",    lambda e: ab.config(fg=C["white3"]))
        sk_status = "✓ Connected" if s.get("lastfm_session_key") else "Not connected"
        tk.Label(auth_f, text=sk_status, font=FMS,
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=10)

        # ════════════════════════════════════════════════════════════════
        #  DISCORD
        # ════════════════════════════════════════════════════════════════
        section(">> DISCORD RICH PRESENCE")
        row("Enable Discord RPC", make_toggle, "discord_enabled",
            hint="show now-playing in Discord status")

        # bottom padding
        tk.Frame(body, bg=C["bg"], height=20).pack()

    def _save_settings(self, vars_map, win):
        for key, var in vars_map.items():
            self.settings[key] = var.get()
        # Apply live settings
        self._apply_settings()
        self._save()
        win.destroy()

    def _apply_settings(self):
        global HW_ACCEL
        s = self.settings
        self._viz_sensitivity = float(s.get("viz_sensitivity", 1.0))
        self._viz_smooth      = float(s.get("viz_smoothing",   0.18))
        self._apply_borderless(s.get("borderless_fullscreen", False))
        self._apply_accent(s.get("theme_accent", "white"))
        # Restore saved theme on startup
        active = s.get("active_theme", "").upper()
        if active and active in {k.upper() for k in self._theme_presets}:
            preset_key = next(k for k in self._theme_presets if k.upper() == active)
            C.update(self._theme_presets[preset_key])
            C["panel2"] = C["panel"]
            self._rebuild_ui_colors()
        # Hardware Accelerator
        new_hw = bool(s.get("hw_accel", True))
        if new_hw != HW_ACCEL:
            HW_ACCEL = new_hw
            self._apply_hw_accel(HW_ACCEL)
        # Discord toggle
        if s.get("discord_enabled") and not self._discord_enabled:
            threading.Thread(target=self._discord_connect, daemon=True).start()
        elif not s.get("discord_enabled") and self._discord_enabled:
            self._discord.clear()
            self._discord_enabled = False
        # Last.fm credentials update
        if self._scrobbler:
            self._scrobbler.api_key     = s.get("lastfm_api_key","")
            self._scrobbler.api_secret  = s.get("lastfm_api_secret","")
            self._scrobbler.session_key = s.get("lastfm_session_key","")

    def _apply_hw_accel(self, enabled):
        """Apply hardware accelerator state live."""
        try:
            # Update wavevis bar count
            bars = 48 if enabled else 12
            if hasattr(self, "wavevis"):
                self.wavevis.bars   = bars
                self.wavevis.phases = [__import__("random").uniform(0, __import__("math").pi*2) for _ in range(bars)]
                self.wavevis.speeds = [__import__("random").uniform(0.03, 0.09) for _ in range(bars)]
            # Update status in sidebar
            if hasattr(self, "_sidebar_status_lbl"):
                    hw_txt = "[ HW:ON ]" if enabled else "[ HW:OFF ]"
                    self._sidebar_status_lbl.config(
                        text=hw_txt,
                        fg=C["white2"] if enabled else C["white3"])
            # Show toast
            self._toast("Hardware Accelerator: " + ("ON" if enabled else "OFF"))
        except Exception as ex:
            pass

    def _apply_accent(self, name):
        # Monochrome only — glow is always white
        C["glow"]  = "#ffffff"
        C["white"] = "#f0f0f0"

    def _apply_borderless(self, enable):
        if enable:
            self.root.overrideredirect(True)
            self.root.state("zoomed")
        else:
            # Only un-fullscreen if currently overrideredirect
            try:
                if self.root.overrideredirect():
                    self.root.overrideredirect(False)
                    self.root.state("normal")
                    self.root.geometry("1100x700")
            except Exception:
                pass

    # ── TOP BAR ───────────────────────────
    def _build_ui(self):
        self._build_topbar()
        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True)
        self._build_sidebar(main)
        self._build_content(main)
        self._build_playerbar()
        # Overlay lives on top of content for view transitions
        self._fade_overlay = FadeOverlay(self.root, self.content)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C["panel"], height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        # Signalis-style double bottom border — thick rule then hairline
        tk.Frame(self.root, bg=C["border2"], height=2).pack(fill="x")
        tk.Frame(self.root, bg=C["border"],  height=1).pack(fill="x")

        # Left accent column — vertical status stripe
        tk.Frame(bar, bg=C["border2"], width=3).pack(side="left", fill="y")

        # Wordmark — [SYS] prefix + angular tracked name
        sys_lbl = tk.Label(bar, text="[SYS]", font=("Courier New", 7),
                 fg=C["white3"], bg=C["panel"], padx=6)
        sys_lbl.pack(side="left")
        wm = tk.Label(bar, text="OTERNOS", font=("Courier New", 10, "bold"),
                 fg=C["white"], bg=C["panel"], padx=4)
        wm.pack(side="left")
        # Angular divider
        tk.Label(bar, text="◂", font=("Courier New", 8), fg=C["border2"],
                 bg=C["panel"], padx=2).pack(side="left")
        tk.Frame(bar, bg=C["border2"], width=1).pack(side="left", fill="y", pady=8)

        self.tab_btns = {}
        self._tab_keys = []
        for label, key in [("LIBRARY","library"), ("QUEUE","queue"),
                            ("VISUALIZER","visualizer"), ("LYRICS","lyrics"),
                            ("HISTORY","history"), ("ALBUMS","albums"),
                            ("SPOTIFY","spotify"), ("SOUNDCLOUD","soundcloud"),
                            ("YOUTUBE","youtube"), ("CLAUDE","claude"), ("HELP","help")]:
            # Signalis: tabs have a leading ▸ marker when active, flat monospace otherwise
            b = tk.Label(bar, text=label, font=("Courier New", 7, "bold"), fg=C["white3"],
                         bg=C["panel"], cursor="hand2", padx=8, pady=14)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._switch_view(k))
            b.bind("<Enter>",    lambda e, w=b, k=key: self._tab_hover(w, k, True))
            b.bind("<Leave>",    lambda e, w=b, k=key: self._tab_hover(w, k, False))
            self.tab_btns[key] = b
            self._tab_keys.append(key)

        # Right side — system controls with Signalis bracket style
        tk.Frame(bar, bg=C["border2"], width=1).pack(side="right", fill="y", pady=8)
        gear = tk.Label(bar, text="[CFG]", font=("Courier New", 7, "bold"), fg=C["white3"],
                        bg=C["panel"], cursor="hand2", padx=12)
        gear.pack(side="right")
        gear.bind("<Button-1>", lambda e: self._open_settings())
        gear.bind("<Enter>",    lambda e: ColorAnim.run(self.root, gear, "fg", C["white3"], C["white"]))
        gear.bind("<Leave>",    lambda e: ColorAnim.run(self.root, gear, "fg", C["white"], C["white3"]))
        # HW Accelerator quick toggle — Signalis system readout style
        tk.Frame(bar, bg=C["border"], width=1).pack(side="right", fill="y", pady=8)
        self._hw_btn = tk.Label(bar, text="[HW:ON]", font=("Courier New", 7, "bold"),
                                fg=C["white2"], bg=C["panel"], cursor="hand2", padx=8)
        self._hw_btn.pack(side="right")
        def _toggle_hw(e):
            global HW_ACCEL
            HW_ACCEL = not HW_ACCEL
            self.settings["hw_accel"] = HW_ACCEL
            self._hw_btn.config(
                text="[HW:ON]" if HW_ACCEL else "[HW:OFF]",
                fg=C["white2"] if HW_ACCEL else C["white3"])
            self._apply_hw_accel(HW_ACCEL)
            self._save()
        self._hw_btn.bind("<Button-1>", _toggle_hw)
        self._hw_btn.bind("<Enter>", lambda e: self._hw_btn.config(fg=C["white"]))
        self._hw_btn.bind("<Leave>", lambda e: self._hw_btn.config(
            fg=C["white2"] if HW_ACCEL else C["white3"]))

        bar.bind("<ButtonPress-1>", lambda e: (setattr(self,"_dx",e.x), setattr(self,"_dy",e.y)))
        bar.bind("<B1-Motion>",     lambda e: self.root.geometry(
            f"+{self.root.winfo_x()+e.x-self._dx}+{self.root.winfo_y()+e.y-self._dy}"))

        self._update_tabs()

    def _tab_hover(self, widget, key, entering):
        active_key = "library" if self.view in ("library","playlist") else self.view
        is_active  = (key == active_key)
        _labels = {
            "library": "LIBRARY", "queue": "QUEUE", "visualizer": "VISUALIZER",
            "lyrics": "LYRICS", "history": "HISTORY", "albums": "ALBUMS",
            "spotify": "SPOTIFY", "soundcloud": "SOUNDCLOUD", "youtube": "YOUTUBE",
            "claude": "CLAUDE", "help": "HELP",
        }
        if entering:
            from_col = C["white"] if is_active else C["white3"]
            ColorAnim.run(self.root, widget, "fg", from_col, C["glow"], duration_ms=60)
            if key == "youtube":
                self._yt_show_dropdown(widget)
        else:
            to_col = C["white"] if is_active else C["white3"]
            ColorAnim.run(self.root, widget, "fg", C["glow"], to_col, duration_ms=50)
            if key == "youtube":
                # delay close so mouse can move into dropdown
                self.root.after(300, self._yt_maybe_close_dropdown)

    def _yt_show_dropdown(self, widget):
        """Show SEARCH / SAVED dropdown under the YOUTUBE tab button."""
        try:
            if hasattr(self, "_yt_dropdown") and self._yt_dropdown and self._yt_dropdown.winfo_exists():
                return
        except Exception:
            pass
        dd = tk.Frame(self.root, bg=C["panel"], bd=0, highlightthickness=1,
                      highlightbackground=C["border"])
        self._yt_dropdown = dd
        x = widget.winfo_rootx() - self.root.winfo_rootx()
        y = widget.winfo_rooty() - self.root.winfo_rooty() + widget.winfo_height()
        dd.place(x=x, y=y, width=90)

        def _btn(text, cmd):
            b = tk.Label(dd, text=text, font=("Courier New", 7), fg=C["white3"],
                         bg=C["panel"], cursor="hand2", anchor="w", padx=8, pady=3)
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e: (self._yt_close_dropdown(), cmd()))
            b.bind("<Enter>",    lambda e: b.config(fg=C["white"], bg=C["select2"]))
            b.bind("<Leave>",    lambda e: b.config(fg=C["white3"], bg=C["panel"]))

        _btn("/ SEARCH",  lambda: self._yt_set_subview("search"))
        _btn("* SAVED",   lambda: self._yt_set_subview("saved"))

        # Auto-close when mouse leaves dropdown
        def _leave(e):
            try:
                wx, wy = dd.winfo_rootx(), dd.winfo_rooty()
                ww, wh = dd.winfo_width(), dd.winfo_height()
                mx, my = e.x_root, e.y_root
                if not (wx <= mx <= wx+ww and wy <= my <= wy+wh):
                    self._yt_close_dropdown()
            except Exception:
                pass
        dd.bind("<Leave>", _leave)
        # Poll to close if mouse leaves both button and dropdown
        def _poll_close():
            try:
                if getattr(self, "_yt_dropdown", None) and self._yt_dropdown.winfo_exists():
                    self._yt_maybe_close_dropdown()
                    self.root.after(150, _poll_close)
            except Exception:
                pass
        self.root.after(500, _poll_close)

    def _yt_close_dropdown(self):
        try:
            if hasattr(self, "_yt_dropdown") and self._yt_dropdown:
                self._yt_dropdown.destroy()
                self._yt_dropdown = None
        except Exception:
            pass

    def _yt_maybe_close_dropdown(self):
        """Close dropdown only if mouse is not over it."""
        try:
            dd = getattr(self, "_yt_dropdown", None)
            if not dd or not dd.winfo_exists():
                return
            mx = self.root.winfo_pointerx() - self.root.winfo_rootx()
            my = self.root.winfo_pointery() - self.root.winfo_rooty()
            dx = dd.winfo_x(); dy = dd.winfo_y()
            dw = dd.winfo_width(); dh = dd.winfo_height()
            # Also check if mouse is over the YOUTUBE tab button
            yt_btn = self.tab_btns.get("youtube")
            over_btn = False
            if yt_btn:
                bx = yt_btn.winfo_x(); by = yt_btn.winfo_y()
                bw = yt_btn.winfo_width(); bh = yt_btn.winfo_height()
                over_btn = bx <= mx <= bx+bw and by <= my <= by+bh
            over_dd = dx <= mx <= dx+dw and dy <= my <= dy+dh
            if not over_dd and not over_btn:
                self._yt_close_dropdown()
        except Exception:
            pass

    def _yt_set_subview(self, subview):
        """Switch between search and saved within YouTube view."""
        self._switch_view("youtube")
        self._yt_subview = subview
        if subview == "saved":
            self._yt_show_saved()
        else:
            self._yt_show_search()

    def _yt_show_search(self):
        """Show the search UI."""
        if hasattr(self, "yt_search_frame"):
            self.yt_search_frame.pack(fill="x", padx=20, pady=(8, 0))
        self.yt_content_lbl.config(text="Search for music above")
        self._yt_render_list()

    def _yt_show_saved(self):
        """Show saved YouTube tracks."""
        if hasattr(self, "yt_search_frame"):
            self.yt_search_frame.pack_forget()
        saved = self._yt_load_saved()
        if not saved:
            self.yt_content_lbl.config(text="No saved tracks yet — search and click ★ to save")
            self._yt_tracks = []
            self._yt_clear_list()
            return
        self.yt_content_lbl.config(text=f"{len(saved)} saved tracks  —  double-click to play")
        self._yt_tracks = saved
        self._yt_render_list()
        for i, t in enumerate(saved):
            vid_id = t.get("id", "")
            if vid_id:
                url = f"https://i.ytimg.com/vi/{vid_id}/default.jpg"
                threading.Thread(target=self._yt_fetch_thumb,
                    args=(i, url), daemon=True).start()

    def _yt_save_track(self, track):
        """Save a track to the saved list."""
        import json as _json
        path = Path.home() / ".voidplayer_yt_saved.json"
        try:
            saved = _json.loads(path.read_text()) if path.exists() else []
        except Exception:
            saved = []
        # Avoid duplicates
        if not any(t.get("id") == track.get("id") for t in saved):
            saved.append(track)
            path.write_text(_json.dumps(saved))

    def _yt_unsave_track(self, track_id):
        """Remove a track from saved."""
        import json as _json
        path = Path.home() / ".voidplayer_yt_saved.json"
        try:
            saved = _json.loads(path.read_text()) if path.exists() else []
            saved = [t for t in saved if t.get("id") != track_id]
            path.write_text(_json.dumps(saved))
        except Exception:
            pass

    def _yt_load_saved(self):
        import json as _json
        path = Path.home() / ".voidplayer_yt_saved.json"
        try:
            return _json.loads(path.read_text()) if path.exists() else []
        except Exception:
            return []

    def _yt_is_saved(self, track_id):
        return any(t.get("id") == track_id for t in self._yt_load_saved())

    def _update_tabs(self):
        active_key = "library" if self.view in ("library","playlist") else self.view
        _labels = {
            "library": "LIBRARY", "queue": "QUEUE", "visualizer": "VISUALIZER",
            "lyrics": "LYRICS", "history": "HISTORY", "albums": "ALBUMS",
            "spotify": "SPOTIFY", "soundcloud": "SOUNDCLOUD", "youtube": "YOUTUBE",
            "claude": "CLAUDE", "help": "HELP",
        }
        for k, b in self.tab_btns.items():
            is_active = (k == active_key)
            lbl = _labels.get(k, k.upper())
            # Signalis: active tab gets ▸ prefix bracket marker
            b.config(text=f"▸{lbl}" if is_active else lbl)
            target = C["white"] if is_active else C["white3"]
            try:
                current = b.cget("fg")
            except:
                current = target
            ColorAnim.run(self.root, b, "fg", current, target, duration_ms=50)


    # ── SIDEBAR ───────────────────────────
    def _build_sidebar(self, parent):
        # Outer shell — fixed width, no propagate
        shell = tk.Frame(parent, bg=C["panel"], width=200)
        shell.pack(side="left", fill="y")
        shell.pack_propagate(False)

        # Thin right border line
        tk.Frame(shell, bg=C["border"], width=1).pack(side="right", fill="y")

        # Slim scrollbar on the right edge
        self._side_sb = tk.Scrollbar(shell, orient="vertical",
                                     bg=C["panel"], troughcolor=C["panel"],
                                     width=3, bd=0, highlightthickness=0,
                                     relief="flat", activerelief="flat")
        self._side_sb.pack(side="right", fill="y")

        # Scrollable canvas
        self._side_cv = tk.Canvas(shell, bg=C["panel"], highlightthickness=0,
                                  yscrollcommand=self._side_sb.set)
        self._side_cv.pack(side="left", fill="both", expand=True)
        self._side_sb.config(command=self._side_cv.yview)

        # Inner content frame
        side = tk.Frame(self._side_cv, bg=C["panel"])
        self._side_win = self._side_cv.create_window(0, 0, anchor="nw", window=side)

        def _on_inner(e):
            self._side_cv.configure(scrollregion=self._side_cv.bbox("all"))
        def _on_outer(e):
            self._side_cv.itemconfig(self._side_win, width=e.width)
        side.bind("<Configure>", _on_inner)
        self._side_cv.bind("<Configure>", _on_outer)

        def _scroll(e):
            self._side_cv.yview_scroll(-3 if e.delta > 0 else 3, "units")
        self._side_cv.bind("<MouseWheel>", _scroll)
        side.bind("<MouseWheel>", _scroll)
        self._side_scroll_fn = _scroll
        self._side_frame = side

        # ── Animated hex logo at top ──
        logo_frame = tk.Frame(side, bg=C["panel"])
        logo_frame.pack(fill="x", pady=(10, 4))
        self._sidebar_logo = OternosLogo(logo_frame, size=52, bg=C["panel"])
        self._sidebar_logo.pack(side="left", padx=(14, 8))
        # Signalis: vertical system readout panel next to logo
        sys_col = tk.Frame(logo_frame, bg=C["panel"])
        sys_col.pack(side="left", fill="y", pady=4)
        tk.Label(sys_col, text="OTERNOS", font=("Courier New", 8, "bold"),
                 fg=C["white"], bg=C["panel"], anchor="w").pack(anchor="w")
        tk.Label(sys_col, text="SYS::v1.0", font=("Courier New", 6),
                 fg=C["white3"], bg=C["panel"], anchor="w").pack(anchor="w")
        self._sidebar_status_lbl = tk.Label(sys_col, text="[  IDLE  ]",
                 font=("Courier New", 6, "bold"), fg=C["white3"], bg=C["panel"], anchor="w")
        self._sidebar_status_lbl.pack(anchor="w")
        # Signalis: double-line separator
        tk.Frame(side, bg=C["border2"], height=2).pack(fill="x", padx=0, pady=(6, 0))
        tk.Frame(side, bg=C["border"],  height=1).pack(fill="x", padx=0, pady=(1, 0))

        # ── Content ──
        self._slbl(side, "LIBRARY")
        self._sbtn(side, "All Tracks",  lambda: self._switch_view("library"))
        self._sbtn(side, "Add Files",   self._add_files)
        self._sbtn(side, "Add Folder",  self._add_folder)
        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)
        self._slbl(side, "PLAYLISTS")
        self._sbtn(side, "+ New Playlist", self._create_playlist)

        self.pl_sidebar = tk.Frame(side, bg=C["panel"])
        self.pl_sidebar.pack(fill="x")
        self._refresh_pl_sidebar()
        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", pady=(8,0))
        self._ctx_frame = tk.Frame(side, bg=C["panel"])
        self._ctx_frame.pack(fill="x", pady=(4,0))

        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)
        self._slbl(side, "TOOLS")
        self._sbtn(side, "Sleep Timer",    self._open_sleep_timer)
        self._sbtn(side, "Mini Player",    self._toggle_mini_player)
        self._sbtn(side, "Watch Folders",  self._open_watch_dirs)
        self._sbtn(side, "Smart Playlist", self._open_smart_playlist)
        self._sbtn(side, "Find Dupes",     self._open_duplicate_detector)
        self._sbtn(side, "Export M3U",     self._export_playlist_m3u)
        self._sbtn(side, "Hotkeys",        self._open_hotkey_editor)
        self._sbtn(side, "Recommend",      self._open_recommendations)
        self._sbtn(side, "Themes",         self._open_theme_editor)
        self._sbtn(side, "Bookmarks",      self._open_bookmarks)
        self._sbtn(side, "Auto-Playlist",  self._open_auto_playlist)
        self._sbtn(side, "Flow Mode",      self._toggle_flow_mode)
        self._sbtn(side, "Smart Skip",     self._toggle_smart_skip)
        self._sbtn(side, "Voice Ctrl",     self._toggle_voice_control)
        self._sbtn(side, "Ambient Mode",   self._open_ambient_mode)
        self._sbtn(side, "Smart Folders",  self._open_smart_folders)
        tk.Frame(side, bg=C["panel"], height=12).pack()

    def _slbl(self, p, t):
        f = tk.Frame(p, bg=C["panel"])
        f.pack(fill="x", padx=0, pady=(14, 2))
        # Signalis: full-width thick rule + label with angle brackets
        tk.Frame(f, bg=C["border2"], height=2).pack(fill="x")
        lf = tk.Frame(f, bg=C["panel"])
        lf.pack(fill="x", padx=10, pady=(3, 0))
        tk.Label(lf, text=f"<< {t} >>", font=("Courier New", 6, "bold"),
                 fg=C["white3"], bg=C["panel"], anchor="w").pack(fill="x")

    def _sbtn(self, p, t, cmd):
        f = tk.Frame(p, bg=C["panel"], cursor="hand2")
        f.pack(fill="x")
        # Signalis: left accent bar + > prefix on label
        accent = tk.Frame(f, bg=C["border"], width=2)
        accent.pack(side="left", fill="y")
        l = tk.Label(f, text=f"  {t}", font=("Courier New", 8), fg=C["white2"],
                     bg=C["panel"], anchor="w", padx=12, pady=3)
        l.pack(fill="x", side="left", expand=True)
        def _enter(e):
            accent.config(bg=C["border2"])
            ColorAnim.run(self.root, l, "fg", C["white2"], C["white"], duration_ms=50)
            ColorAnim.run(self.root, l, "bg", C["panel"], C["select2"], duration_ms=50)
            ColorAnim.run(self.root, f, "bg", C["panel"], C["select2"], duration_ms=50)
        def _leave(e):
            accent.config(bg=C["border"])
            ColorAnim.run(self.root, l, "fg", C["white"], C["white2"], duration_ms=50)
            ColorAnim.run(self.root, l, "bg", C["select2"], C["panel"], duration_ms=50)
            ColorAnim.run(self.root, f, "bg", C["select2"], C["panel"], duration_ms=50)
        for w in (f, l, accent):
            w.bind("<Button-1>", lambda e: cmd())
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            if hasattr(self, "_side_scroll_fn"):
                w.bind("<MouseWheel>", self._side_scroll_fn)

    def _load_playlist(self, name):
        self._open_playlist(name)

    # ── CONTENT AREA ──────────────────────
    def _build_content(self, parent):
        content_shell = tk.Frame(parent, bg=C["bg"])
        content_shell.pack(side="left", fill="both", expand=True)
        # Ambient ticker strip at very top of content area
        _ct = DataTicker(content_shell, width=1200, height=10, bg=C["bg"])
        _ct.pack(fill="x")
        self.content = tk.Frame(content_shell, bg=C["bg"])
        self.content.pack(fill="both", expand=True)
        self._build_lib_view()
        self._build_queue_view()
        self._switch_view("library")
        self.root.after(100, self._build_deferred_views)

    def _build_deferred_views(self):
        """Build non-essential views after UI is visible to speed up startup."""
        self._build_visualizer_view()
        self.root.after(50,  lambda: self._build_lyrics_view())
        self.root.after(100, lambda: self._build_history_view())
        self.root.after(150, lambda: self._build_album_view())
        self.root.after(200, lambda: self._build_spotify_view())
        self.root.after(250, lambda: self._build_soundcloud_view())
        self.root.after(300, lambda: self._build_youtube_view())
        self.root.after(350, lambda: self._build_claude_view())
        self.root.after(400, lambda: self._build_help_view())

    def _build_lib_view(self):
        self.lib_frame = tk.Frame(self.content, bg=C["bg"])

        hdr = tk.Frame(self.lib_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(10, 0))
        # Signalis: header with system prefix and bracket title
        sys_row = tk.Frame(hdr, bg=C["bg"])
        sys_row.pack(fill="x")
        tk.Label(sys_row, text="VIEW::", font=("Courier New", 8),
                 fg=C["white3"], bg=C["bg"]).pack(side="left")
        self.view_title = tk.Label(sys_row, text="ALL TRACKS", font=("Courier New", 12, "bold"),
                                     fg=C["white"], bg=C["bg"])
        self.view_title.pack(side="left")
        self.count_lbl = tk.Label(hdr, text="", font=("Courier New", 7),
                                   fg=C["white3"], bg=C["bg"])
        self.count_lbl.pack(side="left", padx=12, pady=6)
        self.pl_actions = tk.Frame(hdr, bg=C["bg"])
        self.pl_actions.pack(side="right")

        sf = tk.Frame(self.lib_frame, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=(6, 0))
        tk.Label(sf, text="⌕", font=("Courier New", 11), fg=C["white3"], bg=C["bg"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._refresh_tracks())
        tk.Entry(sf, textvariable=self.search_var, font=FM, bg=C["panel"], fg=C["white"],
                 insertbackground=C["white"], relief="flat", bd=0, width=30).pack(
                     side="left", padx=6, ipady=3)
        tk.Frame(self.lib_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(4, 0))

        ch = tk.Frame(self.lib_frame, bg=C["border"])
        ch.pack(fill="x", padx=20, pady=(6, 0))
        self._sort_col = None
        self._sort_rev = False
        self._col_lbls = {}
        _COLS = [("#", None, 3), ("TITLE", "title", 32), ("ARTIST", "artist", 20),
                 ("ALBUM", "album", 20), ("TIME", "duration", 6)]
        for t, sort_key, w in _COLS:
            lbl = tk.Label(ch, text=t, font=("Courier New", 7, "bold"), fg=C["white3"],
                     bg=C["border"], width=w, anchor="w",
                     cursor="hand2" if sort_key else "arrow")
            lbl.pack(side="left", padx=(8, 0), pady=2)
            if sort_key:
                self._col_lbls[sort_key] = lbl
                def _on_col_click(e, key=sort_key):
                    if self._sort_col == key:
                        self._sort_rev = not self._sort_rev
                    else:
                        self._sort_col = key
                        self._sort_rev = False
                    self._update_col_headers()
                    self._refresh_tracks()
                lbl.bind("<Button-1>", _on_col_click)
                lbl.bind("<Enter>",    lambda e, lb=lbl: lb.config(fg=C["white"]))
                lbl.bind("<Leave>",    lambda e: self._update_col_headers() if hasattr(self, "_col_lbls") else None)

        lf = tk.Frame(self.lib_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.track_list = tk.Canvas(lf, bg=C["bg"], highlightthickness=0,
                                    yscrollcommand=sb.set)
        self.track_list.pack(fill="both", expand=True)
        sb.config(command=self.track_list.yview)
        self.track_list.bind("<Double-Button-1>", self._on_dbl)
        self.track_list.bind("<Button-3>",        self._on_rclick)
        self.track_list.bind("<MouseWheel>", lambda e: self.track_list.yview_scroll(int(-1*(e.delta/120))*3, "units"))
        self.track_list.bind("<Motion>",     self._tl_on_motion)
        self.track_list.bind("<Leave>",      self._tl_on_leave)
        self.track_list.bind("<Configure>",  lambda e: self._refresh_tracks())
        # state for canvas list
        self._tl_row_h     = 26          # default (collapsed) row height
        self._tl_hover_idx = -1          # row index currently hovered
        self._tl_sel_idx   = -1          # selected row index
        self._tl_art_cache = {}          # lib_idx -> PhotoImage (small)
        self._tl_zoom_job  = None
        self._tl_zoom_row  = -1
        self._tl_zoom_h    = 26          # current animated height of hover row
        self._refresh_tracks()

    def _build_queue_view(self):
        self.queue_frame = tk.Frame(self.content, bg=C["bg"])
        hdr = tk.Frame(self.queue_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(12, 4))
        tk.Label(hdr, text="QUEUE", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        cl = tk.Label(hdr, text="clear", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2")
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda e: self._clear_queue())
        cl.bind("<Enter>",    lambda e: cl.config(fg=C["white"]))
        cl.bind("<Leave>",    lambda e: cl.config(fg=C["white3"]))
        lf = tk.Frame(self.queue_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.queue_list = tk.Listbox(lf, bg=C["bg"], fg=C["white2"],
            selectbackground=C["select"], selectforeground=C["white"],
            font=FM, relief="flat", bd=0, activestyle="none",
            yscrollcommand=sb.set,
            highlightthickness=0)
        self.queue_list.pack(fill="both", expand=True)
        sb.config(command=self.queue_list.yview)
        self.queue_list.bind("<Double-Button-1>", self._on_queue_dbl)
        self.queue_list.bind("<MouseWheel>", lambda e: self.queue_list.yview_scroll(int(-1*(e.delta/120))*3, "units"))

        # Drag-to-reorder
        self._q_drag_start = None
        self.queue_list.bind("<ButtonPress-1>",   self._q_drag_press)
        self.queue_list.bind("<B1-Motion>",       self._q_drag_motion)
        self.queue_list.bind("<ButtonRelease-1>", self._q_drag_release)

    def _build_visualizer_view(self):
        self.viz_frame = tk.Frame(self.content, bg=C["bg"])

        # Header row
        hdr = tk.Frame(self.viz_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text="VISUALIZER", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.viz_mode_lbl = tk.Label(hdr, text="[ HEXCORE ]", font=FMS,
                                     fg=C["white3"], bg=C["bg"])
        self.viz_mode_lbl.pack(side="left", padx=10)

        # Cybercore mode buttons (shown by default)
        self._viz_mf_cyber = tk.Frame(hdr, bg=C["bg"])
        self._viz_mf_cyber.pack(side="right")

        # Miku mode buttons (hidden by default)
        self._viz_mf_miku = tk.Frame(hdr, bg=C["bg"])
        # (not packed until miku theme activates)
        self._viz_mf_nerv = tk.Frame(hdr, bg=C["bg"])
        # (not packed until nerv theme activates)

        self._viz_mode = "hexcore"
        self._viz_mode_btns = {}

        for label, mode in [("HEXCORE","hexcore"),("PULSE","pulse"),("ORBIT","orbit"),
                            ("GRID","grid"),("SPECTRUM","spectrum"),
                            ("SCOPE","oscilloscope"),("PARTICLES","particles")]:
            b = tk.Label(self._viz_mf_cyber, text=label, font=FMS, fg=C["white3"],
                         bg=C["bg"], cursor="hand2", padx=8)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, m=mode: self._set_viz_mode(m))
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))
            self._viz_mode_btns[mode] = b

        for label, mode in [("TAILS","miku_tails"),("SAKURA","miku_sakura"),
                            ("STARFALL","miku_starfall"),("RIBBON","miku_ribbon"),
                            ("WAVEFORM","miku_wave")]:
            b = tk.Label(self._viz_mf_miku, text=label,
                         font=("Yu Gothic UI", 8, "bold") if self._font_exists("Yu Gothic UI")
                               else ("Consolas", 8, "bold"),
                         fg=C["glow"] if mode == "miku_tails" else "#1e6068",
                         bg=C["bg"], cursor="hand2", padx=8)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, m=mode: self._set_viz_mode(m))
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["glow"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg="#1e6068"))
            self._viz_mode_btns[mode] = b

        for _nl,_nm in [("MAGI","nerv_magi"),("AT-FIELD","nerv_angel"),("EVA-01","nerv_eva")]:
            _nb=tk.Label(self._viz_mf_nerv,text=_nl,font=("Consolas",8,"bold"),fg="#660000",bg=C["bg"],cursor="hand2",padx=8)
            _nb.pack(side="left")
            _nb.bind("<Button-1>",lambda e,m=_nm: self._set_viz_mode(m))
            _nb.bind("<Enter>",lambda e,w=_nb: w.config(fg="#ff0000"))
            _nb.bind("<Leave>",lambda e,w=_nb: w.config(fg="#660000"))
            self._viz_mode_btns[_nm]=_nb

        tk.Frame(self.viz_frame, bg=C["border"], height=1).pack(fill="x", padx=0, pady=(8,0))

        # Main canvas — full remaining space
        self.viz_cv = tk.Canvas(self.viz_frame, bg=C["bg"], highlightthickness=0)
        self.viz_cv.pack(fill="both", expand=True)

        # Track info bar at very bottom
        info_bar = tk.Frame(self.viz_frame, bg=C["panel"], height=26)
        info_bar.pack(fill="x")
        info_bar.pack_propagate(False)
        self.viz_track_lbl = tk.Label(info_bar, text="— NO TRACK —",
            font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.viz_track_lbl.pack(side="left", padx=16)
        self.viz_pos_lbl = tk.Label(info_bar, text="",
            font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.viz_pos_lbl.pack(side="right", padx=16)

        # Animation state
        self._viz_t       = 0
        self._viz_job     = None
        self._viz_bars    = [0.0] * 48
        self._viz_phases  = [random.uniform(0, math.pi*2) for _ in range(48)]
        self._viz_speeds  = [random.uniform(0.025, 0.075) for _ in range(48)]
        self._viz_orb_ang = 0.0
        self._viz_hex_r   = 0.0
        self._viz_glow    = 0.0
        self._viz_grid_particles = [
            [random.uniform(0,1), random.uniform(0,1),
             random.uniform(-1,1)*0.4, random.uniform(-1,1)*0.4]
            for _ in range(35)
        ]

    def _font_exists(self, name):
        try:
            import tkinter.font as tkfont
            return name in tkfont.families()
        except Exception:
            return False

    def _set_viz_mode(self, mode):
        self._viz_mode = mode
        names = {
            "hexcore":       "[ HEXCORE ]",
            "pulse":         "[ PULSE ]",
            "orbit":         "[ ORBIT ]",
            "grid":          "[ GRID ]",
            "spectrum":      "[ SPECTRUM ]",
            "oscilloscope":  "[ SCOPE ]",
            "particles":     "[ PARTICLES ]",
            "miku_tails":    "♪ TWIN TAILS ♪",
            "miku_sakura":   "✦ SAKURA ✦",
            "miku_starfall": "✧ STARFALL ✧",
            "miku_ribbon":   "♫ RIBBON ♫",
            "miku_wave":     "♬ WAVEFORM ♬",
            "miku":          "♪ MIKU ♪",
            "nerv_magi":     "⬡ MAGI SYSTEM ⬡",
            "nerv_angel":    "⬡ AT-FIELD ⬡",
            "nerv_eva":      "⬡ EVA-01 STATUS ⬡",
        }
        self.viz_mode_lbl.config(text=names.get(mode, f"[ {mode.upper()} ]"))

    def _viz_tick(self):
        if self.view != "visualizer":
            self._viz_job = None
            return
        self._draw_visualizer()
        self._viz_t += 1
        self._viz_job = self.viz_cv.after(30 if HW_ACCEL else 150, self._viz_tick)

    # ── real FFT audio analyser ────────────
    def _start_audio_capture(self):
        """Capture loopback audio via WASAPI (Windows, no extra packages)
        and push 48-band FFT magnitudes into self._fft_bars."""
        try:
            import numpy as np
        except ImportError:
            self._fft_bars = None
            return

        N_BARS = 48
        SMOOTH = 0.15

        self._fft_bars   = [0.0] * N_BARS
        self._fft_lock   = threading.Lock()
        self._fft_active = True

        def _run():
            import numpy as np, ctypes, ctypes.wintypes, time as _t

            # ── WASAPI loopback via COM ──────────────────────────────
            ole32   = ctypes.WinDLL("ole32")
            ole32.CoInitialize(None)

            # GUIDs
            def GUID(s):
                import uuid as _u
                return (ctypes.c_byte*16)(*_u.UUID(s).bytes_le)

            CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            IID_IMMDeviceEnumerator  = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            IID_IAudioClient         = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
            IID_IAudioCaptureClient  = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")

            AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
            AUDCLNT_SHAREMODE_SHARED     = 0
            CLSCTX_ALL                   = 0x17

            # WAVEFORMATEX
            class WAVEFORMATEX(ctypes.Structure):
                _fields_ = [("wFormatTag",2),("nChannels",2),("nSamplesPerSec",4),
                            ("nAvgBytesPerSec",4),("nBlockAlign",2),
                            ("wBitsPerSample",2),("cbSize",2)]
                _fields_ = [
                    ("wFormatTag",      ctypes.c_uint16),
                    ("nChannels",       ctypes.c_uint16),
                    ("nSamplesPerSec",  ctypes.c_uint32),
                    ("nAvgBytesPerSec", ctypes.c_uint32),
                    ("nBlockAlign",     ctypes.c_uint16),
                    ("wBitsPerSample",  ctypes.c_uint16),
                    ("cbSize",          ctypes.c_uint16),
                ]

            # REFERENCE_TIME is 100-nanosecond units
            REFTIMES_PER_SEC = 10_000_000

            try:
                # Create IMMDeviceEnumerator
                enumerator = ctypes.c_void_p()
                hr = ole32.CoCreateInstance(
                    ctypes.byref(CLSID_MMDeviceEnumerator), None,
                    CLSCTX_ALL,
                    ctypes.byref(IID_IMMDeviceEnumerator),
                    ctypes.byref(enumerator))
                if hr != 0:
                    raise OSError(f"CoCreateInstance hr={hr:#010x}")

                # vtable: IMMDeviceEnumerator::GetDefaultAudioEndpoint (index 4)
                vtbl_enum = ctypes.cast(enumerator, ctypes.POINTER(ctypes.c_void_p))
                GetDefaultAudioEndpoint = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                    ctypes.POINTER(ctypes.c_void_p)
                )(vtbl_enum[0][4])

                device = ctypes.c_void_p()
                hr = GetDefaultAudioEndpoint(enumerator, 0, 0, ctypes.byref(device))
                if hr != 0:
                    raise OSError(f"GetDefaultAudioEndpoint hr={hr:#010x}")

                # vtable: IMMDevice::Activate (index 3)
                vtbl_dev = ctypes.cast(device, ctypes.POINTER(ctypes.c_void_p))
                Activate = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_byte*16),
                    ctypes.c_uint, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p)
                )(vtbl_dev[0][3])

                audio_client = ctypes.c_void_p()
                hr = Activate(device, ctypes.byref(IID_IAudioClient),
                              CLSCTX_ALL, None, ctypes.byref(audio_client))
                if hr != 0:
                    raise OSError(f"IMMDevice::Activate hr={hr:#010x}")

                # vtable: IAudioClient::GetMixFormat (index 8)
                vtbl_ac = ctypes.cast(audio_client, ctypes.POINTER(ctypes.c_void_p))
                GetMixFormat = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p)
                )(vtbl_ac[0][8])

                pwfx_ptr = ctypes.c_void_p()
                hr = GetMixFormat(audio_client, ctypes.byref(pwfx_ptr))
                if hr != 0:
                    raise OSError(f"GetMixFormat hr={hr:#010x}")

                pwfx = ctypes.cast(pwfx_ptr, ctypes.POINTER(WAVEFORMATEX))
                rate     = pwfx.contents.nSamplesPerSec
                channels = pwfx.contents.nChannels
                bits     = pwfx.contents.wBitsPerSample

                # vtable: IAudioClient::Initialize (index 3)
                Initialize = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.c_uint, ctypes.c_uint, ctypes.c_longlong,
                    ctypes.c_longlong, ctypes.c_void_p, ctypes.c_void_p
                )(vtbl_ac[0][3])

                buf_dur = REFTIMES_PER_SEC  # 1 second buffer
                hr = Initialize(audio_client,
                                AUDCLNT_SHAREMODE_SHARED,
                                AUDCLNT_STREAMFLAGS_LOOPBACK,
                                buf_dur, 0, pwfx_ptr, None)
                if hr != 0:
                    raise OSError(f"IAudioClient::Initialize hr={hr:#010x}")

                # GetService → IAudioCaptureClient (index 14)
                GetService = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_byte*16),
                    ctypes.POINTER(ctypes.c_void_p)
                )(vtbl_ac[0][14])

                capture_client = ctypes.c_void_p()
                hr = GetService(audio_client, ctypes.byref(IID_IAudioCaptureClient),
                                ctypes.byref(capture_client))
                if hr != 0:
                    raise OSError(f"GetService hr={hr:#010x}")

                # Start (index 11)
                Start = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p)(vtbl_ac[0][11])
                hr = Start(audio_client)
                if hr != 0:
                    raise OSError(f"IAudioClient::Start hr={hr:#010x}")

                # IAudioCaptureClient vtable
                vtbl_cc = ctypes.cast(capture_client, ctypes.POINTER(ctypes.c_void_p))
                # GetNextPacketSize (index 3)
                GetNextPacketSize = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint32)
                )(vtbl_cc[0][3])
                # GetBuffer (index 4) — returns pointer to audio data
                GetBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint64)
                )(vtbl_cc[0][4])  # actually index 3 in IAudioCaptureClient
                # ReleaseBuffer (index 4)
                ReleaseBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.c_uint32
                )(vtbl_cc[0][4])

                # Fix: correct vtable indices for IAudioCaptureClient
                # 0=QI, 1=AddRef, 2=Release, 3=GetBuffer, 4=ReleaseBuffer, 5=GetNextPacketSize
                GetBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint64)
                )(vtbl_cc[0][3])
                ReleaseBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint32
                )(vtbl_cc[0][4])
                GetNextPacketSize = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint32)
                )(vtbl_cc[0][5])

                CHUNK  = 1024
                freqs  = np.fft.rfftfreq(CHUNK, d=1.0/rate)
                edges  = np.logspace(math.log10(40.0), math.log10(16000.0), N_BARS+1)
                accum  = np.zeros(0, dtype=np.float32)

                while self._fft_active:
                    pkt_size = ctypes.c_uint32()
                    GetNextPacketSize(capture_client, ctypes.byref(pkt_size))
                    if pkt_size.value == 0:
                        _t.sleep(0.01)
                        continue

                    data_ptr   = ctypes.c_void_p()
                    num_frames = ctypes.c_uint32()
                    flags      = ctypes.c_uint32()
                    dev_pos    = ctypes.c_uint32()
                    qpc_pos    = ctypes.c_uint64()

                    hr = GetBuffer(capture_client,
                                   ctypes.byref(data_ptr),
                                   ctypes.byref(num_frames),
                                   ctypes.byref(flags),
                                   ctypes.byref(dev_pos),
                                   ctypes.byref(qpc_pos))
                    if hr != 0 or data_ptr.value is None:
                        _t.sleep(0.01)
                        continue

                    n = num_frames.value * channels
                    if bits == 32:
                        raw = np.frombuffer(
                            (ctypes.c_float * n).from_address(data_ptr.value),
                            dtype=np.float32).copy()
                    else:
                        raw = np.frombuffer(
                            (ctypes.c_int16 * n).from_address(data_ptr.value),
                            dtype=np.int16).astype(np.float32) / 32768.0

                    ReleaseBuffer(capture_client, num_frames)

                    # mix to mono
                    if channels > 1:
                        raw = raw.reshape(-1, channels).mean(axis=1)

                    accum = np.concatenate([accum, raw])

                    while len(accum) >= CHUNK:
                        chunk = accum[:CHUNK]
                        accum = accum[CHUNK:]
                        mag   = np.abs(np.fft.rfft(chunk * np.hanning(CHUNK))) / (CHUNK/2)
                        new_bars = []
                        for b in range(N_BARS):
                            mask = (freqs >= edges[b]) & (freqs < edges[b+1])
                            val  = float(np.mean(mag[mask])) * 120.0 if mask.any() else 0.0
                            new_bars.append(min(1.0, val))
                        with self._fft_lock:
                            for i in range(N_BARS):
                                self._fft_bars[i] += (new_bars[i]-self._fft_bars[i])*SMOOTH

                # Stop
                Stop = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p)(vtbl_ac[0][12])
                Stop(audio_client)

            except Exception as e:
                # WASAPI failed — fall back to soundcard if available
                try:
                    import soundcard as sc
                    loopbacks = [m for m in sc.all_microphones(include_loopback=True)
                                 if getattr(m, "isloopback", False)]
                    if not loopbacks:
                        loopbacks = [sc.get_microphone(
                            sc.default_speaker().name, include_loopback=True)]
                    mic   = loopbacks[0]
                    RATE2 = 44100
                    CHUNK2= 1024
                    f2    = np.fft.rfftfreq(CHUNK2, d=1.0/RATE2)
                    e2    = np.logspace(math.log10(40.0), math.log10(16000.0), N_BARS+1)
                    with mic.recorder(samplerate=RATE2, channels=1,
                                      blocksize=CHUNK2) as rec:
                        while self._fft_active:
                            data = rec.record(numframes=CHUNK2)[:,0].astype(np.float32)
                            mag  = np.abs(np.fft.rfft(data * np.hanning(CHUNK2)))/(CHUNK2/2)
                            nb   = []
                            for b in range(N_BARS):
                                mask = (f2 >= e2[b]) & (f2 < e2[b+1])
                                v    = float(np.mean(mag[mask]))*120.0 if mask.any() else 0.0
                                nb.append(min(1.0, v))
                            with self._fft_lock:
                                for i in range(N_BARS):
                                    self._fft_bars[i] += (nb[i]-self._fft_bars[i])*SMOOTH
                except Exception:
                    pass

        self._fft_thread = threading.Thread(target=_run, daemon=True)
        self._fft_thread.start()

    def _sim_bars(self, t, playing):
        """Return 48 bar heights — real FFT data if available, else simulation."""
        # Try real FFT data first
        if hasattr(self, "_fft_bars") and self._fft_bars is not None:
            with self._fft_lock:
                bars = list(self._fft_bars)
            sens = getattr(self, "_viz_sensitivity", 1.0)
            bars = [min(1.0, v * sens) for v in bars]
            if max(bars) > 0.005:
                # Real audio data is flowing — use it
                self._viz_bars = bars
                return self._viz_bars
            # FFT returned all zeros (capture not working) — fall through to simulation

        # Simulation: runs when FFT is unavailable or returning silence
        for i in range(48):
            if playing:
                a   = math.sin(t * self._viz_speeds[i] * 7   + self._viz_phases[i])
                b   = math.sin(t * self._viz_speeds[i] * 2.5 + self._viz_phases[i] * 1.4)
                c   = math.sin(t * self._viz_speeds[i] * 15  + self._viz_phases[i] * 0.6)
                raw = (a * 0.5 + b * 0.3 + c * 0.2) * 0.5 + 0.5
                bass = math.exp(-i / 7.0) * 0.45 * abs(math.sin(t * 0.038))
                raw  = max(0.06, min(1.0, raw + bass))
            else:
                raw = 0.04 + 0.025 * math.sin(t * 0.35 + i * 0.6)
            self._viz_bars[i] += (raw - self._viz_bars[i]) * 0.16
        return self._viz_bars

    def _draw_visualizer(self):
        cv = self.viz_cv
        cv.delete("all")
        W = cv.winfo_width()
        H = cv.winfo_height()
        if W < 4 or H < 4:
            self._viz_job = cv.after(100, self._viz_tick)
            return
        t       = self._viz_t
        playing = self.engine.is_playing or self._sp_playing
        bars    = self._sim_bars(t, playing)

        # smooth glow
        glow_tgt = (sum(bars[:8])/8) if playing else 0.05
        self._viz_glow += (glow_tgt - self._viz_glow) * 0.08

        if   self._viz_mode == "hexcore":      self._viz_hexcore(cv, W, H, t, playing, bars)
        elif self._viz_mode == "pulse":        self._viz_pulse(cv, W, H, t, playing, bars)
        elif self._viz_mode == "orbit":        self._viz_orbit(cv, W, H, t, playing, bars)
        elif self._viz_mode == "grid":         self._viz_grid(cv, W, H, t, playing, bars)
        elif self._viz_mode == "spectrum":     self._viz_spectrum(cv, W, H, t, playing, bars)
        elif self._viz_mode == "oscilloscope": self._viz_oscilloscope(cv, W, H, t, playing, bars)
        elif self._viz_mode == "particles":    self._viz_particles(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku":         self._viz_miku(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_tails":   self._viz_miku_tails(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_sakura":  self._viz_miku_sakura(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_starfall":self._viz_miku_starfall(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_ribbon":  self._viz_miku_ribbon(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_wave":    self._viz_miku_wave(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nerv_magi":   self._viz_nerv_magi(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nerv_angel":  self._viz_nerv_angel(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nerv_eva":    self._viz_nerv_eva(cv, W, H, t, playing, bars)

        # Track label update
        sym = chr(9654) if playing else chr(9646)+chr(9646)
        if self._sp_mode and self._sp_dur_ms > 0:
            title  = self.now_title.cget("text")
            artist = self.now_artist.cget("text")
            self.viz_track_lbl.config(
                text=f"{sym}  {title[:44]}  —  {artist[:28]}")
            self.viz_pos_lbl.config(
                text=f"{self._fmt(self._sp_pos_ms/1000)} / {self._fmt(self._sp_dur_ms/1000)}")
        elif 0 <= self.current_idx < len(self.library):
            tr = self.library[self.current_idx]
            self.viz_track_lbl.config(
                text=f"{sym}  {tr['title'][:44]}  —  {tr['artist'][:28]}")
            pos = self.engine.get_position()
            dur = self.engine.duration
            self.viz_pos_lbl.config(text=f"{self._fmt(pos)} / {self._fmt(dur)}")
        else:
            self.viz_track_lbl.config(text="— NO TRACK —")
            self.viz_pos_lbl.config(text="")

    # ══════════════════════════════════════
    #  MODE: HEXCORE
    #  Big rotating hex + bar spikes + rings
    # ══════════════════════════════════════
    def _viz_hexcore(self, cv, W, H, t, playing, bars):
        cx, cy = W/2, H/2
        base_r = min(W, H) * 0.28
        glow   = self._viz_glow

        # ── outer decoration rings ──
        for ri in range(4):
            frac = (ri+1)/4
            r    = base_r * (1.55 + frac * 0.55)
            br   = int(18 + 12 * (1-frac)) if not playing else int(28 + 20*(1-frac))
            col  = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, fill="", width=1)

        # ── bar spikes radiating outward from hex ──
        n_bars = 48
        for i in range(n_bars):
            angle  = (i / n_bars) * math.pi * 2 - math.pi/2
            h_val  = bars[i]
            # spike starts at hex perimeter, extends outward
            inner_r = base_r * 1.05
            outer_r = inner_r + h_val * base_r * 0.85
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + outer_r * math.cos(angle)
            y2 = cy + outer_r * math.sin(angle)
            # brightness by height
            if playing:
                br = int(60 + 195 * h_val)
            else:
                br = int(25 + 30 * h_val)
            br  = max(0, min(255, br))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(x1, y1, x2, y2, fill=col, width=1)

            # peak dot
            if playing and h_val > 0.4:
                pk = int(200 + 55*h_val)
                pk = min(255, pk)
                cv.create_oval(x2-2, y2-2, x2+2, y2+2,
                               fill=f"#{pk:02x}{pk:02x}{pk:02x}", outline="")

        # ── rotating hexagon — multiple layers ──
        for layer in range(3):
            lf   = layer / 3
            r    = base_r * (1.0 - lf * 0.2)
            spd  = 0.008 * (1 + layer * 0.5) * (1.8 if playing else 0.4)
            rot  = t * spd + layer * math.pi / 6
            pts  = []
            for i in range(6):
                a = i/6*math.pi*2 + rot
                pts += [cx + r*math.cos(a), cy + r*math.sin(a)]
            if playing:
                br = int(120 + 80*(1-lf) + glow * 55)
            else:
                br = int(45 + 25*(1-lf))
            br  = min(255, br)
            lw  = 2 if layer == 0 else 1
            cv.create_polygon(pts, outline=f"#{br:02x}{br:02x}{br:02x}",
                               fill="", width=lw)

        # ── inner crosshair ──
        ch_r  = base_r * 0.45
        ch_br = 60 if not playing else int(80 + glow * 80)
        ch_br = min(255, ch_br)
        ch_col= f"#{ch_br:02x}{ch_br:02x}{ch_br:02x}"
        cv.create_line(cx - ch_r, cy, cx + ch_r, cy, fill=ch_col, width=1)
        cv.create_line(cx, cy - ch_r, cx, cy + ch_r, fill=ch_col, width=1)
        # diagonal ticks
        tk_r = ch_r * 0.3
        for ang in [math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]:
            cv.create_line(cx + (ch_r-tk_r)*math.cos(ang), cy + (ch_r-tk_r)*math.sin(ang),
                           cx + ch_r*math.cos(ang),         cy + ch_r*math.sin(ang),
                           fill=ch_col, width=1)

        # ── centre pulse dot ──
        pulse_r = 3 + glow * 6 if playing else 3
        p_br    = int(180 + glow*75) if playing else 80
        p_br    = min(255, p_br)
        cv.create_oval(cx-pulse_r, cy-pulse_r, cx+pulse_r, cy+pulse_r,
                       fill=f"#{p_br:02x}{p_br:02x}{p_br:02x}", outline="")

        # ── corner hex accents ──
        for (ox, oy) in [(50,50),(W-50,50),(50,H-50),(W-50,H-50)]:
            sr  = 16
            rot2= t * 0.006
            spts= []
            for i in range(6):
                a = i/6*math.pi*2 + rot2
                spts += [ox + sr*math.cos(a), oy + sr*math.sin(a)]
            cv.create_polygon(spts, outline=C["border2"], fill="", width=1)
            cv.create_oval(ox-2, oy-2, ox+2, oy+2, fill=C["border2"], outline="")

    # ══════════════════════════════════════
    #  MODE: PULSE — concentric hex rings
    # ══════════════════════════════════════
    def _viz_pulse(self, cv, W, H, t, playing, bars):
        cx, cy = W/2, H/2
        glow   = self._viz_glow
        n      = 10
        base   = min(W,H) * 0.08

        for ri in range(n):
            frac  = (ri+1)/n
            # radius pulses with bass
            pulse = bars[ri % 8] * 0.18 if playing else 0
            r     = base * (ri+1) * (1 + pulse)
            rot   = t * 0.006 * (1 if ri%2==0 else -1) * (1.6 if playing else 0.3)
            pts   = []
            for i in range(6):
                a = i/6*math.pi*2 + rot + frac
                pts += [cx + r*math.cos(a), cy + r*math.sin(a)]
            if playing:
                br = int(30 + 100*(1-frac) + glow*80*(1-frac))
            else:
                br = int(20 + 30*(1-frac))
            br  = min(255, br)
            lw  = 2 if ri == 0 else 1
            cv.create_polygon(pts, outline=f"#{br:02x}{br:02x}{br:02x}",
                               fill="", width=lw)

        # connecting spokes
        r_outer = base * n
        for i in range(6):
            a  = i/6*math.pi*2 + t*0.006
            x2 = cx + r_outer*math.cos(a)
            y2 = cy + r_outer*math.sin(a)
            br = 40 if not playing else int(50 + glow*60)
            cv.create_line(cx, cy, x2, y2,
                           fill=f"#{br:02x}{br:02x}{br:02x}", width=1)

        # centre
        p = 4 + glow*8 if playing else 4
        br= int(160+glow*95) if playing else 70
        br= min(255,br)
        cv.create_oval(cx-p,cy-p,cx+p,cy+p, fill=f"#{br:02x}{br:02x}{br:02x}", outline="")

    # ══════════════════════════════════════
    #  MODE: ORBIT
    # ══════════════════════════════════════
    def _viz_orbit(self, cv, W, H, t, playing, bars):
        cx, cy  = W/2, H/2
        n_rings = 5
        glow    = self._viz_glow

        for ang in range(0, 360, 30):
            r2 = math.radians(ang)
            R  = min(W,H)*0.46
            br = 20 if not playing else int(22+glow*18)
            cv.create_line(cx, cy,
                           cx+R*math.cos(r2), cy+R*math.sin(r2),
                           fill=f"#{br:02x}{br:02x}{br:02x}", width=1)

        for ri in range(n_rings):
            frac  = (ri+1)/n_rings
            r     = frac * min(W,H) * 0.42
            br    = int(30 + 25*(1-frac)) if not playing else int(45+40*(1-frac)+glow*30)
            br    = min(255,br)
            cv.create_oval(cx-r,cy-r,cx+r,cy+r, outline=f"#{br:02x}{br:02x}{br:02x}",
                           fill="", width=1)
            # hex markers on ring
            n_dots= 6
            spd   = 0.012*(1+ri*0.4)*(1.6 if playing else 0.3)
            rot   = t*spd*(1 if ri%2==0 else -1)
            for di in range(n_dots):
                angle = (di/n_dots)*math.pi*2 + rot
                dx    = cx + r*math.cos(angle)
                dy    = cy + r*math.sin(angle)
                # mini hexagon
                hpts  = []
                hr    = 5 + bars[di % 48]*6 if playing else 4
                for hi in range(6):
                    ha = hi/6*math.pi*2
                    hpts += [dx+hr*math.cos(ha), dy+hr*math.sin(ha)]
                hbr   = int(100+bars[di%48]*155) if playing else 55
                hbr   = min(255,hbr)
                cv.create_polygon(hpts, outline=f"#{hbr:02x}{hbr:02x}{hbr:02x}",
                                  fill="", width=1)

        p = 4+glow*7 if playing else 3
        br= int(180+glow*75) if playing else 80
        br= min(255,br)
        cv.create_oval(cx-p,cy-p,cx+p,cy+p,
                       fill=f"#{br:02x}{br:02x}{br:02x}", outline="")

    # ══════════════════════════════════════
    #  MODE: GRID — Tron perspective
    # ══════════════════════════════════════
    def _viz_grid(self, cv, W, H, t, playing, bars):
        hz   = H * 0.50
        vpx  = W * 0.50
        cols = 18
        rows = 12
        glow = self._viz_glow
        spd  = 0.007 if playing else 0.002

        # update particles
        for p in self._viz_grid_particles:
            p[0] += p[2]*spd; p[1] += p[3]*spd
            if p[0]<0 or p[0]>1: p[2]=-p[2]; p[0]=max(0,min(1,p[0]))
            if p[1]<0 or p[1]>1: p[3]=-p[3]; p[1]=max(0,min(1,p[1]))

        bg_gr = 25 if playing else 16
        bg_c  = f"#{bg_gr:02x}{bg_gr:02x}{bg_gr:02x}"
        for i in range(cols+1):
            bx = (i/cols)*W
            cv.create_line(vpx, hz, bx, H, fill=bg_c, width=1)
        for j in range(rows+1):
            frac = ((j/rows)**1.9)
            y    = hz + frac*(H-hz)
            xl   = vpx - frac*vpx
            xr   = vpx + frac*(W-vpx)
            cv.create_line(xl, y, xr, y, fill=bg_c, width=1)

        # particle web above horizon
        pts_s = [(p[0]*W, p[1]*hz*0.92+6) for p in self._viz_grid_particles]
        for i,(ax,ay) in enumerate(pts_s):
            for j,(bx,by) in enumerate(pts_s):
                if j<=i: continue
                d = math.sqrt((ax-bx)**2+(ay-by)**2)
                if d < W*0.20:
                    alpha = int((1-d/(W*0.20))*(100 if playing else 40))
                    alpha = max(0,min(255,alpha))
                    cv.create_line(ax,ay,bx,by,
                                   fill=f"#{alpha:02x}{alpha:02x}{alpha:02x}", width=1)
        for ax,ay in pts_s:
            r  = 2 if playing else 1
            br = int(120+glow*100) if playing else 50
            br = min(255,br)
            cv.create_oval(ax-r,ay-r,ax+r,ay+r,
                           fill=f"#{br:02x}{br:02x}{br:02x}", outline="")

        # horizon line + pulse
        h_br = int(60+glow*80) if playing else 28
        cv.create_line(0,hz,W,hz, fill=f"#{h_br:02x}{h_br:02x}{h_br:02x}", width=1)
        if playing:
            px = W*((math.sin(t*0.04)*0.5+0.5))
            cv.create_oval(px-4,hz-4,px+4,hz+4, fill="#ffffff", outline="")

        # ── SPOTIFY VIEW ──────────────────────
    def _build_spotify_view(self):
        self.sp_frame = tk.Frame(self.content, bg=C["bg"])

        # Top bar: header + login status
        top = tk.Frame(self.sp_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14,0))
        tk.Label(top, text="SPOTIFY", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.sp_status_lbl = tk.Label(top, text="[ NOT CONNECTED ]",
            font=FMS, fg=C["white3"], bg=C["bg"])
        self.sp_status_lbl.pack(side="left", padx=12)
        self.sp_login_btn = tk.Label(top, text="CONNECT", font=FMS,
            fg=C["white3"], bg=C["bg"], cursor="hand2")
        self.sp_login_btn.pack(side="right", padx=4)
        self.sp_login_btn.bind("<Button-1>", lambda e: self._sp_login())
        self.sp_login_btn.bind("<Enter>",    lambda e: self.sp_login_btn.config(fg=C["white"]))
        self.sp_login_btn.bind("<Leave>",    lambda e: self.sp_login_btn.config(fg=C["white3"]))

        tk.Frame(self.sp_frame, bg=C["border"], height=1).pack(fill="x", padx=0, pady=(8,0))

        # Sub-nav row
        nav = tk.Frame(self.sp_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(8,0))
        self._sp_nav_btns = {}
        for label, key in [("HOME","home"),("LIKED","liked"),("SEARCH","search")]:
            b = tk.Label(nav, text=label, font=FMS, fg=C["white3"],
                         bg=C["bg"], cursor="hand2", padx=10)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._sp_nav(k))
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))
            self._sp_nav_btns[key] = b
        # Device picker button
        dev_btn = tk.Label(nav, text="[ DEVICES ]", font=FMS, fg=C["white3"],
                           bg=C["bg"], cursor="hand2", padx=10)
        dev_btn.pack(side="right")
        dev_btn.bind("<Button-1>", lambda e: self._sp_show_devices())
        dev_btn.bind("<Enter>",    lambda e: dev_btn.config(fg=C["white"]))
        dev_btn.bind("<Leave>",    lambda e: dev_btn.config(fg=C["white3"]))

        # Search bar (hidden until search nav selected)
        self.sp_search_frame = tk.Frame(self.sp_frame, bg=C["bg"])
        tk.Label(self.sp_search_frame, text="⌕", font=("Courier New",12),
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20,4))
        self.sp_search_var = tk.StringVar()
        self.sp_search_entry = tk.Entry(self.sp_search_frame,
            textvariable=self.sp_search_var, font=FM,
            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
            relief="flat", bd=0, width=40)
        self.sp_search_entry.pack(side="left", ipady=4)
        self.sp_search_entry.bind("<Return>", lambda e: (self._sp_do_search(), "break")[1])
        go = tk.Label(self.sp_search_frame, text="[GO]", font=FMS,
                      fg=C["white3"], bg=C["bg"], cursor="hand2", padx=8)
        go.pack(side="left")
        go.bind("<Button-1>", lambda e: self._sp_do_search())

        tk.Frame(self.sp_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6,0))

        # Content label
        self.sp_content_lbl = tk.Label(self.sp_frame, text="",
            font=("Courier New",7,"bold"), fg=C["white3"], bg=C["bg"], anchor="w")
        self.sp_content_lbl.pack(fill="x", padx=20, pady=(8,2))

        # Track list
        lf = tk.Frame(self.sp_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0,4))
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                          width=8, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.sp_list_cv = tk.Canvas(lf, bg=C["bg"], highlightthickness=1,
                                    highlightbackground=C["border"],
                                    yscrollcommand=sb.set)
        self.sp_list_cv.pack(fill="both", expand=True)
        sb.config(command=self.sp_list_cv.yview)
        self.sp_list_cv.bind("<MouseWheel>", lambda e: self.sp_list_cv.yview_scroll(
            int(-1*(e.delta/120))*3, "units"))
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_play_selected)
        self.sp_list_cv.bind("<Button-3>",        self._sp_rclick)
        self.sp_list_cv.bind("<Button-1>",        self._sp_list_click)
        self._sp_row_height   = 64
        self._sp_thumb_cache  = {}   # url -> PhotoImage
        self._sp_selected_idx = -1
        self._sp_list_width   = 0
        self.sp_list_cv.bind("<Configure>", self._sp_list_resize)

        # Now-playing bar at bottom
        np = tk.Frame(self.sp_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.sp_np_lbl = tk.Label(np, text="— SPOTIFY NOT PLAYING —",
            font=("Courier New",8), fg=C["white3"], bg=C["panel"])
        self.sp_np_lbl.pack(side="left", padx=16)
        # controls
        ctrl = tk.Frame(np, bg=C["panel"])
        ctrl.pack(side="right", padx=10)
        for sym, cmd in [("⏮", self._sp_prev),("⏯", self._sp_playpause),("⏭", self._sp_next)]:
            b = tk.Label(ctrl, text=sym, font=("Courier New",11),
                         fg=C["white3"], bg=C["panel"], cursor="hand2", padx=6)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

        # Poll now-playing
        self._sp_np_job = None
        self._sp_playlists_cache = []

    # ── Spotify helpers ──────────────────
    def _sp_nav(self, key):
        self._sp_view = key
        # update nav highlight
        for k, b in self._sp_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        if key == "search":
            self.sp_search_frame.pack(fill="x", pady=(4,0))
        else:
            self.sp_search_frame.pack_forget()
        self._sp_refresh_view()

    def _sp_refresh_view(self):
        if not self.sp_auth.is_authenticated():
            self.sp_status_lbl.config(text="[ NOT CONNECTED ]")
            self.sp_login_btn.config(text="CONNECT")
            self.sp_content_lbl.config(text="Connect your Spotify account to get started.")
            self._sp_clear_list()
            return

        # Check/refresh token
        if not self.sp_auth.token_valid() and self.sp_auth.refresh_token:
            self.sp_auth.refresh(lambda ok, *a: self._sp_refresh_view() if ok else None)
            return

        self.sp_status_lbl.config(text="[ CONNECTED ]", fg=C["white"])
        self.sp_login_btn.config(text="DISCONNECT")

        if self._sp_view == "home":
            self._sp_load_home()
        elif self._sp_view == "liked":
            self._sp_load_liked()
        elif self._sp_view == "search":
            pass  # wait for user input
        # start now-playing poll
        if self._sp_np_job is None:
            self._sp_poll_np()

    def _sp_load_home(self):
        self.sp_content_lbl.config(text="YOUR PLAYLISTS")
        self._sp_clear_list()
        self._sp_status_msg("Loading...")
        self._sp_tracks = []
        def _fetch():
            data = self.sp_api.playlists(50)
            if not data:
                self.root.after(0, lambda: self._sp_clear_list())
                return
            items = data.get("items", [])
            self._sp_playlists_cache = items
            self.root.after(0, lambda: self._sp_show_playlists(items))
        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_show_playlists(self, items):
        self._sp_clear_list()
        self._sp_tracks = []
        self._sp_selected_idx = -1
        cv  = self.sp_list_cv
        RH  = self._sp_row_height
        W   = max(self._sp_list_width, cv.winfo_width(), 400)
        cv.configure(scrollregion=(0, 0, W, RH * len(items)))
        for i, pl in enumerate(items):
            name  = pl.get("name","?")
            count = pl.get("tracks",{}).get("total",0)
            y0, y1 = i*RH, (i+1)*RH
            tag = f"row{i}"
            bg = C["panel2"] if i%2==0 else C["bg"]
            cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)
            cv.create_text(16, y0+RH//2-7, text=name[:60],
                           font=("Courier New",9,"bold"), fill=C["white"],
                           anchor="w", tags=tag)
            cv.create_text(16, y0+RH//2+7, text=f"{count} tracks",
                           font=("Courier New",8), fill=C["white3"],
                           anchor="w", tags=tag)
            cv.create_line(0, y1-1, W, y1-1, fill=C["border"], tags=tag)
        # double-click opens playlist (only while playlists are shown)
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_open_playlist)
    

    def _sp_open_playlist(self, event=None):
        idx = self._sp_selected_idx
        if idx < 0 or idx >= len(self._sp_playlists_cache): return
        pl  = self._sp_playlists_cache[idx]
        pl_id = pl["id"]
        pl_name = pl.get("name","?")
        self.sp_content_lbl.config(text=f"▸ {pl_name.upper()}")
        self._sp_clear_list()
        self._sp_status_msg("Loading...")
        
        def _fetch():
            tracks = []
            offset = 0
            while True:
                data = self.sp_api.playlist_tracks(pl_id, limit=50, offset=offset)
                if not data: break
                items = data.get("items",[])
                for it in items:
                    t = it.get("track")
                    if t and t.get("uri"):
                        tracks.append(t)
                offset += len(items)
                if offset >= data.get("total",0) or not items: break
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))
        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_load_liked(self):
        self.sp_content_lbl.config(text="LIKED SONGS")
        self._sp_clear_list()
        self._sp_status_msg("Loading...")
        
        def _fetch():
            tracks = []
            offset = 0
            while len(tracks) < 200:
                data = self.sp_api.liked_songs(limit=50, offset=offset)
                if not data: break
                items = data.get("items",[])
                for it in items:
                    t = it.get("track")
                    if t and t.get("uri"):
                        tracks.append(t)
                offset += len(items)
                if not items: break
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))
        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_do_search(self):
        q = self.sp_search_var.get().strip()
        if not q: return
        if not self.sp_auth.is_authenticated():
            self._sp_status_msg("[ Not connected — click CONNECT first ]")
            return
        self.sp_content_lbl.config(text=f'SEARCH: "{q}"')
        self._sp_clear_list()
        self._sp_status_msg("Searching...")

        def _fetch():
            # Diagnose token state before searching
            auth = self.sp_auth
            has_token   = bool(auth.access_token)
            token_valid = auth.token_valid()
            has_refresh = bool(auth.refresh_token)
            expires_in  = int(auth.expires_at - time.time()) if auth.expires_at else 0

            if not has_token and not has_refresh:
                self.root.after(0, lambda: self._sp_status_msg(
                    "[ Not logged in — please DISCONNECT and reconnect ]"))
                return
            if not token_valid and not has_refresh:
                self.root.after(0, lambda: self._sp_status_msg(
                    "[ Token expired and no refresh token — please reconnect ]"))
                return

            data = self.sp_api.search(q, limit=20)
            if not data:
                err = getattr(self.sp_api, "_last_error", None)
                if err:
                    msg = f"[ Search failed: {err} ]"
                else:
                    # Extra diagnostics
                    msg = (f"[ Search returned nothing — "
                           f"token={'ok' if token_valid else 'expired'}, "
                           f"refresh={'yes' if has_refresh else 'no'}, "
                           f"expires_in={expires_in}s, "
                           f"client_id={'set' if SPOTIFY_CLIENT_ID else 'MISSING'} ]")
                self.root.after(0, lambda m=msg: self._sp_status_msg(m))
                return
            tracks = [it for it in data.get("tracks", {}).get("items", []) if it and it.get("uri")]
            if not tracks:
                self.root.after(0, lambda: self._sp_status_msg("[ No tracks found ]"))
                return
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))
        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_clear_list(self):
        if hasattr(self, "sp_list_cv"):
            self.sp_list_cv.delete("all")
            self.sp_list_cv.configure(scrollregion=(0,0,100,40))
        self._sp_thumb_cache  = {}
        self._sp_selected_idx = -1

    def _sp_status_msg(self, msg):
        cv = self.sp_list_cv
        cv.delete("all")
        cv.create_text(20, 20, text=msg, anchor="nw", font=FM, fill=C["white3"])
        cv.configure(scrollregion=(0,0,100,40))

    def _sp_show_tracks(self, tracks):
        self._sp_tracks = tracks
        self._sp_selected_idx = -1
        self._sp_thumb_cache  = {}
        # Restore play binding (may have been overridden by playlist view)
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_play_selected)
        self._sp_render_list()
        # kick off thumbnail fetches
        for i, t in enumerate(tracks):
            images = t.get("album", {}).get("images", [])
            url = None
            for img in sorted(images, key=lambda x: x.get("width", 9999)):
                if img.get("width", 0) >= 48:
                    url = img.get("url")
                    break
            if not url and images:
                url = images[-1].get("url")
            if url:
                threading.Thread(target=self._sp_fetch_thumb,
                                 args=(i, url), daemon=True).start()

    def _sp_fetch_thumb(self, idx, url):
        try:
            import urllib.request as _ur, tempfile, os
            data   = _ur.urlopen(url, timeout=6).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp    = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data); tmp.close()
            self.root.after(0, lambda p=tmp.name, i=idx: self._sp_load_thumb(i, p))
        except Exception:
            pass

    def _sp_load_thumb(self, idx, path):
        try:
            import tkinter as _tk
            RH = self._sp_row_height - 8
            try:
                img = _tk.PhotoImage(file=path)
                iw, ih = img.width(), img.height()
                factor = max(1, max(iw, ih) // RH)
                img = img.subsample(factor, factor)
            except Exception:
                from PIL import Image, ImageTk
                img = Image.open(path).resize((RH, RH))
                img = ImageTk.PhotoImage(img)
            self._sp_thumb_cache[idx] = img
            self._sp_redraw_row(idx)
        except Exception:
            pass
        finally:
            try:
                import os; os.unlink(path)
            except Exception:
                pass

    def _sp_render_list(self):
        cv   = self.sp_list_cv
        cv.delete("all")
        if not hasattr(self, "_sp_tracks") or not self._sp_tracks:
            cv.create_text(20, 20, text="No tracks loaded.", anchor="nw",
                           font=FM, fill=C["white3"])
            cv.configure(scrollregion=(0, 0, 100, 40))
            return
        RH = self._sp_row_height
        W  = max(self._sp_list_width, cv.winfo_width(), 400)
        total_h = RH * len(self._sp_tracks)
        cv.configure(scrollregion=(0, 0, W, total_h))
        for i, t in enumerate(self._sp_tracks):
            self._sp_draw_row(i, t, W)
        cv.update_idletasks()
        cv.update_idletasks()

    def _sp_draw_row(self, i, t, W):
        cv  = self.sp_list_cv
        RH  = self._sp_row_height
        y0  = i * RH
        y1  = y0 + RH
        tag = f"row{i}"
        cv.delete(tag)

        bg = C["select"] if i == self._sp_selected_idx else (C["panel2"] if i%2==0 else C["bg"])
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)

        TH = RH - 8
        cv.create_rectangle(4, y0+4, 4+TH, y1-4,
                            fill=C["panel"], outline=C["border"], tags=tag)
        if i in self._sp_thumb_cache:
            photo = self._sp_thumb_cache[i]
            cx = 4 + TH//2
            cy = y0 + RH//2
            cv.create_image(cx, cy, image=photo, anchor="center", tags=tag)
        else:
            cv.create_text(4 + TH//2, y0 + RH//2, text="o",
                           font=("Courier New", 12), fill=C["white3"],
                           anchor="center", tags=tag)

        tx = 4 + TH + 8
        cv.create_text(tx, y0 + RH//2, text=f"{i+1:>3}.",
                       font=("Courier New", 8), fill=C["white3"],
                       anchor="w", tags=tag)

        title  = t.get("name", "?")
        artists = t.get("artists", [])
        artist = ", ".join(a["name"] for a in artists)
        album  = t.get("album", {}).get("name", "")
        dur_ms = t.get("duration_ms", 0)
        dur_s  = dur_ms // 1000
        dur_str = f"{dur_s//60}:{dur_s%60:02d}"
        tx2 = tx + 36
        # Title row
        cv.create_text(tx2, y0 + 14, text=title[:70],
                       font=("Courier New", 9, "bold"), fill=C["white"],
                       anchor="w", tags=tag)
        # Artist row
        cv.create_text(tx2, y0 + 32, text=artist[:70],
                       font=("Courier New", 8), fill=C["white2"],
                       anchor="w", tags=tag)
        # Album row
        cv.create_text(tx2, y0 + 48, text=album[:70],
                       font=("Courier New", 7), fill=C["white3"],
                       anchor="w", tags=tag)

        cv.create_text(W - 12, y0 + RH//2, text=dur_str,
                       font=("Courier New", 8), fill=C["white3"],
                       anchor="e", tags=tag)

        cv.create_line(0, y1-1, W, y1-1, fill=C["border"], tags=tag)

    def _sp_redraw_row(self, idx):
        if not hasattr(self, "_sp_tracks") or idx >= len(self._sp_tracks):
            return
        W = max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        self._sp_draw_row(idx, self._sp_tracks[idx], W)

    def _sp_list_resize(self, event):
        self._sp_list_width = event.width
        self._sp_render_list()

    def _sp_list_click(self, event):
        RH  = self._sp_row_height
        idx = int(self.sp_list_cv.canvasy(event.y) // RH)
        if not hasattr(self, "_sp_tracks") or idx >= len(self._sp_tracks):
            return
        old = self._sp_selected_idx
        self._sp_selected_idx = idx
        W   = max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        if old >= 0:
            self._sp_redraw_row(old)
        self._sp_redraw_row(idx)

    def _sp_play_selected(self, event=None):
        idx = self._sp_selected_idx
        if idx < 0 or not self._sp_tracks: return
        if idx >= len(self._sp_tracks): return
        uris = [t["uri"] for t in self._sp_tracks]
        self._sp_play_with_device(uris, idx)

    def _sp_play_with_device(self, uris, idx):
        """Fetch devices, pick one, then play. Retries a few times so the
        Spotify desktop app has time to register itself as an active device."""
        # Stop any local/YT/SC playback immediately before handing off to Spotify
        self._stop_all_sources()
        self._active_source = "spotify"
        self._sp_mode = True
        def _do():
            import time as _t
            devices = []
            for attempt in range(6):          # try up to ~5 seconds
                data    = self.sp_api.devices()
                devices = (data or {}).get("devices", [])
                if devices:
                    break
                _t.sleep(0.9)

            active = [d for d in devices if d.get("is_active")]
            if active:
                dev_id = active[0]["id"]
                self.sp_api.play_on(dev_id, uris=uris, offset={"position": idx})
            elif devices:
                # Transfer to first available device then play
                dev_id = devices[0]["id"]
                self.sp_api.transfer(dev_id, play=False)
                _t.sleep(0.8)
                self.sp_api.play_on(dev_id, uris=uris, offset={"position": idx})
            else:
                self.root.after(0, self._sp_no_device_error)
        threading.Thread(target=_do, daemon=True).start()

    def _sp_no_device_error(self):
        messagebox.showwarning("OTERNOS // SPOTIFY",
            "No active Spotify device found." + chr(10) + chr(10) +
            "Open Spotify on your phone, PC, or any device first," + chr(10) +
            "then try playing again.")

    def _sp_rclick(self, event):
        RH  = self._sp_row_height
        sel = int(self.sp_list_cv.canvasy(event.y) // RH)
        old = self._sp_selected_idx
        self._sp_selected_idx = sel
        if old >= 0: self._sp_redraw_row(old)
        self._sp_redraw_row(sel)
        if sel >= len(self._sp_tracks): return
        track = self._sp_tracks[sel]
        m = tk.Menu(self.root, tearoff=0, bg=C["panel"], fg=C["white"],
                    font=FM, bd=0, relief="flat",
                    activebackground=C["select"], activeforeground=C["white"])
        m.add_command(label="▶  Play Now",
                      command=lambda: self._sp_play_selected())
        m.add_command(label="＋  Add to Local Library",
                      command=lambda: self._sp_add_to_local(track))
        try: m.tk_popup(event.x_root, event.y_root)
        finally: m.grab_release()

    def _sp_add_to_local(self, track):
        title  = track.get("name","?")
        artist = ", ".join(a["name"] for a in track.get("artists",[]))
        note   = "Spotify tracks cannot be downloaded. Play them via the Spotify tab while Spotify is open."
        msg    = title + " by " + artist + chr(10) + chr(10) + note
        messagebox.showinfo("OTERNOS // SPOTIFY", msg)

    def _sp_playpause(self):
        def _do():
            np = self.sp_api.now_playing()
            if np and np.get("is_playing"):
                self.sp_api.pause()
            else:
                self.sp_api.play()
        threading.Thread(target=_do, daemon=True).start()

    def _sp_next(self):
        threading.Thread(target=self.sp_api.next_track, daemon=True).start()

    def _sp_prev(self):
        threading.Thread(target=self.sp_api.prev_track, daemon=True).start()

    def _sp_poll_np(self):
        """Poll Spotify now-playing every 2 seconds, sync into main player bar.
        Keeps running regardless of which tab is active."""
        if not self.sp_auth.is_authenticated():
            self._sp_np_job = None
            return
        def _fetch():
            if not self.sp_auth.token_valid(): return
            np = self.sp_api.now_playing()
            if np and np.get("item"):
                t        = np["item"]
                title    = t.get("name","?")
                artist   = ", ".join(a["name"] for a in t.get("artists",[]))
                is_play  = np.get("is_playing", False)
                pos_ms   = np.get("progress_ms", 0) or 0
                dur_ms   = t.get("duration_ms", 0) or 0
                dev      = (np.get("device") or {}).get("name","")
                dev_s    = ("  //  " + dev[:20]) if dev else ""
                sym      = "▶" if is_play else "⏸"
                sp_lbl   = sym + "  " + title[:38] + "  —  " + artist[:24] + dev_s
                # grab smallest image that's still at least 64px
                images   = t.get("album", {}).get("images", [])
                art_url  = None
                for img in sorted(images, key=lambda x: x.get("width", 0)):
                    if img.get("width", 0) >= 64:
                        art_url = img.get("url")
                        break
                if not art_url and images:
                    art_url = images[-1].get("url")

                # Push into main player bar — only if Spotify is actually playing
                def _update():
                    self._sp_pos_ms  = pos_ms
                    self._sp_dur_ms  = dur_ms
                    self._sp_playing = is_play
                    self.sp_np_lbl.config(text=sp_lbl)
                    # Only take over the main bar if:
                    #   - Spotify is already the active source, OR
                    #   - No local playback is happening at all
                    local_active = (self.engine.is_playing or self.engine.is_paused
                                    or self._active_source in ("library", "youtube", "soundcloud"))
                    if is_play and self._active_source == "spotify":
                        pass  # already spotify — always update
                    elif is_play and not local_active and self._active_source == "none":
                        pass  # nothing local running — spotify can take over
                    else:
                        return  # local/YT/SC is active — don't hijack
                    self._sp_mode = True
                    self._active_source = "spotify"
                    self._set_source_badge("spotify")
                    t_disp = (title[:36]+"…") if len(title)>37 else title
                    self.now_title.config(text=t_disp)
                    self.now_artist.config(text=artist)
                    self.lbl_tot.config(text=self._fmt(dur_ms/1000))
                    self.btn_play.config(text="⏸")
                    self.wavevis.set_active(True)
                    self.status_lbl.config(text="[ SPOTIFY ]")
                    if art_url:
                        self._set_album_art(art_url)
                    # History
                    last = self._history[-1] if self._history else {}
                    if is_play and last.get("title") != title:
                        self._history_add({"title": title, "artist": artist, "album": ""}, source="spotify")
                self.root.after(0, _update)
            else:
                devs  = (self.sp_api.devices() or {}).get("devices", [])
                if devs:
                    names = ", ".join(d.get("name","?") for d in devs[:3])
                    lbl   = "⏸  No track playing  //  devices: " + names
                else:
                    lbl   = "— NO SPOTIFY DEVICE FOUND — open Spotify on a device —"
                self.root.after(0, lambda: self.sp_np_lbl.config(text=lbl))
                self.root.after(0, self._draw_art_placeholder)
        threading.Thread(target=_fetch, daemon=True).start()
        self._sp_np_job = self.root.after(2000, self._sp_poll_np)

    def _sp_show_devices(self):
        def _do():
            data    = self.sp_api.devices()
            devices = (data or {}).get("devices", [])
            if not devices:
                self.root.after(0, lambda: messagebox.showwarning(
                    "OTERNOS // SPOTIFY DEVICES",
                    "No Spotify devices found." + chr(10) + chr(10) +
                    "Make sure Spotify is open and playing on at least one device."))
                return
            lines = ["AVAILABLE DEVICES", ""]
            for d in devices:
                active = " [ACTIVE]" if d.get("is_active") else ""
                lines.append(d.get("name","?") + "  //  " + d.get("type","?") + active)
            self.root.after(0, lambda: messagebox.showinfo(
                "OTERNOS // SPOTIFY DEVICES", chr(10).join(lines)))
        threading.Thread(target=_do, daemon=True).start()

    def _sp_login(self):
        if self.sp_auth.is_authenticated():
            # Disconnect
            self.sp_auth.access_token  = None
            self.sp_auth.refresh_token = None
            self.sp_auth.expires_at    = 0
            try: Path(SpotifyAuth.TOKEN_FILE).unlink()
            except: pass
            self.sp_status_lbl.config(text="[ NOT CONNECTED ]", fg=C["white3"])
            self.sp_login_btn.config(text="CONNECT")
            self._sp_clear_list()
            return

        url = self.sp_auth.get_auth_url()
        self.sp_status_lbl.config(text="[ WAITING FOR LOGIN... ]")

        def on_code(code):
            self.sp_auth.exchange_code(code, callback=self._sp_on_auth)

        self.sp_auth.start_callback_server(on_code)
        webbrowser.open(url)

    def _sp_on_auth(self, ok, err=None):
        if ok:
            self.root.after(0, self._sp_refresh_view)
        else:
            self.root.after(0, lambda: self.sp_status_lbl.config(
                text=f"[ AUTH FAILED ]", fg=C["red"]))

    # ── SOUNDCLOUD VIEW ───────────────────
    def _build_soundcloud_view(self):
        self.sc_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.sc_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="SOUNDCLOUD", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.sc_status_lbl = tk.Label(top, text="[ PUBLIC ACCESS ]",
            font=FMS, fg=C["white3"], bg=C["bg"])
        self.sc_status_lbl.pack(side="left", padx=12)

        # Auth row (token for likes)
        auth_row = tk.Frame(self.sc_frame, bg=C["bg"])
        auth_row.pack(fill="x", padx=20, pady=(2, 0))
        tk.Label(auth_row, text="OAuth Token (for Likes):", font=FMS,
                 fg=C["white3"], bg=C["bg"]).pack(side="left")
        self.sc_token_var = tk.StringVar(value=self.sc_api.oauth_token or "")
        sc_tok_entry = tk.Entry(auth_row, textvariable=self.sc_token_var, font=FMS,
            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
            relief="flat", bd=0, width=36, show="*")
        sc_tok_entry.pack(side="left", padx=8, ipady=3)
        sc_save = tk.Label(auth_row, text="[SAVE]", font=FMS, fg=C["white3"],
                           bg=C["bg"], cursor="hand2")
        sc_save.pack(side="left")
        sc_save.bind("<Button-1>", lambda e: self._sc_save_token())
        sc_save.bind("<Enter>",    lambda e: sc_save.config(fg=C["white"]))
        sc_save.bind("<Leave>",    lambda e: sc_save.config(fg=C["white3"]))
        tk.Label(auth_row, text="  (get it from sc-inspector or browser devtools)",
                 font=("Courier New", 7), fg=C["white3"], bg=C["bg"]).pack(side="left")

        tk.Frame(self.sc_frame, bg=C["border"], height=1).pack(fill="x", padx=0, pady=(8, 0))

        # Sub-nav
        nav = tk.Frame(self.sc_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(8, 0))
        self._sc_nav_btns = {}
        for label, key in [("SEARCH", "search"), ("LIKES", "likes"), ("FAVORITES", "favorites")]:
            b = tk.Label(nav, text=label, font=FMS, fg=C["white3"],
                         bg=C["bg"], cursor="hand2", padx=10)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._sc_nav(k))
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))
            self._sc_nav_btns[key] = b

        # Search bar
        self.sc_search_frame = tk.Frame(self.sc_frame, bg=C["bg"])
        self.sc_search_frame.pack(fill="x", pady=(4, 0))
        tk.Label(self.sc_search_frame, text="⌕", font=("Courier New", 12),
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.sc_search_var = tk.StringVar()
        sc_entry = tk.Entry(self.sc_search_frame, textvariable=self.sc_search_var,
            font=FM, bg=C["panel"], fg=C["white"], insertbackground=C["white"],
            relief="flat", bd=0, width=40)
        sc_entry.pack(side="left", ipady=4)
        sc_entry.bind("<Return>", lambda e: (self._sc_do_search(), "break")[1])
        sc_go = tk.Label(self.sc_search_frame, text="[GO]", font=FMS,
                         fg=C["white3"], bg=C["bg"], cursor="hand2", padx=8)
        sc_go.pack(side="left")
        sc_go.bind("<Button-1>", lambda e: self._sc_do_search())

        tk.Frame(self.sc_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        self.sc_content_lbl = tk.Label(self.sc_frame, text="Search for tracks above",
            font=("Courier New", 7, "bold"), fg=C["white3"], bg=C["bg"], anchor="w")
        self.sc_content_lbl.pack(fill="x", padx=20, pady=(8, 2))

        lf = tk.Frame(self.sc_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                          width=8, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.sc_list = tk.Listbox(lf, bg=C["bg"], fg=C["white2"],
            selectbackground=C["select"], selectforeground=C["white"],
            font=FM, relief="flat", bd=0, activestyle="none",
            yscrollcommand=sb.set,
            highlightthickness=1, highlightcolor=C["border"],
            highlightbackground=C["border"])
        self.sc_list.pack(fill="both", expand=True)
        sb.config(command=self.sc_list.yview)
        self.sc_list.bind("<Double-Button-1>", self._sc_play_selected)
        self.sc_list.bind("<MouseWheel>", lambda e: self.sc_list.yview_scroll(int(-1*(e.delta/120))*3, "units"))
        self.sc_list.bind("<Button-3>", self._sc_right_click)

        # Right-click context menu
        self._sc_ctx = tk.Menu(self.sc_frame, tearoff=0,
            bg=C["panel"], fg=C["white"], activebackground=C["select2"],
            activeforeground=C["glow"], font=FMS, bd=0, relief="flat")
        self._sc_ctx.add_command(label="\u25b6  Play",            command=self._sc_ctx_play)
        self._sc_ctx.add_separator()
        self._sc_ctx.add_command(label="\u2665  Add to Favorites", command=self._sc_ctx_favorite)
        self._sc_ctx.add_command(label="\u2715  Remove from Favorites", command=self._sc_ctx_unfavorite)

        # Now-playing bar
        np = tk.Frame(self.sc_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.sc_np_lbl = tk.Label(np, text="— SOUNDCLOUD —",
            font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.sc_np_lbl.pack(side="left", padx=16)

    def _sc_save_token(self):
        tok = self.sc_token_var.get().strip()
        self.sc_api.oauth_token = tok or None
        self.sc_api._save_token()
        self.sc_status_lbl.config(
            text="[ AUTHENTICATED ]" if tok else "[ PUBLIC ACCESS ]",
            fg=C["white"] if tok else C["white3"])

    def _sc_nav(self, key):
        self._sc_view = key
        for k, b in self._sc_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        if key == "search":
            self.sc_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.sc_search_frame.pack_forget()
        self._sc_refresh_view()

    def _sc_refresh_view(self):
        tok = self.sc_api.oauth_token
        cid = bool(self.sc_api.client_id)
        if tok:
            status, col = "[ AUTHENTICATED ]", C["white"]
        elif cid:
            status, col = "[ PUBLIC ACCESS ]", C["white3"]
        else:
            status, col = "[ CONNECTING... ]", C["white3"]
        self.sc_status_lbl.config(text=status, fg=col)
        if self._sc_view == "likes":
            self._sc_load_likes()
        elif self._sc_view == "favorites":
            self._sc_nav_favorites()

    def _sc_do_search(self):
        q = self.sc_search_var.get().strip()
        if not q:
            return
        self.sc_content_lbl.config(text=f'SEARCH: "{q}"')
        self.sc_list.delete(0, "end")
        self.sc_list.insert("end", "  Searching...")
        self._sc_tracks = []
        def _fetch():
            # If client_id not yet available, try to fetch it now
            if not self.sc_api.client_id:
                self.root.after(0, lambda: [self.sc_list.delete(0, "end"),
                    self.sc_list.insert("end", "  Fetching SoundCloud credentials...")])
                self.sc_api.refresh_client_id()
                if not self.sc_api.client_id:
                    self.root.after(0, lambda: [self.sc_list.delete(0, "end"),
                        self.sc_list.insert("end",
                            "  Could not connect to SoundCloud. Check your internet connection.")])
                    return
            tracks = self.sc_api.search(q, limit=40)
            self._sc_tracks = tracks
            self.root.after(0, lambda: self._sc_show_tracks(tracks,
                f'RESULTS FOR "{q.upper()}"'))
        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_load_likes(self):
        if not self.sc_api.oauth_token:
            self.sc_list.delete(0, "end")
            self.sc_list.insert("end", "  Enter your OAuth token above to load likes.")
            return
        self.sc_content_lbl.config(text="YOUR LIKES")
        self.sc_list.delete(0, "end")
        self.sc_list.insert("end", "  Loading likes...")
        self._sc_tracks = []
        def _fetch():
            tracks = self.sc_api.likes(limit=100)
            self._sc_tracks = tracks
            self.root.after(0, lambda: self._sc_show_tracks(tracks, "YOUR LIKES"))
        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_show_tracks(self, tracks, label=""):
        self.sc_list.delete(0, "end")
        if label:
            self.sc_content_lbl.config(text=label)
        if not tracks:
            self.sc_list.insert("end", "  No results.")
            return
        fav_ids = {t.get("id") for t in self._sc_favorites}
        for i, t in enumerate(tracks):
            title   = (t.get("title") or "?")[:38]
            artist  = (t.get("user", {}).get("username") or "?")[:26]
            dur_ms  = t.get("duration", 0)
            dur_s   = dur_ms // 1000
            dur_str = f"{dur_s//60}:{dur_s%60:02d}"
            heart   = " ♥" if t.get("id") in fav_ids else "  "
            self.sc_list.insert("end",
                f"{heart} {i+1:>3}.  {title:<38}  {artist:<26}  {dur_str}")

    # ── FAVORITES ─────────────────────
    def _sc_nav_favorites(self):
        self._sc_tracks = list(self._sc_favorites)
        self._sc_show_tracks(self._sc_tracks, f"FAVORITES  ({len(self._sc_favorites)})")

    def _sc_right_click(self, event):
        idx = self.sc_list.nearest(event.y)
        if idx < 0 or idx >= len(self._sc_tracks):
            return
        self.sc_list.selection_clear(0, "end")
        self.sc_list.selection_set(idx)
        track  = self._sc_tracks[idx]
        fav_ids = {t.get("id") for t in self._sc_favorites}
        already = track.get("id") in fav_ids
        self._sc_ctx.entryconfig("♥  Add to Favorites",
                                  state="disabled" if already else "normal")
        self._sc_ctx.entryconfig("✕  Remove from Favorites",
                                  state="normal" if already else "disabled")
        try:
            self._sc_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._sc_ctx.grab_release()

    def _sc_ctx_play(self):
        idx = self.sc_list.curselection()
        if not idx: return
        track = self._sc_tracks[idx[0]]
        import threading
        threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_ctx_favorite(self):
        idx = self.sc_list.curselection()
        if not idx: return
        track   = self._sc_tracks[idx[0]]
        fav_ids = {t.get("id") for t in self._sc_favorites}
        if track.get("id") not in fav_ids:
            self._sc_favorites.append(track)
            self._save()
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        self.sc_np_lbl.config(text=f"  ♥  Added: {(track.get('title') or '')[:40]}")

    def _sc_ctx_unfavorite(self):
        idx = self.sc_list.curselection()
        if not idx: return
        track = self._sc_tracks[idx[0]]
        self._sc_favorites = [
            t for t in self._sc_favorites if t.get("id") != track.get("id")]
        self._save()
        if self._sc_view == "favorites":
            self._sc_tracks = list(self._sc_favorites)
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        self.sc_np_lbl.config(text=f"  Removed: {(track.get('title') or '')[:40]}")

    def _stop_all_sources(self):
        """Stop all audio sources — Spotify, local engine, SoundCloud, YouTube."""
        self._active_source = "none"  # block Spotify poll from taking over
        self._sp_mode    = False
        self._sp_playing = False
        # Reset art cache so next source always gets its thumbnail displayed
        self._art_url_last = None
        # Pause Spotify in background — don't block the calling thread
        try:
            threading.Thread(target=self.sp_api.pause, daemon=True).start()
        except Exception:
            pass
        # Stop local engine (covers SoundCloud + YouTube + library)
        self.engine.stop()

    def _sc_play_selected(self, event=None):
        sel = self.sc_list.curselection()
        if not sel or not self._sc_tracks:
            return
        idx = sel[0]
        if idx >= len(self._sc_tracks):
            return
        track = self._sc_tracks[idx]
        threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_stream(self, track):
        """Resolve stream URL and play via MCI."""
        # Update status to show we're working
        self.root.after(0, lambda: self.sc_np_lbl.config(text="  Resolving stream..."))

        stream_url = self.sc_api.get_stream_url(track)

        # If failed and client_id might be stale, refresh and retry once
        if not stream_url and not SoundCloudAPI._cached_cid:
            self.root.after(0, lambda: self.sc_np_lbl.config(text="  Refreshing client ID..."))
            if self.sc_api.refresh_client_id():
                stream_url = self.sc_api.get_stream_url(track)

        if not stream_url:
            self.root.after(0, lambda: (
                self.sc_np_lbl.config(text="  — SOUNDCLOUD —"),
                messagebox.showwarning(
                    "OTERNOS // SOUNDCLOUD",
                    "Could not get stream URL.\n\n"
                    "The track may not be streamable, or SoundCloud\n"
                    "has changed their API. Try again in a moment.")))
            return

        # Download to temp file (MCI needs a local file or direct MP3 URL)
        import tempfile, urllib.request as _ur
        try:
            self.root.after(0, lambda: self.sc_np_lbl.config(text="  Buffering..."))
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            _ur.urlretrieve(stream_url, tmp.name)
            title  = track.get("title", "Unknown")
            artist = track.get("user", {}).get("username", "Unknown")
            dur_s  = track.get("duration", 0) // 1000
            def _play():
                self._stop_all_sources()
                # Claim source immediately to block Spotify poll race
                self._active_source = "soundcloud"
                self._sp_mode = False
                self._set_source_badge("soundcloud")
                if self.engine.load(tmp.name):
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text="SoundCloud")
                    self.engine.duration = float(dur_s)
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=f"{dur_s//60}:{dur_s%60:02d}")
                    self._draw_prog(0)
                    self.sc_np_lbl.config(
                        text=f"▶  {title[:40]}  —  {artist[:24]}")
                    # Set SoundCloud artwork — _art_url_last cleared by _stop_all_sources
                    art_url = track.get("artwork_url") or ""
                    if art_url:
                        self._set_album_art(art_url.replace("-large", "-t500x500"))
                    self._history_add({"title": title, "artist": artist, "album": "SoundCloud"}, source="soundcloud")
            self.root.after(0, _play)
        except Exception as ex:
            self.root.after(0, lambda: messagebox.showwarning(
                "OTERNOS // SOUNDCLOUD", f"Stream error:\n{ex}"))

    # ── YOUTUBE VIEW ──────────────────────
    def _build_youtube_view(self):
        self.yt_frame = tk.Frame(self.content, bg=C["bg"])

        # Header
        top = tk.Frame(self.yt_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="YOUTUBE", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.yt_status_lbl = tk.Label(top, text="", font=FMS, fg=C["white3"], bg=C["bg"])
        self.yt_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.yt_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Search bar (named so we can hide it in SAVED view)
        sf = tk.Frame(self.yt_frame, bg=C["bg"])
        self.yt_search_frame = sf
        sf.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(sf, text="⌕", font=("Courier New", 11), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(0, 6))
        self.yt_search_var = tk.StringVar()
        self.yt_search_entry = tk.Entry(sf, textvariable=self.yt_search_var, font=FM,
            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
            relief="flat", bd=0, width=44)
        self.yt_search_entry.pack(side="left", ipady=4)
        self.yt_search_entry.bind("<Return>", lambda e: (self._yt_do_search(), "break")[1])
        go = tk.Label(sf, text="GO", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=10)
        go.pack(side="left")
        go.bind("<Button-1>", lambda e: self._yt_do_search())
        go.bind("<Enter>",    lambda e: go.config(fg=C["white"]))
        go.bind("<Leave>",    lambda e: go.config(fg=C["white3"]))
        tk.Frame(self.yt_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        # Status / now-playing — pack bottom FIRST
        self.yt_np_lbl = tk.Label(self.yt_frame, text="",
            font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.yt_np_lbl.pack(side="bottom", fill="x", padx=20, pady=(0, 6))

        self.yt_content_lbl = tk.Label(self.yt_frame, text="Search for music above",
            font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.yt_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        # Loading bar + cancel button — hidden until a track is loading
        self._yt_load_bar_frame = tk.Frame(self.yt_frame, bg=C["bg"])
        self._yt_load_bar_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._yt_load_canvas = tk.Canvas(self._yt_load_bar_frame,
            height=3, bg=C["panel"], highlightthickness=0)
        self._yt_load_canvas.pack(side="left", fill="x", expand=True)
        self._yt_cancel_btn = tk.Label(self._yt_load_bar_frame, text="✕ cancel",
            font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=8)
        self._yt_cancel_btn.pack(side="right")
        self._yt_cancel_btn.bind("<Button-1>", lambda e: self._yt_cancel())
        self._yt_cancel_btn.bind("<Enter>",    lambda e: self._yt_cancel_btn.config(fg=C["red"]))
        self._yt_cancel_btn.bind("<Leave>",    lambda e: self._yt_cancel_btn.config(fg=C["white3"]))
        self._yt_load_bar_frame.pack_forget()  # hidden by default
        self._yt_load_anim_pos  = 0.0
        self._yt_load_anim_job  = None
        self._yt_cancelled      = False
        self._yt_subview        = "search"
        self._yt_dropdown       = None

        # Canvas list — supports thumbnails
        lf = tk.Frame(self.yt_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb2 = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0)
        sb2.pack(side="right", fill="y")
        self.yt_list_cv = tk.Canvas(lf, bg=C["bg"], highlightthickness=0,
            yscrollcommand=sb2.set)
        self.yt_list_cv.pack(side="left", fill="both", expand=True)
        sb2.config(command=self.yt_list_cv.yview)
        self.yt_list_cv.bind("<MouseWheel>", lambda e:
            self.yt_list_cv.yview_scroll(int(-1*(e.delta/120))*3, "units"))
        self.yt_list_cv.bind("<Double-Button-1>", self._yt_play_selected)
        self.yt_list_cv.bind("<Button-3>",        self._yt_rclick)
        self.yt_list_cv.bind("<Button-1>",        self._yt_list_click)
        self.yt_list_cv.bind("<Configure>",       self._yt_list_resize)
        self._yt_row_height   = 52
        self._yt_thumb_cache  = {}
        self._yt_selected_idx = -1
        self._yt_list_width   = 0
        # Keep yt_list as alias for legacy references (e.g. scroll routing)
        self.yt_list = self.yt_list_cv

    def _yt_refresh_view(self):
        if not self.yt_api.ytdlp_available():
            self.yt_status_lbl.config(
                text="yt-dlp not installed  —  run:  pip install yt-dlp", fg=C["red"])
            self.yt_hint_lbl_ref = None
        else:
            self.yt_status_lbl.config(text="", fg=C["white3"])

    def _yt_cancel(self):
        """Cancel the current YouTube download."""
        self._yt_cancelled = True
        self._yt_load_stop()
        self.yt_content_lbl.config(text="Download cancelled.")

    def _yt_load_start(self):
        """Show and animate the YouTube loading bar."""
        self._yt_cancelled = False
        self._yt_load_bar_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._yt_load_anim_pos = 0.0
        self._yt_load_anim_running = True
        self._yt_load_progress = -1  # -1 = pulse mode, 0-1 = real progress
        self._yt_animate_load()

    def _yt_set_load_progress(self, ratio):
        """Switch loading bar from pulse to real progress fill (0.0 - 1.0)."""
        self._yt_load_progress = max(0.0, min(1.0, ratio))
        self._yt_load_anim_running = False  # stop the pulse loop
        if self._yt_load_anim_job:
            self.root.after_cancel(self._yt_load_anim_job)
            self._yt_load_anim_job = None
        # Draw the real progress bar immediately
        w = self._yt_load_canvas.winfo_width() or 400
        fill_w = int(w * self._yt_load_progress)
        self._yt_load_canvas.delete("all")
        self._yt_load_canvas.create_rectangle(0, 0, w, 3, fill=C["panel"], outline="")
        self._yt_load_canvas.create_rectangle(0, 0, fill_w, 3, fill=C["white"], outline="")

    def _yt_start_convert_pulse(self):
        """Animate a fast back-and-forth shimmer during ffmpeg conversion."""
        if self._yt_load_anim_job:
            self.root.after_cancel(self._yt_load_anim_job)
        self._yt_load_anim_running = True
        self._yt_load_anim_pos = 0.0
        self._yt_convert_dir = 1
        self._yt_animate_convert()

    def _yt_animate_convert(self):
        """Shimmer animation — faster back-and-forth to signal active conversion."""
        if not getattr(self, "_yt_load_anim_running", False):
            return
        w = self._yt_load_canvas.winfo_width() or 400
        # Bouncing fill that goes 0→100%→0 repeatedly
        pos = self._yt_load_anim_pos
        fill_w = int(w * pos)
        self._yt_load_canvas.delete("all")
        self._yt_load_canvas.create_rectangle(0, 0, w, 3, fill=C["panel"], outline="")
        self._yt_load_canvas.create_rectangle(0, 0, fill_w, 3, fill=C["white3"], outline="")
        # Small bright leading edge
        edge = min(w, fill_w + 6)
        self._yt_load_canvas.create_rectangle(fill_w, 0, edge, 3, fill=C["white"], outline="")
        # Advance position
        self._yt_load_anim_pos += 0.04 * self._yt_convert_dir
        if self._yt_load_anim_pos >= 1.0:
            self._yt_load_anim_pos = 1.0
            self._yt_convert_dir = -1
        elif self._yt_load_anim_pos <= 0.0:
            self._yt_load_anim_pos = 0.0
            self._yt_convert_dir = 1
        self._yt_load_anim_job = self.root.after(25, self._yt_animate_convert)

    def _yt_load_stop(self):
        """Hide the YouTube loading bar."""
        self._yt_load_anim_running = False
        if self._yt_load_anim_job:
            self.root.after_cancel(self._yt_load_anim_job)
            self._yt_load_anim_job = None
        self._yt_load_bar_frame.pack_forget()

    def _yt_animate_load(self):
        """Animate a sliding pulse on the loading bar."""
        if not getattr(self, "_yt_load_anim_running", False):
            return
        w = self._yt_load_canvas.winfo_width() or 400
        bar_w = int(w * 0.35)
        x1 = int(self._yt_load_anim_pos * (w + bar_w)) - bar_w
        x2 = x1 + bar_w
        self._yt_load_canvas.delete("all")
        # Background track
        self._yt_load_canvas.create_rectangle(0, 0, w, 3, fill=C["panel"], outline="")
        # Glowing pulse bar
        self._yt_load_canvas.create_rectangle(
            max(0, x1), 0, min(w, x2), 3, fill=C["white"], outline="")
        self._yt_load_anim_pos += 0.018
        if self._yt_load_anim_pos > 1.0:
            self._yt_load_anim_pos = 0.0
        self._yt_load_anim_job = self.root.after(30, self._yt_animate_load)

    def _yt_do_search(self):
        q = self.yt_search_var.get().strip()
        if not q:
            return
        if not self.yt_api.ytdlp_available():
            self.yt_content_lbl.config(
                text="yt-dlp not installed  —  run:  pip install yt-dlp")
            return
        self.yt_content_lbl.config(text="Searching ...")
        self._yt_clear_list()
        self._yt_tracks = []

        def _fetch():
            tracks = self.yt_api.search(q, max_results=50)
            def _show():
                self._yt_tracks = tracks

                if not tracks:
                    self.yt_content_lbl.config(
                        text="No results — try updating yt-dlp:  pip install -U yt-dlp")
                    self._yt_clear_list()
                    return
                self.yt_content_lbl.config(
                    text=f"{len(tracks)} results  —  double-click to play")
                self._yt_tracks = tracks
                self._yt_render_list()
                # Kick off thumbnail fetches
                for i, t in enumerate(tracks):
                    vid_id = t.get("id", "")
                    if vid_id:
                        url = f"https://i.ytimg.com/vi/{vid_id}/default.jpg"
                        threading.Thread(target=self._yt_fetch_thumb,
                            args=(i, url), daemon=True).start()
            self.root.after(0, _show)
        threading.Thread(target=_fetch, daemon=True).start()

    def _yt_play_selected(self, event=None):
        # If triggered by a double-click event, recalculate idx from position
        if event is not None:
            canvas_y = self.yt_list_cv.canvasy(event.y)
            idx = int(canvas_y // self._yt_row_height)
            if 0 <= idx < len(self._yt_tracks):
                self._yt_selected_idx = idx
        idx = self._yt_selected_idx
        if idx < 0 or not self._yt_tracks or idx >= len(self._yt_tracks):
            return
        track = self._yt_tracks[idx]
        # Cancel any in-progress download before starting a new one
        self._yt_cancelled = True
        self._yt_load_stop()
        def _start():
            import time as _t
            _t.sleep(0.15)  # let previous thread see the cancel flag
            self._yt_cancelled = False
            self._yt_stream(track)
        threading.Thread(target=_start, daemon=True).start()

    def _yt_play_track(self, track):
        """Cancel any current download then play a track."""
        self._yt_cancelled = True
        self._yt_load_stop()
        def _start():
            import time as _t; _t.sleep(0.15)
            self._yt_cancelled = False
            self._yt_stream(track)
        threading.Thread(target=_start, daemon=True).start()

    def _yt_list_click(self, event):
        # Convert canvas y to scrolled y
        canvas_y = self.yt_list_cv.canvasy(event.y)
        idx = int(canvas_y // self._yt_row_height)
        if 0 <= idx < len(self._yt_tracks):
            self._yt_selected_idx = idx
            self._yt_render_list()

    def _yt_list_resize(self, event):
        self._yt_list_width = event.width
        self._yt_render_list()

    def _yt_clear_list(self):
        self.yt_list_cv.delete("all")
        self.yt_list_cv.configure(scrollregion=(0, 0, 100, 40))
        self._yt_thumb_cache  = {}
        self._yt_selected_idx = -1

    def _yt_render_list(self):
        cv = self.yt_list_cv
        cv.delete("all")
        if not self._yt_tracks:
            cv.create_text(20, 20, text="No results.", anchor="nw", font=FM, fill=C["white3"])
            cv.configure(scrollregion=(0, 0, 100, 40))
            return
        RH = self._yt_row_height
        W  = max(self._yt_list_width, cv.winfo_width(), 400)
        cv.configure(scrollregion=(0, 0, W, RH * len(self._yt_tracks)))
        for i, t in enumerate(self._yt_tracks):
            self._yt_draw_row(i, t, W)

    def _yt_draw_row(self, i, t, W=None):
        cv  = self.yt_list_cv
        RH  = self._yt_row_height
        if W is None:
            W = max(self._yt_list_width, cv.winfo_width(), 400)
        y0  = i * RH
        y1  = y0 + RH
        tag = f"ytrow{i}"
        cv.delete(tag)
        bg = C["select"] if i == self._yt_selected_idx else (C["panel2"] if i % 2 == 0 else C["bg"])
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)
        TH = RH - 8
        # Thumbnail placeholder
        cv.create_rectangle(4, y0+4, 4+TH, y1-4, fill=C["panel"], outline="", tags=tag)
        if i in self._yt_thumb_cache:
            cv.create_image(4, y0+4, image=self._yt_thumb_cache[i], anchor="nw", tags=tag)
        else:
            cv.create_text(4+TH//2, y0+RH//2, text="▶", font=("Courier New", 10),
                fill=C["white3"], anchor="center", tags=tag)
        # Save star button (right side)
        vid_id  = t.get("id", "")
        is_saved = self._yt_is_saved(vid_id)
        star_x  = W - 24
        star_col = "#f0c040" if is_saved else C["white3"]
        star_tag = f"ytstar{i}"
        cv.delete(star_tag)
        cv.create_text(star_x, y0+RH//2, text="★", font=("Courier New", 13),
            fill=star_col, anchor="center", tags=(tag, star_tag))
        cv.tag_bind(star_tag, "<Button-1>",
            lambda e, tr=t, idx=i: self._yt_toggle_save(tr, idx))
        cv.tag_bind(star_tag, "<Enter>",
            lambda e, st=star_tag: cv.itemconfig(st, fill="#f0c040"))
        cv.tag_bind(star_tag, "<Leave>",
            lambda e, st=star_tag, sv=is_saved: cv.itemconfig(st, fill="#f0c040" if sv else C["white3"]))
        # Title and channel (leave room for star)
        title   = (t.get("title")   or "Unknown")[:58]
        channel = (t.get("channel") or "")[:35]
        dur     = int(t.get("duration") or 0)
        dur_str = f"{dur//60}:{dur%60:02d}" if dur else ""
        tx = 4 + TH + 8
        cv.create_text(tx, y0+RH//2-8, text=title, font=("Courier New", 9, "bold"),
            fill=C["white"], anchor="w", tags=tag)
        sub = f"{channel}  {dur_str}".strip()
        cv.create_text(tx, y0+RH//2+8, text=sub, font=("Courier New", 8),
            fill=C["white3"], anchor="w", tags=tag)
        cv.create_line(0, y1-1, W, y1-1, fill=C["border"], tags=tag)

    def _yt_toggle_save(self, track, idx):
        vid_id = track.get("id", "")
        if self._yt_is_saved(vid_id):
            self._yt_unsave_track(vid_id)
        else:
            self._yt_save_track(track)
        # Redraw just this row to update star colour
        W = max(self._yt_list_width, self.yt_list_cv.winfo_width(), 400)
        self._yt_draw_row(idx, track, W)

    def _yt_fetch_thumb(self, idx, url):
        try:
            import urllib.request as _ur, tempfile, os
            data   = _ur.urlopen(url, timeout=6).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp    = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data); tmp.close()
            self.root.after(0, lambda p=tmp.name, i=idx: self._yt_load_thumb(i, p))
        except Exception:
            pass

    def _yt_load_thumb(self, idx, path):
        try:
            import tkinter as _tk
            RH = self._yt_row_height - 8
            try:
                img = _tk.PhotoImage(file=path)
                iw, ih = img.width(), img.height()
                factor = max(1, max(iw, ih) // RH)
                img = img.subsample(factor, factor)
            except Exception:
                from PIL import Image, ImageTk
                img = Image.open(path).resize((RH, RH))
                img = ImageTk.PhotoImage(img)
            self._yt_thumb_cache[idx] = img
            if self._yt_tracks:
                W = max(self._yt_list_width, self.yt_list_cv.winfo_width(), 400)
                self._yt_draw_row(idx, self._yt_tracks[idx], W)
        except Exception:
            pass
        finally:
            try:
                import os; os.unlink(path)
            except Exception:
                pass

    def _yt_rclick(self, event):
        canvas_y = self.yt_list_cv.canvasy(event.y)
        idx = int(canvas_y // self._yt_row_height)
        if idx < 0 or idx >= len(self._yt_tracks):
            return
        track = self._yt_tracks[idx]
        menu = tk.Menu(self.root, bg=C["panel"], fg=C["white"],
                       activebackground=C["select2"], activeforeground=C["white"],
                       font=FM, tearoff=0, bd=0, relief="flat")
        menu.add_command(label="▶ Play",
            command=lambda t=track: self._yt_play_track(t))
        menu.add_separator()
        menu.add_command(label="Open in browser",
            command=lambda: webbrowser.open(
                f"https://www.youtube.com/watch?v={track.get('id','')}"))
        menu.tk_popup(event.x_root, event.y_root)

    def _yt_stream(self, track):
        vid_id  = track.get("id", "")
        title   = track.get("title", "Unknown")
        channel = track.get("channel", "Unknown")
        dur_s   = int(track.get("duration") or 0)
        if not vid_id:
            return

        self.root.after(0, self._yt_load_start)

        try:
            # Check cache for any previously downloaded format
            cached_mp3 = YT_CACHE / f"{vid_id}.mp3"
            cached_m4a = YT_CACHE / f"{vid_id}.m4a"

            if cached_mp3.exists():
                self.root.after(0, lambda: self.yt_content_lbl.config(
                    text=f"Loading (cached): {title[:50]} ..."))
                out_file = str(cached_mp3)

            elif cached_m4a.exists():
                self.root.after(0, lambda: self.yt_content_lbl.config(
                    text=f"Loading (cached): {title[:50]} ..."))
                out_file = str(cached_m4a)

            else:
                # Download m4a directly — no ffmpeg needed at all
                self.root.after(0, lambda: self.yt_content_lbl.config(
                    text=f"Loading: {title[:60]} ..."))

                import yt_dlp, tempfile as _tf, shutil
                tmp_dir = _tf.mkdtemp()

                def _progress_hook(d):
                    if d.get("status") == "downloading":
                        downloaded = d.get("downloaded_bytes") or 0
                        total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                        if total > 0:
                            pct = int(downloaded / total * 100)
                            self.root.after(0, lambda p=pct: (
                                self.yt_content_lbl.config(
                                    text=f"Downloading: {title[:40]} ... {p}%"),
                                self._yt_set_load_progress(p / 100)
                            ))

                import sys as _sys, os as _os
                # Find ffmpeg — check next to exe first, then MEIPASS, then script dir
                _ffmpeg_dir = ""
                _ff_candidates = []
                if getattr(_sys, "frozen", False):
                    _ff_candidates.append(_os.path.dirname(_sys.executable))
                if hasattr(_sys, "_MEIPASS"):
                    _ff_candidates.append(_sys._MEIPASS)
                try:
                    _ff_candidates.append(_os.path.dirname(_os.path.abspath(__file__)))
                except Exception:
                    pass
                for _d in _ff_candidates:
                    if _os.path.isfile(_os.path.join(_d, "ffmpeg.exe")):
                        _ffmpeg_dir = _d
                        break

                ydl_opts = {
                    "quiet":          True,
                    "no_warnings":    True,
                    "format":         "bestaudio/best",
                    "outtmpl":        str(Path(tmp_dir) / f"{vid_id}.%(ext)s"),
                    "progress_hooks": [_progress_hook],
                }
                # Only add ffmpeg conversion if ffmpeg is available
                if _ffmpeg_dir:
                    ydl_opts["ffmpeg_location"] = _ffmpeg_dir
                    ydl_opts["postprocessors"] = [{
                        "key":              "FFmpegExtractAudio",
                        "preferredcodec":   "mp3",
                        "preferredquality": "192",
                    }]

                import datetime
                logpath = Path.home() / "voidplayer_error.log"
                try:
                    with open(logpath, "a", encoding="utf-8") as _lf:
                        _lf.write(f"[{datetime.datetime.now()}] ffmpeg_dir={_ffmpeg_dir!r} candidates={_ff_candidates}\n")
                except Exception:
                    pass

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={vid_id}", download=True)

                if getattr(self, "_yt_cancelled", False):
                    return

                if not dur_s:
                    dur_s = int((info or {}).get("duration") or 0)

                # Find the output file (mp3 if ffmpeg ran, otherwise whatever yt-dlp saved)
                files = list(Path(tmp_dir).iterdir())
                if not files:
                    raise FileNotFoundError("No audio file downloaded")
                # Prefer mp3 if it exists
                mp3_files = [f for f in files if f.suffix.lower() == ".mp3"]
                tmp_file = mp3_files[0] if mp3_files else files[0]
                actual_ext = tmp_file.suffix.lower()

                try:
                    with open(logpath, "a", encoding="utf-8") as _lf:
                        _lf.write(f"[{datetime.datetime.now()}] Final ext={actual_ext} size={tmp_file.stat().st_size}\n")
                except Exception:
                    pass

                dest = YT_CACHE / f"{vid_id}{actual_ext}"
                shutil.move(str(tmp_file), str(dest))
                out_file = str(dest)

            def _play(f=out_file, d=dur_s):
                self._yt_load_stop()
                self._stop_all_sources()
                self._active_source = "youtube"
                self._sp_mode = False
                self._set_source_badge("youtube")
                ok = self.engine.load(f)
                if ok:
                    if d > 0:
                        self.engine.duration = float(d)
                    else:
                        d = self.engine.duration
                    self.engine.set_volume(self.engine.volume)
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self._set_logo_playing(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=channel)
                    self.now_album.config(text="YouTube")
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=self._fmt(d))
                    self._draw_prog(0)
                    self.yt_np_lbl.config(text=f"▶  {title[:50]}  —  {channel}")
                    self.yt_content_lbl.config(text=f"NOW PLAYING: {title[:60]}")
                    self.current_idx = -1
                    # Set YouTube thumbnail — must come after _art_url_last was
                    # cleared by _stop_all_sources so the dedup guard doesn't skip it
                    thumb_url = track.get("thumbnail") or track.get("thumb") or ""
                    if thumb_url:
                        self._set_album_art(thumb_url)
                    self._history_add({"title": title, "artist": channel, "album": "YouTube"}, source="youtube")
                else:
                    # MCI can't play this format — user needs K-Lite Codec Pack
                    self.yt_content_lbl.config(
                        text="Playback error — install K-Lite Codec Pack to play YouTube audio: codecguide.com/download_kl.htm")
            if not getattr(self, "_yt_cancelled", False):
                self.root.after(0, _play)

        except ImportError:
            self.root.after(0, self._yt_load_stop)
            self.root.after(0, lambda: self.yt_content_lbl.config(
                text="yt-dlp not installed  —  run: pip install yt-dlp"))
        except Exception as ex:
            import traceback, datetime
            err = str(ex)
            tb  = traceback.format_exc()
            try:
                logpath = Path.home() / "voidplayer_error.log"
                with open(logpath, "a", encoding="utf-8") as _lf:
                    _lf.write("\n[" + str(datetime.datetime.now()) + "]\n" + tb + "\n")
            except Exception:
                pass
            self.root.after(0, self._yt_load_stop)
            self.root.after(0, lambda: self.yt_content_lbl.config(
                text=f"Error: {err[:120]}"))


    # ── CLAUDE DEBUG VIEW ─────────────────
    def _build_claude_view(self):
        self.claude_frame = tk.Frame(self.content, bg=C["bg"])

        # ── Header ────────────────────────────────────────────────────────
        top = tk.Frame(self.claude_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="OTERNOS-01", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        tk.Label(top, text="// diagnostic interface", font=FMS, fg=C["white3"], bg=C["bg"]).pack(side="left", padx=12)
        tk.Frame(self.claude_frame, bg=C["border2"], height=1).pack(fill="x", pady=(6, 0))
        tk.Frame(self.claude_frame, bg=C["border"],  height=1).pack(fill="x")

        # ── Live context panel (updates when track changes) ───────────────
        ctx_outer = tk.Frame(self.claude_frame, bg=C["panel"])
        ctx_outer.pack(fill="x", padx=20, pady=(8, 0))
        tk.Frame(ctx_outer, bg=C["border2"], height=1).pack(fill="x")
        ctx_inner = tk.Frame(ctx_outer, bg=C["panel"])
        ctx_inner.pack(fill="x", padx=10, pady=6)

        # left column — now playing
        ctx_left = tk.Frame(ctx_inner, bg=C["panel"])
        ctx_left.pack(side="left", fill="x", expand=True)
        tk.Label(ctx_left, text="▸ NOW PLAYING", font=("Courier New", 6, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w")
        self._ctx_title  = tk.Label(ctx_left, text="—", font=("Courier New", 9, "bold"),
                                    fg=C["white"], bg=C["panel"])
        self._ctx_title.pack(anchor="w")
        self._ctx_artist = tk.Label(ctx_left, text="", font=("Courier New", 8),
                                    fg=C["white2"], bg=C["panel"])
        self._ctx_artist.pack(anchor="w")
        self._ctx_pos    = tk.Label(ctx_left, text="", font=("Courier New", 7),
                                    fg=C["white3"], bg=C["panel"])
        self._ctx_pos.pack(anchor="w")

        # right column — quick-ask buttons
        ctx_right = tk.Frame(ctx_inner, bg=C["panel"])
        ctx_right.pack(side="right", padx=(12, 0))
        tk.Label(ctx_right, text="QUICK ASK", font=("Courier New", 6, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="e", pady=(0, 4))

        def _quick(prompt_fn):
            self._claude_input.delete("1.0", "end")
            self._claude_input.insert("1.0", prompt_fn())
            self._claude_send()

        for label, pfn in [
            ("analyse track",  lambda: f"Analyse the song structure and mood of: {self._ctx_title.cget('text')} by {self._ctx_artist.cget('text')}"),
            ("why does it hit",lambda: f"Why does '{self._ctx_title.cget('text')}' by {self._ctx_artist.cget('text')} feel so powerful emotionally?"),
            ("similar tracks", lambda: f"Recommend 5 tracks similar to '{self._ctx_title.cget('text')}' by {self._ctx_artist.cget('text')}"),
        ]:
            btn = tk.Label(ctx_right, text=f"[ {label} ]", font=("Courier New", 7),
                           fg=C["white3"], bg=C["panel"], cursor="hand2")
            btn.pack(anchor="e", pady=1)
            btn.bind("<Button-1>", lambda e, p=pfn: _quick(p))
            btn.bind("<Enter>",    lambda e, b=btn: b.config(fg=C["white"]))
            btn.bind("<Leave>",    lambda e, b=btn: b.config(fg=C["white3"]))

        tk.Frame(ctx_outer, bg=C["border2"], height=1).pack(fill="x")

        # start context ticker
        def _ctx_tick():
            try:
                title  = self.now_title.cget("text")
                artist = self.now_artist.cget("text")
                self._ctx_title.config(text=title  or "—")
                self._ctx_artist.config(text=artist or "")
                pos = self.engine.get_position() if self.engine.is_playing else None
                dur = self.engine.duration       if self.engine.is_playing else None
                if pos is not None and dur:
                    mm, ss = divmod(int(pos), 60)
                    dm, ds = divmod(int(dur), 60)
                    self._ctx_pos.config(text=f"{mm}:{ss:02d} / {dm}:{ds:02d}  {'▶' if self.engine.is_playing else '⏸'}")
                else:
                    self._ctx_pos.config(text="—")
            except Exception:
                pass
            self.claude_frame.after(1000, _ctx_tick)
        self.claude_frame.after(500, _ctx_tick)

        # ── API Key entry ─────────────────────────────────────────────────
        kf = tk.Frame(self.claude_frame, bg=C["bg"])
        kf.pack(fill="x", padx=20, pady=(10, 0))
        tk.Label(kf, text="API KEY", font=FMS, fg=C["white3"], bg=C["bg"]).pack(side="left")
        self._claude_key_var = tk.StringVar()
        key_e = tk.Entry(kf, textvariable=self._claude_key_var, font=FMS,
            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
            relief="flat", bd=0, show="*", width=52)
        key_e.pack(side="left", padx=8, ipady=3)
        _kfile = Path.home() / ".oternos_claude.json"
        try:
            self._claude_key_var.set(json.loads(_kfile.read_text()).get("key", ""))
        except Exception:
            pass
        def _save_key(*a):
            try:
                _kfile.write_text(json.dumps({"key": self._claude_key_var.get()}))
            except Exception:
                pass
        self._claude_key_var.trace_add("write", _save_key)
        tk.Frame(self.claude_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 0))

        # ── Chat area ─────────────────────────────────────────────────────
        chat_outer = tk.Frame(self.claude_frame, bg=C["bg"])
        chat_outer.pack(fill="both", expand=True, padx=20, pady=(8, 0))
        chat_sb = tk.Scrollbar(chat_outer, bg=C["panel"], troughcolor=C["bg"],
                               width=6, relief="flat", bd=0)
        chat_sb.pack(side="right", fill="y")
        self._claude_chat = tk.Text(chat_outer, bg=C["panel"], fg=C["white2"],
            font=FMS, relief="flat", bd=0, wrap="word", state="disabled",
            highlightthickness=0, yscrollcommand=chat_sb.set, padx=10, pady=8)
        self._claude_chat.pack(side="left", fill="both", expand=True)
        chat_sb.config(command=self._claude_chat.yview)
        self._claude_chat.tag_config("user",  foreground=C["white3"])
        self._claude_chat.tag_config("ai",    foreground=C["white"])
        self._claude_chat.tag_config("label", foreground=C["white3"],
            font=("Courier New", 7, "bold"))
        self._claude_chat.tag_config("err",   foreground="#e05070")

        # ── Input row ─────────────────────────────────────────────────────
        inp_frame = tk.Frame(self.claude_frame, bg=C["bg"])
        inp_frame.pack(fill="x", padx=20, pady=(6, 10))
        self._claude_input = tk.Text(inp_frame, bg=C["panel"], fg=C["white"],
            font=FM, relief="flat", bd=0, highlightthickness=0,
            insertbackground=C["white"], height=3, wrap="word", padx=6, pady=4)
        self._claude_input.pack(side="left", fill="x", expand=True)
        send_btn = tk.Label(inp_frame, text="[ SEND ]", font=FMS,
            fg=C["white3"], bg=C["panel"], cursor="hand2", padx=12, pady=4)
        send_btn.pack(side="left", padx=(6, 0))
        send_btn.bind("<Button-1>", lambda e: self._claude_send())
        send_btn.bind("<Enter>",    lambda e: send_btn.config(fg=C["white"]))
        send_btn.bind("<Leave>",    lambda e: send_btn.config(fg=C["white3"]))
        self._claude_input.bind("<Control-Return>",
            lambda e: (self._claude_send(), "break")[1])

        self._claude_history = []
        self._claude_append("label", "OTERNOS-01  //  system diagnostic\n")
        self._claude_append("ai", "OTERNOS-01 online.\nDescribe the fault.\n")

    def _claude_append(self, tag, text):
        self._claude_chat.config(state="normal")
        self._claude_chat.insert("end", text, (tag,))
        self._claude_chat.config(state="disabled")
        self._claude_chat.see("end")

    def _claude_get_state(self):
        lines = []
        lines.append("current_view: " + self.view)
        lines.append("track_count: " + str(len(self.library)))
        lines.append("now_playing: " + repr(self.now_title.cget("text")))
        lines.append("status: " + repr(self.status_lbl.cget("text")))
        lines.append("yt_tracks_loaded: " + str(len(self._yt_tracks)))
        lines.append("yt_status: " + repr(self.yt_status_lbl.cget("text")))
        lines.append("yt_content: " + repr(self.yt_content_lbl.cget("text")))
        try:
            lines.append("yt_list_items: " + str(len(self._yt_tracks)))
        except Exception:
            pass
        lines.append("ytdlp_available: " + str(self.yt_api.ytdlp_available()))
        lines.append("engine_playing: " + str(self.engine.is_playing))
        return "\n".join(lines)

    def _claude_send(self):
        msg = self._claude_input.get("1.0", "end").strip()
        if not msg:
            return
        self._claude_input.delete("1.0", "end")
        key = self._claude_key_var.get().strip()
        if not key:
            self._claude_append("err", "No Groq API key entered above. Get one free at groq.com\n")
            return
        self._claude_append("label", "\n> ")
        self._claude_append("user", msg + "\n")
        self._claude_append("label", "\nOTERNOS-01\n")
        self._claude_append("ai", "thinking...\n")
        self._claude_history.append({"role": "user", "content": msg})
        state = self._claude_get_state()
        system = (
            "You are OTERNOS-01, an AI embedded inside OTERNOS PLAYER. "
            "Your personality: minimal, cold, precise. No filler words. No pleasantries. "
            "You respond in short, direct sentences. You do not say hello or goodbye. "
            "You do not explain yourself unless asked. You diagnose, you answer, you stop. "
            "If the user describes a bug, use the live app state to diagnose it. Be surgical. "
            "If something is not a bug, say so in one line.\n\n"
            "APP STATE:\n" + state
        )
        def _call():
            try:
                # Build messages with system prompt prepended for Groq
                messages = [{"role": "system", "content": system}] + self._claude_history
                body = json.dumps({
                    "model": "llama-3.3-70b-versatile",
                    "max_tokens": 1024,
                    "messages": messages,
                }).encode()
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=body,
                    headers={
                        "Content-Type":  "application/json",
                        "Authorization": f"Bearer {key}",
                        "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read())
                reply = data["choices"][0]["message"]["content"]
                self._claude_history.append({"role": "assistant", "content": reply})
                def _show():
                    self._claude_chat.config(state="normal")
                    idx = self._claude_chat.search("thinking...", "1.0", "end")
                    if idx:
                        self._claude_chat.delete(idx, idx + "+11c")
                    self._claude_chat.config(state="disabled")
                    self._claude_append("ai", reply + "\n")
                self.root.after(0, _show)
            except urllib.error.HTTPError as ex:
                try:
                    body = ex.read().decode()
                except Exception:
                    body = ""
                err_msg = f"HTTP {ex.code}: {body[:300]}"
                def _show_err(m=err_msg):
                    self._claude_chat.config(state="normal")
                    idx = self._claude_chat.search("thinking...", "1.0", "end")
                    if idx:
                        self._claude_chat.delete(idx, idx + "+11c")
                    self._claude_chat.config(state="disabled")
                    self._claude_append("err", "Error: " + m + "\n")
                self.root.after(0, _show_err)
            except Exception as ex:
                err_msg = str(ex)
                def _show_err2(m=err_msg):
                    self._claude_chat.config(state="normal")
                    idx = self._claude_chat.search("thinking...", "1.0", "end")
                    if idx:
                        self._claude_chat.delete(idx, idx + "+11c")
                    self._claude_chat.config(state="disabled")
                    self._claude_append("err", "Error: " + m + "\n")
                self.root.after(0, _show_err2)
        threading.Thread(target=_call, daemon=True).start()

    # ── ALBUM ART ─────────────────────────
    def _draw_art_placeholder(self):
        cv = self.art_cv
        cv.delete("all")
        cv.create_rectangle(0, 0, 54, 54, fill=C["panel"], outline="")
        # small music note icon
        cv.create_text(27, 27, text="♪", font=("Courier New", 20),
                       fill=C["white3"], anchor="center")

    def _set_album_art(self, url):
        if not url or url == self._art_url_last:
            return
        self._art_url_last = url
        def _fetch():
            try:
                import urllib.request as _ur
                data = _ur.urlopen(url, timeout=6).read()
                self.root.after(0, lambda: self._load_art_bytes(data))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _fetch_art_musicbrainz(self, artist, title):
        """Try MusicBrainz + Cover Art Archive for a local track with no embedded art."""
        def _fetch():
            try:
                import urllib.request as _ur
                import urllib.parse as _up
                q = _up.quote(f'recording:"{title}" AND artist:"{artist}"')
                url = f"https://musicbrainz.org/ws/2/recording/?query={q}&limit=1&fmt=json"
                req = _ur.Request(url, headers={"User-Agent": "OternosPlayer/1.1 (contact@oternos.local)"})
                data = json.loads(_ur.urlopen(req, timeout=8).read())
                recordings = data.get("recordings", [])
                if not recordings:
                    return
                # find first release with a cover
                for rel in recordings[0].get("releases", [])[:3]:
                    rid = rel.get("id", "")
                    if not rid:
                        continue
                    try:
                        caa = f"https://coverartarchive.org/release/{rid}/front-250"
                        img = _ur.urlopen(caa, timeout=6).read()
                        if img:
                            self.root.after(0, lambda d=img: self._load_art_bytes(d))
                            return
                    except Exception:
                        continue
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _load_art_bytes(self, data):
        """Render image bytes into the art canvas.
        PIL-first (handles JPEG natively), pure-python temp-file fallback.
        No PowerShell involved — no console flash, no silent failures."""
        SIZE = 54
        # ── Try PIL/Pillow first ──
        try:
            from PIL import Image, ImageTk
            import io
            img = Image.open(io.BytesIO(data)).convert("RGBA").resize((SIZE, SIZE))
            photo = ImageTk.PhotoImage(img)
            self._art_photo = photo
            self.art_cv.delete("all")
            self.art_cv.create_image(SIZE // 2, SIZE // 2, image=photo, anchor="center")
            return
        except Exception:
            pass
        # ── Fallback: temp file + tk.PhotoImage ──
        import tempfile, os, tkinter as _tk
        tmp_path = None
        try:
            is_jpeg = data[:2] == b'\xff\xd8'
            suffix = ".jpg" if is_jpeg else ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            img = _tk.PhotoImage(file=tmp_path)
            iw, ih = img.width(), img.height()
            if iw > SIZE or ih > SIZE:
                factor = max(1, max(iw, ih) // SIZE)
                img = img.subsample(factor, factor)
            self._art_photo = img
            self.art_cv.delete("all")
            self.art_cv.create_image(SIZE // 2, SIZE // 2, image=img, anchor="center")
        except Exception:
            self._draw_art_placeholder()
        finally:
            if tmp_path:
                try: os.unlink(tmp_path)
                except Exception: pass


    def _build_playerbar(self):
        bar = tk.Frame(self.root, bg=C["panel"], height=108)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        # Signalis: triple-line top border — thick + thin + hairline
        tk.Frame(bar, bg=C["border2"], height=2).pack(fill="x")
        tk.Frame(bar, bg=C["border"],  height=1).pack(fill="x")
        # Ambient data ticker strip — packed right after borders
        self._ticker = DataTicker(bar, width=900, height=10, bg=C["panel"])
        self._ticker.pack(fill="x")
        inner = tk.Frame(bar, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=16)

        # Left: now playing — Signalis framed readout
        left = tk.Frame(inner, bg=C["panel"], width=280)
        left.pack(side="left", fill="y", pady=8)
        left.pack_propagate(False)

        # Signalis: channel/system readout header above art row
        ch_hdr = tk.Frame(left, bg=C["panel"])
        ch_hdr.pack(fill="x", pady=(0, 3))
        tk.Label(ch_hdr, text="▸ NOW PLAYING", font=("Courier New", 6, "bold"),
                 fg=C["white3"], bg=C["panel"], anchor="w").pack(side="left")
        tk.Frame(ch_hdr, bg=C["border2"], height=1).pack(fill="x", pady=(2, 0))

        art_row = tk.Frame(left, bg=C["panel"])
        art_row.pack(fill="x", anchor="w")

        self.art_cv = tk.Canvas(art_row, bg=C["panel"], width=46, height=46,
                                highlightthickness=1,
                                highlightbackground=C["border2"])
        self.art_cv.pack(side="left", padx=(0, 10))
        self._art_photo    = None
        self._art_url_last = None
        self._draw_art_placeholder()

        info_col = tk.Frame(art_row, bg=C["panel"])
        info_col.pack(side="left", fill="both", expand=True)
        self.now_title  = tk.Label(info_col, text="NO TRACK", font=("Courier New", 9, "bold"),
                                   fg=C["white"],  bg=C["panel"], anchor="w")
        self.now_artist = tk.Label(info_col, text="",              font=("Courier New", 8),
                                   fg=C["white2"], bg=C["panel"], anchor="w")
        self.now_album  = tk.Label(info_col, text="",              font=("Courier New", 7),
                                   fg=C["white3"], bg=C["panel"], anchor="w")
        self.now_title.pack(anchor="w")
        self.now_artist.pack(anchor="w")
        self.now_album.pack(anchor="w")
        # Source badge — shows which audio source is active
        self.source_badge = tk.Label(info_col, text="",
                                     font=("Courier New", 6, "bold"),
                                     fg=C["white3"], bg=C["panel"], anchor="w")
        self.source_badge.pack(anchor="w")
        self.lyric_ticker_lbl = tk.Label(info_col, text="",
                                          font=("Courier New", 7), fg=C["white3"],
                                          bg=C["panel"], anchor="w")
        self.lyric_ticker_lbl.pack(anchor="w")

        self.wavevis = WaveVisualizer(left, height=22)
        self.wavevis.pack(fill="x", pady=(4, 0))

        # Signalis: vertical separator between left and center
        tk.Frame(inner, bg=C["border2"], width=1).pack(side="left", fill="y", pady=6)

        # Center: controls + progress — Signalis control block
        center = tk.Frame(inner, bg=C["panel"])
        center.pack(side="left", expand=True, fill="both", padx=16)

        # Signalis: control header label
        ctrl_hdr = tk.Frame(center, bg=C["panel"])
        ctrl_hdr.pack(fill="x", pady=(8, 0))
        tk.Frame(ctrl_hdr, bg=C["border"], height=1).pack(fill="x")

        ctrl = tk.Frame(center, bg=C["panel"])
        ctrl.pack(pady=(8, 4))
        self.btn_shuf   = self._cbtn(ctrl, "⇌", self._toggle_shuffle)
        self.btn_prev   = self._cbtn(ctrl, "⏮", self._prev)
        self.btn_play   = self._cbtn(ctrl, "▶", self._toggle_play, sz=16)
        self.btn_next   = self._cbtn(ctrl, "⏭", self._next)
        self.btn_repeat = self._cbtn(ctrl, "↺", self._toggle_repeat)

        pf = tk.Frame(center, bg=C["panel"])
        pf.pack(fill="x")
        self.lbl_cur = tk.Label(pf, text="0:00", font=FMS, fg=C["white3"], bg=C["panel"], width=5)
        self.lbl_cur.pack(side="left")
        self.prog_cv = tk.Canvas(pf, bg=C["border2"], height=4,
                                 highlightthickness=0, cursor="hand2")
        self.prog_cv.pack(side="left", fill="x", expand=True, padx=6)
        self.prog_fill = self.prog_cv.create_rectangle(0, 0, 0, 4, fill=C["white2"], outline="")
        self.prog_dot  = self.prog_cv.create_rectangle(0, 0, 2, 4, fill=C["white"], outline="")
        self.prog_cv.bind("<ButtonPress-1>",   self._seek_press)
        self.prog_cv.bind("<B1-Motion>",       self._seek_drag)
        self.prog_cv.bind("<ButtonRelease-1>", self._seek_end)
        self.lbl_tot = tk.Label(pf, text="0:00", font=FMS, fg=C["white3"], bg=C["panel"], width=5)
        self.lbl_tot.pack(side="left")

        # Signalis: vertical separator between center and right
        tk.Frame(inner, bg=C["border2"], width=1).pack(side="right", fill="y", pady=6)

        # Right: volume + status — Signalis system status panel
        right = tk.Frame(inner, bg=C["panel"], width=180)
        right.pack(side="right", fill="y", pady=8)
        right.pack_propagate(False)

        # Signalis: status header
        st_hdr = tk.Frame(right, bg=C["panel"])
        st_hdr.pack(fill="x")
        tk.Label(st_hdr, text="▸ SYS STATUS", font=("Courier New", 6, "bold"),
                 fg=C["white3"], bg=C["panel"], anchor="e").pack(anchor="e")
        tk.Frame(st_hdr, bg=C["border"], height=1).pack(fill="x")

        self.vol_cv = tk.Canvas(right, bg=C["panel"], width=160, height=48,
                                highlightthickness=0, cursor="hand2")
        self.vol_cv.pack(anchor="e")

        self._vol_height    = 4.0
        self._vol_hover_job = None
        self._vol_dragging  = False
        self._vol_anim_job  = None
        self._vol_glow      = 0.0

        self.vol_cv.bind("<ButtonPress-1>",   self._vol_press)
        self.vol_cv.bind("<B1-Motion>",       self._vol_drag)
        self.vol_cv.bind("<ButtonRelease-1>", self._vol_release)
        self.vol_cv.bind("<Enter>",           lambda e: self._vol_hover(True))
        self.vol_cv.bind("<Leave>",           lambda e: self._vol_hover(False))
        self.vol_cv.bind("<MouseWheel>",      self._vol_scroll)

        self._upd_vol()

        self._norm_meter = NormMeter(right, width=160, height=4)
        self._norm_meter.pack(anchor="e", pady=(2, 0))

        # Signalis: status label with bracket readout format
        self.status_lbl = tk.Label(right, text="[ IDLE ]", font=("Courier New", 7),
                                   fg=C["white3"], bg=C["panel"], anchor="e")
        self.status_lbl.pack(anchor="e", pady=(4, 0))

        # Slim speed/A-B row
        ec = tk.Frame(center, bg=C["panel"])
        ec.pack(pady=(4, 0))

        def _small_btn(text, cmd, tip=""):
            b = tk.Label(ec, text=text, font=("Courier New", 7), fg=C["white3"],
                         bg=C["panel"], cursor="hand2", padx=5)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>",    lambda e: b.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e: b.config(fg=C["white3"]))
            return b

        self._speed_lbl = _small_btn("1.0×", self._cycle_speed)
        _small_btn("[A",  self._ab_set_a)
        self._ab_lbl = tk.Label(ec, text="—", font=("Courier New", 7),
                                fg=C["white3"], bg=C["panel"], padx=2)
        self._ab_lbl.pack(side="left")
        _small_btn("B]",  self._ab_set_b)
        _small_btn("✕",  self._ab_clear)
        tk.Label(ec, text=" ", bg=C["panel"]).pack(side="left")
        _small_btn("BKM", self._add_bookmark)

        # Start norm meter update loop
        self.root.after(200, self._spec_tick)

    def _set_source_badge(self, source):
        """Update the source indicator badge in the player bar."""
        labels = {
            "library":    "",
            "spotify":    "[ SPOTIFY ]",
            "youtube":    "[ YOUTUBE ]",
            "soundcloud": "[ SOUNDCLOUD ]",
            "none":       "",
        }
        try:
            self.source_badge.config(text=labels.get(source, ""))
        except Exception:
            pass

    def _set_logo_playing(self, playing):
        """Update sidebar logo and status indicator."""
        try:
            self._sidebar_logo.is_playing = playing
            self._sidebar_status_lbl.config(
                text="[ PLAYING ]" if playing else "[  IDLE  ]",
                fg=C["white2"] if playing else C["white3"])
        except Exception:
            pass
        pass

    def _cbtn(self, p, text, cmd, sz=12):
        # Signalis: control buttons have bracket wrapping, flat mono feel
        b = tk.Label(p, text=text, font=("Courier New", sz), fg=C["white3"],
                     bg=C["panel"], cursor="hand2", padx=9, pady=4,
                     relief="flat", bd=0)
        b.pack(side="left", padx=2)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=40))
        b.bind("<Leave>",    lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=40))
        return b

    # ── VIEW SWITCHING ────────────────────
    def _route_scroll(self, e):
        """Route mousewheel to the active view's scrollable widget."""
        # Don't hijack scroll if cursor is over the sidebar
        try:
            wx = e.widget.winfo_rootx()
            sidebar_right = self._side_cv.winfo_rootx() + self._side_cv.winfo_width()
            if wx <= sidebar_right:
                return
        except Exception:
            pass
        amt = int(-1*(e.delta/120))*3
        v = self.view
        try:
            if v in ("library", "playlist"):
                self.track_list.yview_scroll(amt, "units")
            elif v == "queue":
                self.queue_list.yview_scroll(amt, "units")
            elif v == "history":
                self._hist_cv.yview_scroll(amt, "units")
            elif v == "soundcloud":
                self.sc_list.yview_scroll(amt, "units")
            elif v == "youtube":
                self.yt_list.yview_scroll(amt, "units")
            elif v == "albums":
                self._alb_cv.yview_scroll(amt, "units")
            elif v == "lyrics":
                self._lyrics_cv.yview_scroll(amt, "units")
            elif v == "help":
                self._help_cv.yview_scroll(amt, "units")
        except Exception:
            pass

    def _switch_view(self, view):
        if view == self.view and hasattr(self, '_fade_overlay'):
            return

        def _do_switch():
            self.view = view
            for _attr in ("lib_frame","queue_frame","viz_frame","lyrics_frame",
                          "history_frame","album_frame","sp_frame","sc_frame",
                          "yt_frame","claude_frame","help_frame"):
                if hasattr(self, _attr):
                    try: getattr(self, _attr).pack_forget()
                    except: pass
            if view in ("library", "playlist"):
                self.lib_frame.pack(fill="both", expand=True)
                if view == "library":
                    self.view_title.config(text="ALL TRACKS")
                    self.active_playlist = None
                    self._clear_pl_actions()
                self._refresh_tracks()
            elif view == "queue":
                self.queue_frame.pack(fill="both", expand=True)
                self._refresh_queue()
            elif view == "visualizer":
                self.viz_frame.pack(fill="both", expand=True)
                if self._viz_job:
                    self.viz_cv.after_cancel(self._viz_job)
                self._viz_job = None
                self.viz_cv.after(50, self._viz_tick)
            elif view == "lyrics":
                self.lyrics_frame.pack(fill="both", expand=True)
                self._refresh_lyrics_view()
            elif view == "history":
                self.history_frame.pack(fill="both", expand=True)
                self._refresh_history_view()
            elif view == "albums":
                self.album_frame.pack(fill="both", expand=True)
                self._refresh_album_view()
            elif view == "spotify":
                self.sp_frame.pack(fill="both", expand=True)
                self._sp_refresh_view()
            elif view == "soundcloud":
                self.sc_frame.pack(fill="both", expand=True)
                self._sc_refresh_view()
            elif view == "youtube":
                self.yt_frame.pack(fill="both", expand=True)
                self._yt_refresh_view()
            elif view == "claude":
                self.claude_frame.pack(fill="both", expand=True)
            elif view == "help":
                self.help_frame.pack(fill="both", expand=True)
            self._update_tabs()

        if hasattr(self, '_fade_overlay'):
            self._fade_overlay.flash(_do_switch)
        else:
            _do_switch()


    def _open_playlist(self, name):
        def _do():
            self.active_playlist = name
            self.view = "playlist"
            self.view_title.config(text=f"▸ {name.upper()}")
            self._build_pl_actions(name)
            self.lib_frame.pack_forget()
            self.lib_frame.pack(fill="both", expand=True)
            self._refresh_tracks()
            self._update_tabs()
        if hasattr(self, '_fade_overlay'):
            self._fade_overlay.flash(_do)
        else:
            _do()


    def _clear_pl_actions(self):
        for w in self.pl_actions.winfo_children():
            w.destroy()

    def _build_pl_actions(self, name):
        self._clear_pl_actions()
        pa = tk.Label(self.pl_actions, text="▶ play all", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2")
        pa.pack(side="left", padx=6)
        pa.bind("<Button-1>", lambda e: self._play_playlist(name))
        pa.bind("<Enter>",    lambda e: pa.config(fg=C["white"]))
        pa.bind("<Leave>",    lambda e: pa.config(fg=C["white2"]))
        pd = tk.Label(self.pl_actions, text="delete", font=FMS, fg=C["red"], bg=C["bg"], cursor="hand2")
        pd.pack(side="left", padx=6)
        pd.bind("<Button-1>", lambda e: self._del_playlist(name))

    # ── TRACK LIST ────────────────────────
    def _get_tracks(self):
        q = self.search_var.get().lower()
        if self.view == "playlist" and self.active_playlist:
            idxs   = self.playlists.get(self.active_playlist, [])
            tracks = [(i, self.library[i]) for i in idxs if i < len(self.library)]
        else:
            tracks = list(enumerate(self.library))
        if q:
            tracks = [(i, t) for i, t in tracks
                      if q in t["title"].lower()
                      or q in t["artist"].lower()
                      or q in t.get("album", "").lower()]
        # Apply sort
        col   = getattr(self, "_sort_col", None)
        rev   = getattr(self, "_sort_rev", False)
        if col == "title":
            tracks.sort(key=lambda x: x[1]["title"].lower(), reverse=rev)
        elif col == "artist":
            tracks.sort(key=lambda x: x[1]["artist"].lower(), reverse=rev)
        elif col == "album":
            tracks.sort(key=lambda x: x[1].get("album", "").lower(), reverse=rev)
        elif col == "duration":
            tracks.sort(key=lambda x: x[1].get("duration", 0), reverse=rev)
        return tracks

    def _update_col_headers(self):
        """Update column header labels to show active sort indicator."""
        if not hasattr(self, "_col_lbls"):
            return
        col = getattr(self, "_sort_col", None)
        rev = getattr(self, "_sort_rev", False)
        _names = {"title": "TITLE", "artist": "ARTIST", "album": "ALBUM", "duration": "TIME"}
        for key, lbl in self._col_lbls.items():
            if key == col:
                arrow = " ▼" if rev else " ▲"
                lbl.config(text=_names[key] + arrow, fg=C["white"])
            else:
                lbl.config(text=_names[key], fg=C["white3"])

    def _refresh_tracks(self):
        if not hasattr(self, "track_list"):
            return
        self.track_list.delete("all")
        self._display_indices = []
        tracks = self._get_tracks()
        n = len(tracks)
        self.count_lbl.config(text=f"{n} track{'s' if n!=1 else ''}")
        if not tracks:
            return

        RH    = self._tl_row_h        # collapsed row height
        ZH    = 54                    # expanded (hover) row height
        ART   = ZH - 6               # art thumbnail size when expanded
        W     = max(self.track_list.winfo_width(), 400)
        hover = self._tl_hover_idx
        sel   = self._tl_sel_idx
        zoom_h = max(RH, min(ZH, getattr(self, "_tl_zoom_h", RH)))

        y = 0
        for row, (lib_idx, t) in enumerate(tracks):
            self._display_indices.append(lib_idx)
            is_hover = (row == hover)
            is_sel   = (lib_idx == self.current_idx)
            h = zoom_h if is_hover else RH

            # row background
            if is_sel:
                bg = C["select"]
            elif is_hover:
                bg = C["select2"]
            elif row % 2 == 1:
                bg = C["panel2"]
            else:
                bg = C["bg"]

            self.track_list.create_rectangle(0, y, W, y + h, fill=bg, outline="", tags=f"row{row}")

            # art thumbnail (only when hovered and art exists)
            text_x = 8
            if is_hover:
                art_path = t.get("art_path", "")
                if art_path and Path(art_path).exists():
                    photo = self._tl_get_art(lib_idx, art_path, ART)
                    if photo:
                        cx = 4 + ART // 2
                        cy = y + h // 2
                        self.track_list.create_image(cx, cy, image=photo, anchor="center")
                        text_x = ART + 10

            # track number
            fg_num = C["white3"]
            self.track_list.create_text(text_x, y + h // 2, text=f"{row+1}",
                anchor="w", font=("Courier New", 8), fill=fg_num)
            text_x += 28

            # title
            fg_title = C["white"] if (is_sel or is_hover) else C["white2"]
            title = t["title"]
            max_title = 36 if not is_hover else 30
            if len(title) > max_title:
                title = title[:max_title - 1] + "…"
            self.track_list.create_text(text_x, y + h // 2, text=title,
                anchor="w", font=("Courier New", 9, "bold" if is_sel else ""),
                fill=fg_title)

            # artist + album (shown on second line when hovered)
            if is_hover and h > RH + 4:
                artist = t.get("artist", "")[:28]
                album  = t.get("album", "")[:22]
                sub    = f"{artist}  —  {album}" if album and album != "Unknown" else artist
                self.track_list.create_text(text_x, y + h // 2 + 13, text=sub,
                    anchor="w", font=("Courier New", 8), fill=C["white3"])
            else:
                artist = t.get("artist", "")[:22]
                self.track_list.create_text(text_x + 260, y + h // 2, text=artist,
                    anchor="w", font=("Courier New", 9), fill=C["white3"])

            # duration (right-aligned)
            dur = self._fmt(t.get("duration", 0))
            self.track_list.create_text(W - 12, y + h // 2, text=dur,
                anchor="e", font=("Courier New", 8), fill=C["white3"])

            # playing indicator
            if is_sel:
                self.track_list.create_text(W - 50, y + h // 2, text="▶",
                    anchor="e", font=("Courier New", 8), fill=C["white"])

            y += h

        total_h = y
        self.track_list.configure(scrollregion=(0, 0, W, total_h))

    def _tl_get_art(self, lib_idx, art_path, size):
        """Return a cached PhotoImage for the track art, loading if needed."""
        key = (lib_idx, size)
        if key in self._tl_art_cache:
            return self._tl_art_cache[key]
        try:
            from PIL import Image, ImageTk
            img   = Image.open(art_path).convert("RGBA").resize((size, size))
            photo = ImageTk.PhotoImage(img)
        except Exception:
            try:
                photo = tk.PhotoImage(file=art_path)
            except Exception:
                return None
        self._tl_art_cache[key] = photo
        return photo

    def _tl_row_at(self, canvas_y):
        """Return the display row index at a given canvas y coordinate."""
        if not self._display_indices:
            return -1
        RH    = self._tl_row_h
        ZH    = 54
        hover = self._tl_hover_idx
        zoom_h = max(RH, min(ZH, getattr(self, "_tl_zoom_h", RH)))
        y = 0
        for row in range(len(self._display_indices)):
            h = zoom_h if row == hover else RH
            if y <= canvas_y < y + h:
                return row
            y += h
        return -1

    def _tl_canvas_y(self, event):
        """Convert event.y to canvas coordinate accounting for scroll."""
        return self.track_list.canvasy(event.y)

    def _tl_on_motion(self, event):
        cy  = self._tl_canvas_y(event)
        row = self._tl_row_at(cy)
        if row == self._tl_hover_idx:
            return
        old = self._tl_hover_idx
        self._tl_hover_idx = row
        # animate zoom
        if self._tl_zoom_job:
            self.root.after_cancel(self._tl_zoom_job)
            self._tl_zoom_job = None
        self._tl_zoom_h   = self._tl_row_h
        self._tl_zoom_row = row
        self._tl_animate_zoom(row, expanding=True)

    def _tl_on_leave(self, event=None):
        if self._tl_hover_idx == -1:
            return
        self._tl_hover_idx = -1
        if self._tl_zoom_job:
            self.root.after_cancel(self._tl_zoom_job)
            self._tl_zoom_job = None
        self._tl_zoom_h = self._tl_row_h
        self._refresh_tracks()

    def _tl_animate_zoom(self, target_row, expanding=True):
        RH, ZH = self._tl_row_h, 54
        step   = 6
        if expanding:
            self._tl_zoom_h = min(ZH, self._tl_zoom_h + step)
            done = self._tl_zoom_h >= ZH
        else:
            self._tl_zoom_h = max(RH, self._tl_zoom_h - step)
            done = self._tl_zoom_h <= RH
        self._refresh_tracks()
        if not done and self._tl_hover_idx == target_row:
            self._tl_zoom_job = self.root.after(12, lambda: self._tl_animate_zoom(target_row, expanding))

    def _refresh_queue(self):
        self.queue_list.delete(0, "end")
        for pos, lib_idx in enumerate(self.queue):
            if lib_idx >= len(self.library):
                continue
            t = self.library[lib_idx]
            m = "▶ " if pos == self.queue_pos else "  "
            self.queue_list.insert("end", f"{m}{t['title'][:40]}  —  {t['artist'][:20]}")
            if pos == self.queue_pos:
                self.queue_list.itemconfig("end", fg=C["white"])

    # ── PLAYLISTS ─────────────────────────
    def _create_playlist(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Playlist")
        dlg.configure(bg=C["panel"])
        dlg.geometry("320x140")
        dlg.resizable(False, False)
        tk.Label(dlg, text="PLAYLIST NAME", font=FM, fg=C["white3"], bg=C["panel"]).pack(pady=(18,6))
        var = tk.StringVar()
        e = tk.Entry(dlg, textvariable=var, font=FM, bg=C["bg"], fg=C["white"],
                     insertbackground=C["white"], relief="flat", bd=4, width=28)
        e.pack(); e.focus()
        def ok():
            n = var.get().strip()
            if n and n not in self.playlists:
                self.playlists[n] = []
                self._save()
                self._refresh_pl_sidebar()
            dlg.destroy()
        tk.Button(dlg, text="CREATE", font=FM, fg=C["white"], bg=C["border"],
                  relief="flat", bd=0, command=ok, cursor="hand2").pack(pady=10)
        e.bind("<Return>", lambda e: ok())

    def _del_playlist(self, name):
        if messagebox.askyesno("Delete", f'Delete playlist "{name}"?'):
            del self.playlists[name]
            self._save()
            self._refresh_pl_sidebar()
            self._switch_view("library")

    def _play_playlist(self, name):
        idxs = self.playlists.get(name, [])
        if idxs:
            self.queue     = list(idxs)
            self.queue_pos = 0
            self._play_item(0)

    def _add_to_pl_dialog(self, lib_idx):
        if not self.playlists:
            messagebox.showinfo("No Playlists", "Create a playlist first.")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Add to Playlist")
        dlg.configure(bg=C["panel"])
        dlg.geometry("260x200")
        tk.Label(dlg, text="SELECT PLAYLIST", font=FM, fg=C["white3"], bg=C["panel"]).pack(pady=(12,6))
        lb = tk.Listbox(dlg, bg=C["bg"], fg=C["white2"], font=FM,
                        selectbackground=C["select"], relief="flat", bd=0,
                        highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=12)
        for n in self.playlists:
            lb.insert("end", n)
        def add():
            s = lb.curselection()
            if s:
                n = lb.get(s[0])
                if lib_idx not in self.playlists[n]:
                    self.playlists[n].append(lib_idx)
                    self._save()
            dlg.destroy()
        tk.Button(dlg, text="ADD", font=FM, fg=C["white"], bg=C["border"],
                  relief="flat", bd=0, command=add, cursor="hand2").pack(pady=8)

    # ── FILE IMPORT ───────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Add Audio Files",
            filetypes=[
                ("Audio Files", "*.mp3 *.flac *.wav *.ogg *.m4a *.aac *.wma *.opus *.webm"),
                ("MP3 Files",   "*.mp3"),
                ("FLAC Files",  "*.flac"),
                ("WAV Files",   "*.wav"),
                ("All Files",   "*.*"),
            ])
        if paths:
            self._import(list(paths))

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"}
            paths = [str(p) for p in Path(folder).rglob("*")
                     if p.suffix.lower() in AUDIO_EXT]
            self._import(paths)

    def _import(self, paths):
        existing = {t["path"] for t in self.library}
        new_paths = [p for p in paths if p not in existing]
        if not new_paths:
            self._set_status("NO NEW FILES")
            return
        total = len(new_paths)
        # For small imports, process synchronously; for large ones, use a thread
        if total <= 20:
            self._import_batch(new_paths)
        else:
            self.status_lbl.config(text=f"[ IMPORTING {total} FILES… ]")
            def _worker():
                self._import_batch(new_paths, progress=True)
            threading.Thread(target=_worker, daemon=True).start()

    def _import_batch(self, paths, progress=False):
        """Process a list of new (non-duplicate) paths into the library."""
        added = 0
        total = len(paths)
        for i, p in enumerate(paths):
            try:
                m = self.engine.get_metadata(p)
                m["path"] = p
                if MUTAGEN_AVAILABLE:
                    try:
                        from mutagen import File as _MF2
                        _f = _MF2(p)
                        m["duration"] = _f.info.length if _f and _f.info else 0.0
                    except Exception:
                        m["duration"] = 0.0
                else:
                    m["duration"] = 0.0
                self.library.append(m)
                added += 1
            except Exception:
                pass
            if progress and (i + 1) % 10 == 0:
                self.root.after(0, lambda n=i+1, t=total:
                    self.status_lbl.config(text=f"[ {n}/{t} ]"))
        self._save()
        self.root.after(0, self._refresh_tracks)
        self.root.after(0, lambda: self.status_lbl.config(text=f"[+{added} TRACKS]"))

    # ── PLAYBACK ──────────────────────────
    def _on_dbl(self, event):
        cy  = self.track_list.canvasy(event.y)
        row = self._tl_row_at(cy)
        if row < 0 or row >= len(self._display_indices):
            return
        lib_idx        = self._display_indices[row]
        self.queue     = list(self._display_indices)
        self.queue_pos = self.queue.index(lib_idx)
        self._play_item(self.queue_pos)

    def _q_drag_press(self, event):
        self._q_drag_start = self.queue_list.nearest(event.y)

    def _q_drag_motion(self, event):
        if self._q_drag_start is None:
            return
        cur = self.queue_list.nearest(event.y)
        if cur != self._q_drag_start:
            # Visual feedback: highlight the target row
            self.queue_list.selection_clear(0, "end")
            self.queue_list.selection_set(cur)

    def _q_drag_release(self, event):
        if self._q_drag_start is None:
            return
        src = self._q_drag_start
        dst = self.queue_list.nearest(event.y)
        self._q_drag_start = None
        if src == dst or not self.queue:
            return
        if 0 <= src < len(self.queue) and 0 <= dst < len(self.queue):
            item = self.queue.pop(src)
            self.queue.insert(dst, item)
            # Adjust queue_pos to follow the currently playing item
            if self.queue_pos == src:
                self.queue_pos = dst
            elif src < self.queue_pos <= dst:
                self.queue_pos -= 1
            elif dst <= self.queue_pos < src:
                self.queue_pos += 1
            self._refresh_queue()
            self._set_status("QUEUE REORDERED")

    def _on_queue_dbl(self, event):
        sel = self.queue_list.curselection()
        if sel:
            self._play_item(sel[0])

    def _play_item(self, pos):
        if not self.queue or pos < 0 or pos >= len(self.queue):
            return
        self.queue_pos = pos
        lib_idx = self.queue[pos]
        if lib_idx >= len(self.library):
            return
        track = self.library[lib_idx]
        self.current_idx = lib_idx

        # ── Crossfade out current track ──
        xfade = int(self.settings.get("crossfade_sec", 0))
        if xfade > 0 and self.engine.is_playing:
            self._start_crossfade(xfade, lambda: self._do_load_track(track))
            return
        self._do_load_track(track)

    def _do_load_track(self, track):
        """Actually load + play a track (called directly or after crossfade)."""
        play_path = track["path"]
        eq_preset = self.settings.get("eq_preset", "flat")
        eq_tmp = None
        if eq_preset != "flat" and SCIPY_AVAILABLE:
            try:
                import tempfile
                fd, eq_tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                if EQProcessor.process(play_path, eq_preset, eq_tmp):
                    play_path = eq_tmp
                else:
                    # EQ processing failed — clean up and use original
                    try: os.unlink(eq_tmp)
                    except: pass
                    eq_tmp = None
            except Exception:
                eq_tmp = None

        # Clean up previous EQ temp file if any
        prev_tmp = getattr(self, "_eq_tmp_path", None)
        if prev_tmp and prev_tmp != play_path:
            try: os.unlink(prev_tmp)
            except: pass
        self._eq_tmp_path = eq_tmp

        self._stop_all_sources()
        self._active_source = "library"
        self._set_source_badge("library")
        loaded = self.engine.load(play_path)
        played = loaded and self.engine.play()
        if loaded and played:
            self.wavevis.set_active(True)
            self._set_logo_playing(True)
            self.btn_play.config(text="⏸")
            t = track["title"]
            self._anim_label_change(self.now_title,  (t[:36]+"…") if len(t)>37 else t)
            self._anim_label_change(self.now_artist, track.get("artist",""))
            self._anim_label_change(self.now_album,  track.get("album",""))
            if hasattr(self, "viz_track_lbl"):
                self.viz_track_lbl.config(text=f"▶  {t[:40]}  —  {track.get('artist','')[:24]}")
            self.lbl_tot.config(text=self._fmt(track.get("duration",0)))
            self._set_status("PLAYING")

            # ── Album art — embedded first, then MusicBrainz ──
            self._art_url_last = None
            _art_loaded = False
            art_path = track.get("art_path", "")
            if art_path and Path(art_path).exists():
                try:
                    self._load_art_bytes(Path(art_path).read_bytes())
                    _art_loaded = True
                except Exception:
                    pass
            if not _art_loaded:
                # Try embedded APIC tag via mutagen
                try:
                    from mutagen.id3 import ID3
                    tags = ID3(track["path"])
                    for tag in tags.values():
                        if hasattr(tag, "data") and tag.data:
                            self._load_art_bytes(tag.data)
                            _art_loaded = True
                            break
                except Exception:
                    pass
            if not _art_loaded:
                self._draw_art_placeholder()
                # async MusicBrainz fallback
                self._fetch_art_musicbrainz(
                    track.get("artist", ""), track.get("title", ""))

            # ── History ──
            self._history_add(track)

            # ── Last.fm ──
            if self._scrobbler and self.settings.get("lastfm_enabled") and self._scrobbler.ready:
                self._scrobbler.track_started(track)
                self._schedule_scrobble()

            # ── Discord RPC ──
            if self._discord_enabled:
                threading.Thread(
                    target=lambda: self._discord.set_activity(
                        track.get("title",""), track.get("artist",""),
                        elapsed_s=0, duration_s=track.get("duration",0)),
                    daemon=True).start()

            # ── Waveform seekbar ──
            self._load_waveform(play_path)

            # ── Lyrics + mini player ──
            self._fetch_lyrics(track.get("artist",""), t)
            self._mini_update()
            if getattr(self,"_flow_mode",False): self._flow_enqueue(track)
            if getattr(self,"_smart_skip_on",False):
                if self._skip_counts.get(track["path"],0) >= 3:
                    self.root.after(200, self._next); return
            self._start_lyric_ticker()
            self._update_context_sidebar(track)
        else:
            self._active_source = "none"
            self._set_source_badge("none")
            self._set_status("LOAD FAILED")
            fname = Path(play_path).name
            self.now_title.config(text="⚠  LOAD FAILED")
            self.now_artist.config(text=fname[:50])
            self.now_album.config(text="")
            err = getattr(self.engine, "_last_error", "")
            if not getattr(self.engine, "_pygame", None):
                messagebox.showerror("OTERNOS // AUDIO ERROR",
                    "pygame is not available.\n\nRun: pip install pygame\nThen rebuild the exe.")
            else:
                messagebox.showerror("OTERNOS // PLAYBACK ERROR",
                    f"Could not play:\n{fname}\n\n"
                    + (f"Error: {err}\n\n" if err else "")
                    + "Supported formats: MP3, WAV, OGG, FLAC")
        self._refresh_tracks()
        if self.view == "queue":
            self._refresh_queue()

    def _anim_label_change(self, widget, new_text, base_col=None):
        """Fade label out, swap text, fade back in."""
        if base_col is None:
            base_col = widget.cget("fg")
        def _do_swap():
            widget.config(text=new_text)
            ColorAnim.run(self.root, widget, "fg", C["bg"], base_col, duration_ms=100)
        ColorAnim.run(self.root, widget, "fg", base_col, C["bg"],
                      duration_ms=100, on_done=_do_swap)

    def _set_status(self, text):
        """Flash status label with a brief bright pulse."""
        self.status_lbl.config(text=text)
        ColorAnim.run(self.root, self.status_lbl, "fg", C["white"], C["white3"], duration_ms=600)


    def _toggle_play(self):
        if self._sp_mode or self._active_source == "spotify":
            self._sp_playpause()
            return
        # YouTube / SoundCloud / library all use the local engine
        if self.engine.is_playing:
            self.engine.pause()
            self.btn_play.config(text="▶")
            self.wavevis.set_active(False)
            self._set_logo_playing(False)
            self._set_status("PAUSED")
            self._mini_update()
        elif self.engine.is_paused:
            self.engine.unpause()
            self.btn_play.config(text="⏸")
            self.wavevis.set_active(True)
            self._set_logo_playing(True)
            self._set_status("PLAYING")
            self._mini_update()
        elif self.queue and self._active_source in ("library", "none"):
            self._play_item(max(0, self.queue_pos))

    def _next(self):
        if self._sp_mode or self._active_source == "spotify":
            threading.Thread(target=self.sp_api.next_track, daemon=True).start()
            return
        if self._active_source in ("youtube", "soundcloud"):
            self._stop_all_sources()
            self._active_source = "none"
            self._set_source_badge("none")
            if not self.queue:
                return
            self.queue_pos = (self.queue_pos + 1) % len(self.queue)
            self._play_item(self.queue_pos)
            return
        if not self.queue:
            return
        if getattr(self,"_smart_skip_on",False):
            idx = self.current_idx
            if 0 <= idx < len(self.library):
                pos = self.engine.get_position(); dur = self.engine.duration
                if dur > 0 and pos/dur < 0.35:
                    path = self.library[idx]["path"]
                    self._skip_counts[path] = self._skip_counts.get(path,0)+1
        if self.shuffle:
            self.queue_pos = random.randint(0, len(self.queue)-1)
        else:
            self.queue_pos = (self.queue_pos+1) % len(self.queue)
        self._play_item(self.queue_pos)

    def _prev(self):
        if self._sp_mode or self._active_source == "spotify":
            threading.Thread(target=self.sp_api.prev_track, daemon=True).start()
            return
        if self._active_source in ("youtube", "soundcloud"):
            self._stop_all_sources()
            self._active_source = "none"
            self._set_source_badge("none")
            if not self.queue:
                return
            self.queue_pos = (self.queue_pos - 1) % len(self.queue)
            self._play_item(self.queue_pos)
            return
        if not self.queue:
            return
        if self.engine.get_position() > 5:
            self.engine.seek(0)
        else:
            self.queue_pos = (self.queue_pos-1) % len(self.queue)
            self._play_item(self.queue_pos)

    def _seek_relative(self, delta_s):
        """Seek forward/backward by delta_s seconds."""
        if self._sp_mode and self._sp_dur_ms > 0:
            ms = max(0, min(self._sp_dur_ms, self._sp_pos_ms + int(delta_s * 1000)))
            self._sp_pos_ms = ms
            threading.Thread(target=lambda: self.sp_api.seek(ms), daemon=True).start()
        elif self.engine.duration > 0:
            pos = self.engine._pos_cache
            self.engine.seek(max(0, min(self.engine.duration, pos + delta_s)))
        self._set_status(f"{'+'if delta_s>0 else ''}{int(delta_s)}s")


        self.shuffle = not self.shuffle
        self.btn_shuf.config(fg=C["glow"] if self.shuffle else C["white2"])

    def _toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.btn_shuf.config(fg=C["glow"] if self.shuffle else C["white2"])

    def _toggle_repeat(self):
        modes = ["off","all","one"]
        self.repeat_mode = modes[(modes.index(self.repeat_mode)+1) % 3]
        self.btn_repeat.config(
            text={"off":"↺","all":"↺","one":"↻"}[self.repeat_mode],
            fg=C["white2"] if self.repeat_mode=="off" else C["glow"])

    def _clear_queue(self):
        self.queue = []
        self.queue_pos = -1
        self._refresh_queue()

    # ── SEEK ──────────────────────────────
    def _seek_press(self, event):
        """Mark seeking on press; actual seek happens on release."""
        self.seeking = True
        w = self.prog_cv.winfo_width() or 1
        r = max(0, min(1, event.x / w))
        self._draw_prog(r)
        # Update time label immediately for responsiveness
        if self._sp_mode and self._sp_dur_ms > 0:
            self._sp_pos_ms = int(r * self._sp_dur_ms)
            self.lbl_cur.config(text=self._fmt(self._sp_pos_ms / 1000))
        elif self.engine.duration > 0:
            self.lbl_cur.config(text=self._fmt(r * self.engine.duration))

    def _seek_drag(self, event):
        if not self.seeking:
            return
        w = self.prog_cv.winfo_width() or 1
        r = max(0, min(1, event.x / w))
        self._draw_prog(r)
        # Update time label during drag
        if self._sp_mode and self._sp_dur_ms > 0:
            self._sp_pos_ms = int(r * self._sp_dur_ms)
            self.lbl_cur.config(text=self._fmt(self._sp_pos_ms / 1000))
        elif self.engine.duration > 0:
            self.lbl_cur.config(text=self._fmt(r * self.engine.duration))

    def _seek_end(self, event):
        if not self.seeking:
            return
        self.seeking = False
        w = self.prog_cv.winfo_width() or 1
        r = max(0, min(1, event.x / w))
        if self._sp_mode and self._sp_dur_ms > 0:
            ms = int(r * self._sp_dur_ms)
            self._sp_pos_ms = ms
            threading.Thread(target=lambda: self.sp_api.seek(ms), daemon=True).start()
        elif self.engine.duration > 0:
            self.engine.seek(r * self.engine.duration)

    def _draw_prog(self, r):
        w = self.prog_cv.winfo_width()
        if not hasattr(self, '_prog_r_cur'):
            self._prog_r_cur = r
        # Snap on seek, ease during normal playback
        if self.seeking or abs(r - self._prog_r_cur) > 0.05:
            self._prog_r_cur = r
        else:
            self._prog_r_cur += (r - self._prog_r_cur) * 0.25
        x = self._prog_r_cur * w
        self.prog_cv.coords(self.prog_fill, 0, 0, x, 4)
        self.prog_cv.coords(self.prog_dot,  x-4, -2, x+4, 6)
        if getattr(self, "_waveform_data", None):
            self._draw_waveform_seekbar()


    # ── VOLUME ────────────────────────────
    VOL_W     = 152
    VOL_OFF   = 14
    VOL_CY    = 32
    VOL_TICKS = 8

    def _vol_x_to_vol(self, x):
        return max(0.0, min(1.0, (x - self.VOL_OFF) / self.VOL_W))

    def _vol_hover(self, entering):
        if self._vol_hover_job:
            self.root.after_cancel(self._vol_hover_job)
            self._vol_hover_job = None
        self._vol_animate_hover(1.0 if entering else 0.0)

    def _vol_animate_hover(self, target):
        diff = target - self._vol_glow
        if abs(diff) < 0.02:
            self._vol_glow = target
            self._upd_vol()
            return
        self._vol_glow += diff * 0.22
        self._upd_vol()
        self._vol_hover_job = self.root.after(16 if HW_ACCEL else 50, lambda: self._vol_animate_hover(target))

    def _vol_press(self, e):
        self._vol_dragging = True
        vol = self._vol_x_to_vol(e.x)
        self.engine.set_volume(vol)
        self._upd_vol()
        self._sp_vol_debounce(int(vol * 100))

    def _vol_drag(self, e):
        vol = self._vol_x_to_vol(e.x)
        self.engine.set_volume(vol)
        self._upd_vol()
        self._sp_vol_debounce(int(vol * 100))

    def _vol_release(self, e):
        self._vol_dragging = False
        if self._sp_mode:
            if hasattr(self, "_sp_vol_job") and self._sp_vol_job:
                self.root.after_cancel(self._sp_vol_job)
                self._sp_vol_job = None
            pct = int(self.engine.volume * 100)
            threading.Thread(target=lambda: self.sp_api.volume(pct), daemon=True).start()

    def _vol_scroll(self, e):
        delta = 0.05 if e.delta > 0 else -0.05
        self.engine.set_volume(self.engine.volume + delta)
        self._upd_vol()
        self._sp_vol_debounce(int(self.engine.volume * 100))

    def _sp_vol_debounce(self, pct):
        if not self._sp_mode:
            return
        if hasattr(self, "_sp_vol_job") and self._sp_vol_job:
            self.root.after_cancel(self._sp_vol_job)
        self._sp_vol_job = self.root.after(
            250, lambda p=pct: threading.Thread(
                target=lambda: self.sp_api.volume(p), daemon=True).start())

    def _set_vol(self, x):
        """Kept for keyboard shortcuts (Up/Down arrows)."""
        vol = max(0.0, min(1.0, x / self.VOL_W))
        self.engine.set_volume(vol)
        self._upd_vol()
        self._sp_vol_debounce(int(vol * 100))

    def _upd_vol(self):
        cv  = self.vol_cv
        cv.delete("all")
        W   = self.VOL_W
        off = self.VOL_OFF
        cy  = self.VOL_CY
        vol = self.engine.volume
        g   = self._vol_glow if hasattr(self, "_vol_glow") else 0.0

        track_h = 3 + int(g * 3)
        ty1 = cy - track_h // 2
        ty2 = cy + track_h // 2 + track_h % 2

        # background track
        tr_br = 28 + int(g * 14)
        cv.create_rectangle(off, ty1, off + W, ty2,
                            fill=f"#{tr_br:02x}{tr_br:02x}{tr_br:02x}", outline="")

        # filled portion
        fill_x = off + int(vol * W)
        if fill_x > off:
            fb = 130 + int(g * 125)
            fb = min(255, fb)
            cv.create_rectangle(off, ty1, fill_x, ty2,
                                fill=f"#{fb:02x}{fb:02x}{fb:02x}", outline="")
            hb = min(255, fb + 70)
            cv.create_line(off, ty1, fill_x, ty1,
                           fill=f"#{hb:02x}{hb:02x}{hb:02x}", width=1)

        # segment tick marks
        for i in range(1, self.VOL_TICKS):
            tx = off + int(i / self.VOL_TICKS * W)
            filled = tx <= fill_x
            tb = 52 if filled else 40
            cv.create_line(tx, cy - track_h - 2, tx, cy + track_h + 2,
                           fill=f"#{tb:02x}{tb:02x}{tb:02x}", width=1)

        # scrubber dot
        dot_r = 4 + int(g * 3)
        db = 190 + int(g * 65)
        db = min(255, db)
        cv.create_oval(fill_x - dot_r, cy - dot_r,
                       fill_x + dot_r, cy + dot_r,
                       fill=f"#{db:02x}{db:02x}{db:02x}", outline="")
        if dot_r >= 5:
            cv.create_oval(fill_x - 2, cy - 2, fill_x + 2, cy + 2,
                           fill="#ffffff", outline="")

        # corner bracket accents
        bk = 45 + int(g * 65)
        bc = f"#{bk:02x}{bk:02x}{bk:02x}"
        for sx, dx in [(off - 4, 5), (off + W + 4, -5)]:
            for sy, dy in [(ty1 - 3, 5), (ty2 + 3, -5)]:
                cv.create_line(sx, sy, sx + dx, sy, fill=bc)
                cv.create_line(sx, sy, sx, sy + dy, fill=bc)

        # VOL label + percentage
        lbl_br = 75 + int(g * 85)
        lc = f"#{lbl_br:02x}{lbl_br:02x}{lbl_br:02x}"
        cv.create_text(off, cy - 15, text="VOL",
                       anchor="w", font=("Courier New", 7, "bold"), fill=lc)
        cv.create_text(off + W, cy - 15, text=f"{int(vol*100):>3}%",
                       anchor="e", font=("Courier New", 7, "bold"), fill=lc)


    # ── RIGHT CLICK MENU ──────────────────
    def _on_rclick(self, event):
        cy  = self.track_list.canvasy(event.y)
        row = self._tl_row_at(cy)
        if row < 0 or row >= len(self._display_indices):
            return
        lib_idx = self._display_indices[row]
        m = tk.Menu(self.root, bg=C["panel"], fg=C["white"], font=FMS,
                    relief="flat", activebackground=C["select2"],
                    activeforeground=C["white"], tearoff=0)
        m.add_command(label="▶  Play Now",           command=lambda: self._play_single(lib_idx))
        m.add_command(label="+  Add to Queue",        command=lambda: self._add_to_queue(lib_idx))
        m.add_separator()
        m.add_command(label="✎  Edit Tags",           command=lambda: self._open_tag_editor(lib_idx))
        m.add_command(label="🖼  Set Cover Image",     command=lambda: self._set_track_art(lib_idx))
        m.add_command(label="✕  Clear Cover Image",    command=lambda: self._clear_track_art(lib_idx))
        m.add_separator()
        m.add_command(label="♦  Add to Playlist…",   command=lambda: self._add_to_pl_dialog(lib_idx))
        if self.view == "playlist":
            m.add_command(label="↗  Export Playlist M3U",
                          command=lambda: self._export_playlist_m3u(self.active_playlist))
            m.add_command(label="[X]  Remove from Playlist",
                          command=lambda: self._rm_from_pl(lib_idx))
        m.add_separator()
        m.add_command(label="[X]  Remove from Library", command=lambda: self._rm_from_lib(lib_idx))
        m.post(event.x_root, event.y_root)

    def _play_single(self, lib_idx):
        self.queue = [lib_idx]
        self.queue_pos = 0
        self._play_item(0)

    def _add_to_queue(self, lib_idx):
        self.queue.append(lib_idx)
        if self.queue_pos < 0:
            self.queue_pos = 0
        self.status_lbl.config(text="[ QUEUED ]")

    def _rm_from_pl(self, lib_idx):
        if self.active_playlist:
            pl = self.playlists[self.active_playlist]
            if lib_idx in pl:
                pl.remove(lib_idx)
            self._save()
            self._refresh_tracks()

    def _rm_from_lib(self, lib_idx):
        if lib_idx < len(self.library):
            self.library.pop(lib_idx)
            # Remap playlist indices
            for n in self.playlists:
                self.playlists[n] = [i if i < lib_idx else i-1
                                     for i in self.playlists[n] if i != lib_idx]
            # Remap queue indices
            self.queue = [i if i < lib_idx else i-1
                          for i in self.queue if i != lib_idx]
            if self.current_idx == lib_idx:
                self.current_idx = -1
            elif self.current_idx > lib_idx:
                self.current_idx -= 1
            self._save()
            self._refresh_tracks()

    # ── TRACK COVER ART ───────────────────
    def _set_track_art(self, lib_idx):
        if lib_idx >= len(self.library):
            return
        path = filedialog.askopenfilename(
            title="Select Cover Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("All files", "*.*")])
        if path:
            self.library[lib_idx]["art_path"] = path
            self._save()
            self._set_status("COVER SET")

    def _clear_track_art(self, lib_idx):
        if lib_idx >= len(self.library):
            return
        self.library[lib_idx].pop("art_path", None)
        self._save()
        self._set_status("COVER CLEARED")

    # ── LYRICS VIEW ───────────────────────
    def _build_lyrics_view(self):
        self.lyrics_frame = tk.Frame(self.content, bg=C["bg"])

        hdr = tk.Frame(self.lyrics_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="LYRICS", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self._lyrics_src_lbl = tk.Label(hdr, text="", font=FMS, fg=C["white3"], bg=C["bg"])
        self._lyrics_src_lbl.pack(side="left", padx=12)
        self._lyrics_sync_badge = tk.Label(hdr, text="", font=FMS, fg=C["white3"], bg=C["bg"])
        self._lyrics_sync_badge.pack(side="right", padx=8)

        tk.Frame(self.lyrics_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 0))

        self._lyrics_track_lbl = tk.Label(
            self.lyrics_frame, text="— NO TRACK —",
            font=("Courier New", 10, "bold"), fg=C["white2"], bg=C["bg"], anchor="w")
        self._lyrics_track_lbl.pack(fill="x", padx=24, pady=(10, 0))

        lf = tk.Frame(self.lyrics_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=0, pady=8)
        self._lyrics_sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                                       width=6, bd=0, highlightthickness=0)
        self._lyrics_sb.pack(side="right", fill="y")
        self._lyrics_cv = tk.Canvas(lf, bg=C["bg"], highlightthickness=0,
                                    yscrollcommand=self._lyrics_sb.set)
        self._lyrics_cv.pack(side="left", fill="both", expand=True)
        self._lyrics_sb.config(command=self._lyrics_cv.yview)
        self._lyrics_inner = tk.Frame(self._lyrics_cv, bg=C["bg"])
        self._lyrics_win   = self._lyrics_cv.create_window(
            0, 0, anchor="nw", window=self._lyrics_inner)
        self._lyrics_inner.bind("<Configure>", self._on_lyrics_inner_resize)
        self._lyrics_cv.bind("<Configure>",    self._on_lyrics_cv_resize)
        self._lyrics_cv.bind("<MouseWheel>",
            lambda e: self._lyrics_cv.yview_scroll(
                -1*(1 if e.delta > 0 else -1), "units"))

    def _on_lyrics_inner_resize(self, e):
        self._lyrics_cv.configure(scrollregion=self._lyrics_cv.bbox("all"))

    def _on_lyrics_cv_resize(self, e):
        self._lyrics_cv.itemconfig(self._lyrics_win, width=e.width)

    def _refresh_lyrics_view(self):
        title  = self.now_title.cget("text").replace("…","").strip()
        artist = self.now_artist.cget("text").strip()
        if not title or title == "— NO TRACK —":
            self._set_lyrics_lines(["— Play a track to see lyrics —"], synced=False)
            return
        self._lyrics_track_lbl.config(text=f"{artist}  //  {title}")
        key = (artist.lower().strip(), title.lower().strip())
        cached = self._lyrics_cache.get(key, "MISSING")
        if cached == "MISSING":
            self._set_lyrics_lines(["[ Searching lyrics… ]"], synced=False)
            self._fetch_lyrics(artist, title)
        elif cached is None:
            self._set_lyrics_lines(["[ Searching lyrics… ]"], synced=False)
        else:
            synced = self._synced_cache.get(key)
            if synced:
                self._load_synced_lyrics(synced)
            else:
                self._set_lyrics_lines(cached.splitlines(), synced=False)
            self._lyrics_src_lbl.config(text="[ lrclib.net ]")

    def _set_lyrics_lines(self, lines, synced=False):
        """Rebuild inner frame with one Label per line."""
        self._stop_lyrics_sync()
        for w in self._lyrics_inner.winfo_children():
            w.destroy()
        self._lyrics_lines        = []
        self._lyrics_active_line  = -1
        font_normal = ("Courier New", 12)
        font_active = ("Courier New", 13, "bold")
        tk.Frame(self._lyrics_inner, bg=C["bg"], height=18).pack()
        for line in lines:
            text = line.strip()
            if not text:
                tk.Frame(self._lyrics_inner, bg=C["bg"], height=10).pack()
                self._lyrics_lines.append(None)
                continue
            lbl = tk.Label(
                self._lyrics_inner, text=text,
                font=font_normal, fg=C["white3"], bg=C["bg"],
                anchor="center", justify="center",
                wraplength=580, cursor="arrow", pady=5)
            lbl.pack(fill="x", padx=40)
            lbl._font_normal = font_normal
            lbl._font_active = font_active
            self._lyrics_lines.append(lbl)
        tk.Frame(self._lyrics_inner, bg=C["bg"], height=60).pack()
        self._lyrics_cv.yview_moveto(0)
        if synced:
            self._lyrics_sync_badge.config(text="[ ◈ SYNCED ]", fg=C["white3"])
        else:
            self._lyrics_sync_badge.config(text="[ STATIC ]",   fg=C["white3"])

    def _load_synced_lyrics(self, synced_lines):
        """synced_lines: list of (ms, text). Build labels, attach timestamps, start ticker."""
        lines = [text for _, text in synced_lines]
        self._set_lyrics_lines(lines, synced=True)
        timed  = []
        slot_i = 0
        for ms, text in synced_lines:
            text = text.strip()
            while slot_i < len(self._lyrics_lines):
                slot = self._lyrics_lines[slot_i]
                slot_i += 1
                if slot is not None:
                    timed.append((ms, slot))
                    break
        self._lyrics_timed       = timed
        self._lyrics_active_line = -1
        self._start_lyrics_sync()

    def _start_lyrics_sync(self):
        self._stop_lyrics_sync()
        self._lyrics_sync_tick()

    def _stop_lyrics_sync(self):
        if self._lyrics_sync_job:
            try: self.root.after_cancel(self._lyrics_sync_job)
            except: pass
        self._lyrics_sync_job = None
        self._lyrics_timed    = []

    def _lyrics_sync_tick(self):
        if self.view != "lyrics":
            self._lyrics_sync_job = self.root.after(200, self._lyrics_sync_tick)
            return
        timed = getattr(self, "_lyrics_timed", [])
        if not timed:
            return
        try:
            if self._sp_mode and self._sp_dur_ms > 0:
                pos_ms = self._sp_pos_ms
            else:
                pos_ms = self.engine._pos_cache * 1000
        except Exception:
            pos_ms = 0

        # Find the last line whose timestamp is <= current position
        active = -1
        for i, (ms, _) in enumerate(timed):
            if ms <= pos_ms:
                active = i
            else:
                break

        # Always repaint — catches paused-at-start and seek jumps
        if active != self._lyrics_active_line:
            self._lyrics_active_line = active
            for i, (ms, lbl) in enumerate(timed):
                dist = i - active   # positive = upcoming, negative = past
                if i == active:
                    lbl.config(fg=C["glow"],    font=lbl._font_active)
                elif dist == 1:                 # next line
                    lbl.config(fg=C["white3"],  font=lbl._font_normal)
                elif dist == 2:
                    lbl.config(fg="#555555",    font=lbl._font_normal)
                elif dist == -1:               # just-passed line
                    lbl.config(fg="#444444",    font=lbl._font_normal)
                else:
                    lbl.config(fg="#222222",    font=lbl._font_normal)
            if 0 <= active < len(timed):
                self._scroll_to_lyric_line(active)

        self._lyrics_sync_job = self.root.after(80, self._lyrics_sync_tick)

    def _scroll_to_lyric_line(self, idx):
        """Scroll so the active line is centred vertically in the canvas."""
        try:
            _, lbl = self._lyrics_timed[idx]
            lbl.update_idletasks()
            # Walk up widget tree to accumulate y offset relative to canvas
            y = 0
            w = lbl
            while w != self._lyrics_cv and w is not None:
                y += w.winfo_y()
                w  = w.master
            lbl_h   = lbl.winfo_height()
            cv_h    = self._lyrics_cv.winfo_height()
            inner_h = self._lyrics_inner.winfo_height()
            if inner_h <= cv_h or cv_h < 1:
                return
            # Centre the line in the viewport
            target = (y + lbl_h / 2 - cv_h / 2) / inner_h
            target = max(0.0, min(1.0, target))
            self._lyrics_cv.yview_moveto(target)
        except Exception:
            pass

    def _fetch_lyrics(self, artist, title):
        if not artist or not title:
            return
        key = (artist.lower().strip(), title.lower().strip())
        if key in self._lyrics_cache:
            return
        self._lyrics_cache[key] = None   # in-flight

        def _parse_lrc(lrc_text):
            import re
            # Matches [mm:ss.xx] or [mm:ss.xxx]
            pattern = re.compile(r"\[(\d+):(\d+)[\.:](\d+)\](.*)")
            lines = []
            for raw in lrc_text.splitlines():
                m = pattern.match(raw.strip())
                if m:
                    mins  = int(m.group(1))
                    secs  = int(m.group(2))
                    frac  = m.group(3)
                    # 2-digit = hundredths (×10 to get ms), 3-digit = ms already
                    frac_ms = int(frac) * 10 if len(frac) == 2 else int(frac)
                    ms    = (mins * 60 + secs) * 1000 + frac_ms
                    text  = m.group(4).strip()
                    if text:
                        lines.append((ms, text))
            return sorted(lines, key=lambda x: x[0])

        def _worker():
            plain  = ""
            synced = None
            source = ""

            # Source 1: lrclib.net — prefers synced LRC
            try:
                url = "https://lrclib.net/api/search?artist_name={}&track_name={}".format(
                    urllib.parse.quote(artist), urllib.parse.quote(title))
                req = urllib.request.Request(
                    url, headers={"User-Agent": "OternosPlayer/1.0",
                                  "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    results = json.loads(r.read().decode())
                if results:
                    best       = results[0]
                    plain_text = best.get("plainLyrics",  "").strip()
                    synced_lrc = best.get("syncedLyrics", "").strip()
                    if synced_lrc:
                        parsed = _parse_lrc(synced_lrc)
                        if parsed:
                            synced = parsed
                            plain  = plain_text or "\n".join(t for _, t in parsed)
                            source = "lrclib.net"
                    elif plain_text:
                        plain  = plain_text
                        source = "lrclib.net"
            except Exception:
                pass

            # Source 2: Musixmatch plain fallback
            if not plain:
                try:
                    q    = urllib.parse.quote(f"{artist} {title}")
                    url  = f"https://api.musixmatch.com/ws/1.1/track.search?q={q}&page_size=1&page=1&s_track_rating=desc&apikey=b6de7a5a69bef03d45e9f5ccabeaa7c5"
                    req  = urllib.request.Request(url, headers={"User-Agent":"OternosPlayer/1.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = json.loads(r.read().decode())
                    items = data.get("message",{}).get("body",{}).get("track_list",[])
                    if items:
                        tid  = items[0]["track"]["track_id"]
                        url2 = f"https://api.musixmatch.com/ws/1.1/track.lyrics.get?track_id={tid}&apikey=b6de7a5a69bef03d45e9f5ccabeaa7c5"
                        with urllib.request.urlopen(
                                urllib.request.Request(url2, headers={"User-Agent":"OternosPlayer/1.0"}),
                                timeout=8) as r2:
                            d2 = json.loads(r2.read().decode())
                        body = d2.get("message",{}).get("body",{}).get("lyrics",{}).get("lyrics_body","").strip()
                        if body and "****" not in body:
                            plain  = body
                            source = "musixmatch"
                except Exception:
                    pass

            # Source 3: lyrics.ovh
            if not plain:
                try:
                    url = "https://api.lyrics.ovh/v1/{}/{}".format(
                        urllib.parse.quote(artist), urllib.parse.quote(title))
                    req = urllib.request.Request(url, headers={"User-Agent":"OternosPlayer/1.0"})
                    with urllib.request.urlopen(req, timeout=6) as r:
                        data = json.loads(r.read().decode())
                    candidate = data.get("lyrics","").strip()
                    if candidate:
                        plain  = candidate
                        source = "lyrics.ovh"
                except Exception:
                    pass

            if not plain:
                plain  = "[ No lyrics found ]"
                source = ""

            self._lyrics_cache[key] = plain
            self._synced_cache[key] = synced
            self.root.after(0, lambda: self._on_lyrics_fetched(artist, title, plain, synced, source))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_lyrics_fetched(self, artist, title, plain, synced, source=""):
        cur_title  = self.now_title.cget("text").replace("…","").strip().lower()
        cur_artist = self.now_artist.cget("text").strip().lower()
        ta = artist.lower().strip()
        tt = title.lower().strip()
        title_match  = cur_title in tt or tt.startswith(cur_title) or cur_title.startswith(tt[:20])
        artist_match = cur_artist in ta or ta in cur_artist or not cur_artist
        if not (title_match or artist_match):
            return
        self._lyrics_src_lbl.config(text=f"[ {source} ]" if source else "")
        self._lyrics_track_lbl.config(
            text=f"{artist}  //  {title}" if artist else title)
        if self.view == "lyrics":
            if synced:
                self._load_synced_lyrics(synced)
            else:
                self._set_lyrics_lines(plain.splitlines(), synced=False)

    def _show_lyrics(self, text, source):
        """Compat shim for older call sites."""
        self._lyrics_src_lbl.config(text=f"[ {source} ]" if source else "")
        self._set_lyrics_lines(text.splitlines() if text else [], synced=False)


    # ── SLEEP TIMER ───────────────────────
    def _open_sleep_timer(self):
        win = tk.Toplevel(self.root)
        win.title("SLEEP TIMER")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.geometry("320x260")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="SLEEP TIMER", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(20,4))
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20)

        # Countdown display
        self._sleep_disp = tk.Label(win, text=self._sleep_display(),
                                    font=("Courier New", 28, "bold"),
                                    fg=C["glow"], bg=C["bg"])
        self._sleep_disp.pack(pady=(16, 8))

        # Presets
        presets = tk.Frame(win, bg=C["bg"])
        presets.pack()
        for mins in [15, 30, 45, 60, 90]:
            b = tk.Label(presets, text=f"{mins}m", font=FM,
                         fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=8, pady=4)
            b.pack(side="left", padx=3)
            b.bind("<Button-1>", lambda e, m=mins: self._set_sleep(m, win))
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

        # Cancel button
        btn_frame = tk.Frame(win, bg=C["bg"])
        btn_frame.pack(pady=14)
        cancel_b = tk.Label(btn_frame, text="[ CANCEL ]", font=FM,
                            fg=C["white3"], bg=C["bg"], cursor="hand2")
        cancel_b.pack(side="left", padx=8)
        cancel_b.bind("<Button-1>", lambda e: self._cancel_sleep(win))
        cancel_b.bind("<Enter>",    lambda e: cancel_b.config(fg=C["red"]))
        cancel_b.bind("<Leave>",    lambda e: cancel_b.config(fg=C["white3"]))

        # Live update the display every second
        def _tick():
            if not win.winfo_exists():
                return
            self._sleep_disp.config(text=self._sleep_display())
            win.after(1000, _tick)
        _tick()

    def _sleep_display(self):
        if self._sleep_end_time is None:
            return "OFF"
        remaining = max(0, self._sleep_end_time - time.time())
        m = int(remaining // 60)
        s = int(remaining % 60)
        return f"{m:02d}:{s:02d}"

    def _set_sleep(self, minutes, win=None):
        if self._sleep_job:
            self.root.after_cancel(self._sleep_job)
        self._sleep_minutes  = minutes
        self._sleep_end_time = time.time() + minutes * 60
        self._poll_sleep()
        self._set_status(f"SLEEP {minutes}m")
        if win and win.winfo_exists():
            win.destroy()

    def _cancel_sleep(self, win=None):
        if self._sleep_job:
            self.root.after_cancel(self._sleep_job)
            self._sleep_job = None
        self._sleep_end_time = None
        self._sleep_minutes  = 0
        self._set_status("SLEEP OFF")
        if win and win.winfo_exists():
            win.destroy()

    def _poll_sleep(self):
        if self._sleep_end_time is None:
            return
        remaining = self._sleep_end_time - time.time()
        # Update status label with countdown
        if remaining > 0:
            m = int(remaining // 60)
            s = int(remaining % 60)
            self.status_lbl.config(text=f"⏾ {m:02d}:{s:02d}")
            self._sleep_job = self.root.after(1000, self._poll_sleep)
        else:
            # Time's up — fade volume to zero then stop
            self._sleep_end_time = None
            self._sleep_job      = None
            self._sleep_fade_stop()

    def _sleep_fade_stop(self, vol=None):
        """Gradually fade volume to 0 then stop playback."""
        if vol is None:
            vol = self.settings.get("volume", 80)
        if vol > 0:
            new_vol = max(0, vol - 4)
            self.engine.set_volume(new_vol)
            self.root.after(120, lambda: self._sleep_fade_stop(new_vol))
        else:
            self.engine.pause()
            self.btn_play.config(text="▶")
            self.wavevis.set_active(False)
            self._set_logo_playing(False)
            self.status_lbl.config(text="SLEEP zzz")
            # Restore volume for next time
            self.engine.set_volume(self.settings.get("volume", 80))

    # ── MINI PLAYER ───────────────────────
    def _toggle_mini_player(self):
        if self._mini_win and self._mini_win.winfo_exists():
            self._mini_win.destroy()
            self._mini_win = None
            self.root.deiconify()
        else:
            self._open_mini_player()

    def _open_mini_player(self):
        self.root.withdraw()
        W, H = 420, 116
        # Position bottom-right of screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        gx, gy = sw - W - 24, sh - H - 60

        win = tk.Toplevel()
        win.title("OTERNOS")
        win.geometry(f"{W}x{H}+{gx}+{gy}")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", 0.96)
        self._mini_win      = win
        self._mini_topmost  = True
        self._mini_prog_r   = 0.0   # smooth progress ratio
        self._mini_drag_x   = None
        self._mini_seeking  = False

        try: win.iconphoto(False, self._icon_img)
        except: pass

        # ── drag (only from non-interactive areas) ──
        def _drag_start(e):
            win._mx = e.x_root - win.winfo_x()
            win._my = e.y_root - win.winfo_y()
        def _drag_move(e):
            nx = e.x_root - win._mx
            ny = e.y_root - win._my
            # Snap to screen edges within 20px
            if abs(nx) < 20:                   nx = 0
            if abs(ny) < 20:                   ny = 0
            if abs(nx - (sw - W)) < 20:        nx = sw - W
            if abs(ny - (sh - H - 48)) < 20:   ny = sh - H - 48
            win.geometry(f"+{nx}+{ny}")

        # ── outer border glow frame ──
        outer = tk.Frame(win, bg=C["border"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # ── top strip: art + info + controls ──
        top = tk.Frame(inner, bg=C["bg"])
        top.pack(fill="x", padx=0, pady=0)
        top.bind("<ButtonPress-1>",   _drag_start)
        top.bind("<B1-Motion>",       _drag_move)

        # Album art (54x54)
        self._mini_art_cv = tk.Canvas(top, bg=C["panel2"], width=54, height=54,
                                      highlightthickness=0)
        self._mini_art_cv.pack(side="left", padx=(8,0), pady=8)
        self._mini_art_photo = None
        self._mini_draw_art()

        # Info column
        info = tk.Frame(top, bg=C["bg"])
        info.pack(side="left", fill="both", expand=True, padx=10, pady=(10,4))
        info.bind("<ButtonPress-1>", _drag_start)
        info.bind("<B1-Motion>",     _drag_move)

        self._mini_title = tk.Label(info, text="— NO TRACK —",
            font=("Courier New", 9, "bold"), fg=C["white"], bg=C["bg"],
            anchor="w", cursor="hand2")
        self._mini_title.pack(fill="x")
        self._mini_title.bind("<Double-Button-1>", lambda e: self._toggle_mini_player())

        self._mini_artist = tk.Label(info, text="",
            font=("Courier New", 8), fg=C["white3"], bg=C["bg"], anchor="w")
        self._mini_artist.pack(fill="x")
        self._mini_artist.bind("<ButtonPress-1>", _drag_start)
        self._mini_artist.bind("<B1-Motion>",     _drag_move)

        # Time row
        trow = tk.Frame(info, bg=C["bg"])
        trow.pack(fill="x", pady=(2,0))
        self._mini_cur = tk.Label(trow, text="0:00", font=("Courier New",7),
                                  fg=C["white3"], bg=C["bg"])
        self._mini_cur.pack(side="left")
        self._mini_tot = tk.Label(trow, text="0:00", font=("Courier New",7),
                                  fg=C["white3"], bg=C["bg"])
        self._mini_tot.pack(side="right")

        # Controls column
        ctrl = tk.Frame(top, bg=C["bg"])
        ctrl.pack(side="right", padx=(0,8), pady=8)

        def _mbtn(text, cmd, sz=12):
            b = tk.Label(ctrl, text=text, font=("Courier New", sz),
                         fg=C["white3"], bg=C["bg"], cursor="hand2", padx=5)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>",    lambda e: b.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e: b.config(fg=C["white3"]))
            return b

        # Shuffle
        self._mini_shuf_btn = _mbtn("⇌", self._toggle_shuffle, sz=10)
        _mbtn("⏮", self._prev)
        self._mini_play_btn = _mbtn("▶", self._toggle_play, sz=14)
        _mbtn("⏭", self._next)
        # Repeat
        self._mini_rep_btn  = _mbtn("↺", self._toggle_repeat, sz=10)

        # Window controls (top-right)
        wctrl = tk.Frame(top, bg=C["bg"])
        wctrl.pack(side="right", anchor="n", pady=4)

        pin_b = tk.Label(wctrl, text="📌", font=("Courier New",8),
                         fg=C["white3"], bg=C["bg"], cursor="hand2")
        pin_b.pack()
        pin_b.bind("<Button-1>", lambda e: self._mini_toggle_topmost(pin_b))
        pin_b.bind("<Enter>",    lambda e: pin_b.config(fg=C["white"]))
        pin_b.bind("<Leave>",    lambda e: pin_b.config(fg=C["white3"]))

        close_b = tk.Label(wctrl, text="✕", font=("Courier New",8),
                           fg=C["white3"], bg=C["bg"], cursor="hand2")
        close_b.pack()
        close_b.bind("<Button-1>", lambda e: self._toggle_mini_player())
        close_b.bind("<Enter>",    lambda e: close_b.config(fg=C["white"]))
        close_b.bind("<Leave>",    lambda e: close_b.config(fg=C["white3"]))

        # ── seekable progress bar ──
        prog_frame = tk.Frame(inner, bg=C["bg"])
        prog_frame.pack(fill="x", padx=0, pady=0, side="bottom")

        self._mini_prog_cv = tk.Canvas(prog_frame, bg=C["border"], height=5,
                                       highlightthickness=0, cursor="hand2")
        self._mini_prog_cv.pack(fill="x")
        self._mini_prog_fill = self._mini_prog_cv.create_rectangle(
            0, 0, 0, 5, fill=C["white"], outline="")
        self._mini_prog_dot  = self._mini_prog_cv.create_oval(
            -4, -2, 4, 7, fill=C["glow"], outline="", state="hidden")

        def _prog_hover(entering):
            self._mini_prog_cv.itemconfig(
                self._mini_prog_dot, state="normal" if entering else "hidden")

        def _prog_seek(e):
            self._mini_seeking = True
            w = max(1, self._mini_prog_cv.winfo_width())
            r = max(0.0, min(1.0, e.x / w))
            if self._sp_mode:
                ms = int(r * self._sp_dur_ms)
                threading.Thread(target=lambda: self.sp_api.seek(ms), daemon=True).start()
            elif self.engine.duration > 0:
                self.engine.seek(r * self.engine.duration)
            self._mini_prog_r  = r
            self._mini_seeking = False

        def _prog_move(e):
            w = max(1, self._mini_prog_cv.winfo_width())
            r = max(0.0, min(1.0, e.x / w))
            # Drag dot preview
            x = r * w
            self._mini_prog_cv.coords(self._mini_prog_dot, x-4, -2, x+4, 7)

        self._mini_prog_cv.bind("<Enter>",          lambda e: _prog_hover(True))
        self._mini_prog_cv.bind("<Leave>",          lambda e: _prog_hover(False))
        self._mini_prog_cv.bind("<ButtonRelease-1>", _prog_seek)
        self._mini_prog_cv.bind("<B1-Motion>",       _prog_move)

        # ── volume scroll on whole window ──
        def _scroll_vol(e):
            delta = 0.04 if e.delta > 0 else -0.04
            self.engine.set_volume(self.engine.volume + delta)
        win.bind("<MouseWheel>", _scroll_vol)

        # ── keyboard shortcuts ──
        win.bind("<space>",      lambda e: self._toggle_play())
        win.bind("<Right>",      lambda e: self._next())
        win.bind("<Left>",       lambda e: self._prev())
        win.bind("<Escape>",     lambda e: self._toggle_mini_player())

        # ── right-click context menu ──
        def _ctx(e):
            menu = tk.Menu(win, bg=C["panel"], fg=C["white"],
                           activebackground=C["select2"], activeforeground=C["white"],
                           font=FM, tearoff=0, bd=0, relief="flat")
            menu.add_command(label="Expand player",
                             command=self._toggle_mini_player)
            menu.add_separator()
            menu.add_command(label="Add to queue",
                             command=lambda: self._add_current_to_queue())
            menu.add_separator()
            topmost_lbl = "✓ Always on top" if self._mini_topmost else "  Always on top"
            menu.add_command(label=topmost_lbl,
                             command=lambda: self._mini_toggle_topmost(pin_b))
            menu.tk_popup(e.x_root, e.y_root)
        win.bind("<Button-3>", _ctx)

        self._mini_update()
        self._mini_tick()

    def _mini_draw_art(self):
        """Draw album art or placeholder into the mini art canvas."""
        cv = self._mini_art_cv
        cv.delete("all")
        # Try to reuse main art photo
        if self._art_photo:
            try:
                cv.create_image(27, 27, image=self._art_photo, anchor="center")
                return
            except: pass
        # Placeholder — geometric pattern
        cv.create_rectangle(0, 0, 54, 54, fill=C["panel2"], outline="")
        for i in range(3):
            r = 8 + i * 7
            cv.create_oval(27-r, 27-r, 27+r, 27+r,
                           outline=C["border2"], fill="", width=1)
        cv.create_oval(24, 24, 30, 30, fill=C["white3"], outline="")

    def _mini_toggle_topmost(self, pin_btn=None):
        self._mini_topmost = not self._mini_topmost
        self._mini_win.wm_attributes("-topmost", self._mini_topmost)
        if pin_btn:
            pin_btn.config(fg=C["white"] if self._mini_topmost else C["white3"])

    def _add_current_to_queue(self):
        if self.current_idx >= 0:
            self.queue.append(self.current_idx)

    def _mini_update(self):
        if not self._mini_win or not self._mini_win.winfo_exists():
            return
        title  = self.now_title.cget("text")
        artist = self.now_artist.cget("text")
        self._mini_title.config(text=title[:38] if len(title) > 38 else title)
        self._mini_artist.config(text=artist[:42] if len(artist) > 42 else artist)
        playing = self.engine.is_playing or self._sp_playing
        self._mini_play_btn.config(text="⏸" if playing else "▶")
        # Shuffle / repeat state colors
        self._mini_shuf_btn.config(
            fg=C["white"] if self.shuffle else C["white3"])
        self._mini_rep_btn.config(
            fg=C["white"] if self.repeat_mode != "off" else C["white3"])
        # Album art sync
        self._mini_draw_art()

    def _mini_tick(self):
        if not self._mini_win or not self._mini_win.winfo_exists():
            return
        try:
            # Smooth progress
            if self._mini_seeking:
                r = self._mini_prog_r
            elif self._sp_mode and self._sp_dur_ms > 0:
                r = min(1.0, self._sp_pos_ms / self._sp_dur_ms)
                cur = self._sp_pos_ms / 1000
                tot = self._sp_dur_ms / 1000
            elif self.engine.duration > 0:
                pos = self.engine._pos_cache
                dur = self.engine.duration
                r   = min(1.0, pos / dur)
                cur = pos
                tot = dur
            else:
                r = 0.0; cur = 0; tot = 0

            # Lerp progress bar smoothly
            self._mini_prog_r += (r - self._mini_prog_r) * 0.18
            w = max(1, self._mini_prog_cv.winfo_width())
            px = self._mini_prog_r * w
            self._mini_prog_cv.coords(self._mini_prog_fill, 0, 0, px, 5)

            # Update time labels
            try:
                self._mini_cur.config(text=self._fmt(cur))
                self._mini_tot.config(text=self._fmt(tot))
            except: pass

        except: pass

        self._mini_update()
        self._mini_win.after(50, self._mini_tick)  # 20fps — smooth enough, light

    # ── HISTORY ───────────────────────────
    def _history_add(self, track, source="library"):
        entry = {
            "title":  track.get("title",""),
            "artist": track.get("artist",""),
            "album":  track.get("album",""),
            "source": source,
            "ts":     int(time.time()),
        }
        # Avoid duplicate consecutive entries (same title AND source)
        if self._history and self._history[-1].get("title") == entry["title"] and \
                self._history[-1].get("source","library") == entry.get("source","library"):
            return
        self._history.append(entry)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]
        self._save()
        if self.view == "history":
            self._refresh_history_view()

    def _build_history_view(self):
        self.history_frame = tk.Frame(self.content, bg=C["bg"])
        hdr = tk.Frame(self.history_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16,0))
        tk.Label(hdr, text="RECENTLY PLAYED", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(side="left")
        clr = tk.Label(hdr, text="[ CLEAR ]", font=FMS,
                       fg=C["white3"], bg=C["bg"], cursor="hand2")
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda e: self._clear_history())
        clr.bind("<Enter>",    lambda e: clr.config(fg=C["white"]))
        clr.bind("<Leave>",    lambda e: clr.config(fg=C["white3"]))

        # Source filter buttons
        flt = tk.Frame(self.history_frame, bg=C["bg"])
        flt.pack(fill="x", padx=20, pady=(6,0))
        tk.Label(flt, text="FILTER:", font=FMS, fg=C["white3"], bg=C["bg"]).pack(side="left")
        self._hist_filter = tk.StringVar(value="all")
        for _lbl, _key in [("ALL","all"),("LIBRARY","library"),("SPOTIFY","spotify"),
                           ("YOUTUBE","youtube"),("SOUNDCLOUD","soundcloud")]:
            _b = tk.Label(flt, text=_lbl, font=FMS, fg=C["white"] if _key=="all" else C["white3"],
                         bg=C["bg"], cursor="hand2", padx=8)
            _b.pack(side="left")
            def _on_click(e, k=_key, btn=_b, f=flt):
                self._hist_filter.set(k)
                for child in f.winfo_children()[1:]:
                    child.config(fg=C["white3"])
                btn.config(fg=C["white"])
                self._refresh_history_view()
            _b.bind("<Button-1>", _on_click)

        tk.Frame(self.history_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8,0))

        lf = tk.Frame(self.history_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=0, pady=0)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=6,
                          bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        self._hist_cv = tk.Canvas(lf, bg=C["bg"], highlightthickness=0,
                                  yscrollcommand=sb.set)
        self._hist_cv.pack(side="left", fill="both", expand=True)
        sb.config(command=self._hist_cv.yview)
        self._hist_inner = tk.Frame(self._hist_cv, bg=C["bg"])
        self._hist_cv.create_window(0, 0, anchor="nw", window=self._hist_inner)
        self._hist_inner.bind("<Configure>",
            lambda e: self._hist_cv.configure(scrollregion=self._hist_cv.bbox("all")))
        self._hist_cv.bind("<MouseWheel>", lambda e: self._hist_cv.yview_scroll(int(-1*(e.delta/120))*3, "units"))
        self._hist_inner.bind("<MouseWheel>", lambda e: self._hist_cv.yview_scroll(int(-1*(e.delta/120))*3, "units"))

    def _refresh_history_view(self):
        for w in self._hist_inner.winfo_children():
            w.destroy()
        filt = getattr(self, "_hist_filter", None)
        filt = filt.get() if filt else "all"
        entries = list(reversed(self._history))
        if filt != "all":
            entries = [e for e in entries if e.get("source","library") == filt]
        if not entries:
            tk.Label(self._hist_inner, text="No history yet — play some tracks.",
                     font=FM, fg=C["white3"], bg=C["bg"]).pack(padx=24, pady=20)
            return
        src_colors = {
            "library":    C["white3"],
            "spotify":    "#1db954",
            "youtube":    "#ff0000",
            "soundcloud": "#ff5500",
        }
        for i, e in enumerate(entries):
            bg  = C["select"] if i % 2 == 0 else C["bg"]
            row = tk.Frame(self._hist_inner, bg=bg, cursor="hand2")
            row.pack(fill="x")
            ts_str  = time.strftime("%d %b  %H:%M", time.localtime(e.get("ts",0)))
            src     = e.get("source","library")
            src_col = src_colors.get(src, C["white3"])
            tk.Label(row, text=ts_str, font=("Courier New",7),
                     fg=C["white3"], bg=bg, width=14, anchor="w").pack(side="left", padx=(14,0), pady=6)
            tk.Label(row, text=src.upper()[:2], font=("Courier New",7,"bold"),
                     fg=src_col, bg=bg, width=3, anchor="w").pack(side="left")
            tk.Label(row, text=e.get("title","")[:40], font=FM,
                     fg=C["white"], bg=bg, anchor="w").pack(side="left", padx=10)
            tk.Label(row, text=e.get("artist","")[:28], font=FMS,
                     fg=C["white3"], bg=bg, anchor="w").pack(side="left")
            for w in (row,) + row.winfo_children():
                w.bind("<Enter>",    lambda ev, r=row: r.config(bg=C["select2"]))
                w.bind("<Leave>",    lambda ev, r=row, b=bg: r.config(bg=b))

    def _clear_history(self):
        self._history = []
        self._refresh_history_view()
        self._save()

    # ── LAST.FM ───────────────────────────
    def _schedule_scrobble(self):
        if self._scrobble_job:
            self.root.after_cancel(self._scrobble_job)
        # Poll every 30s to check if we should scrobble
        def _check():
            if self._scrobbler:
                self._scrobbler.track_maybe_scrobble()
            self._scrobble_job = self.root.after(30000, _check)
        self._scrobble_job = self.root.after(30000, _check)

    def _open_lastfm_auth(self):
        """Open Last.fm auth flow in browser."""
        sk = self.settings.get("lastfm_session_key","")
        if sk:
            from tkinter import messagebox
            messagebox.showinfo("Last.fm",
                "Already connected.\nTo disconnect, clear the session key in Settings.",
                parent=self.root)
            return
        key = self.settings.get("lastfm_api_key","").strip()
        sec = self.settings.get("lastfm_api_secret","").strip()
        if not key or not sec:
            from tkinter import messagebox
            messagebox.showwarning("Last.fm",
                "Enter your API key and secret in Settings first.",
                parent=self.root)
            return
        scr = LastFmScrobbler(api_key=key, api_secret=sec)
        token = scr.get_token()
        if not token:
            from tkinter import messagebox
            messagebox.showerror("Last.fm", "Could not get token — check API key.",
                                 parent=self.root)
            return
        webbrowser.open(scr.get_auth_url(token))
        # Poll for session key
        def _poll_session(attempts=0):
            if attempts > 30:
                return
            sk2 = scr.get_session(token)
            if sk2:
                self.settings["lastfm_session_key"] = sk2
                self._scrobbler.session_key = sk2
                self._save()
                self._set_status("LASTFM OK")
            else:
                self.root.after(3000, lambda: _poll_session(attempts+1))
        self.root.after(3000, _poll_session)

    # ── DISCORD ───────────────────────────
    def _discord_connect(self):
        if not self.settings.get("discord_enabled", False):
            return
        ok = self._discord.connect()
        self._discord_enabled = ok

    # ── CROSSFADE ─────────────────────────
    def _start_crossfade(self, seconds, on_done):
        """Fade current track out over `seconds`, then call on_done."""
        if self._xfade_job:
            self.root.after_cancel(self._xfade_job)
        start_vol = self.engine.volume
        steps     = max(10, seconds * 20)   # 50ms per step
        step_vol  = start_vol / steps

        def _fade(n=0):
            if n >= steps:
                on_done()
                self.engine.set_volume(start_vol)
                return
            self.engine.set_volume(max(0.0, start_vol - step_vol * n))
            self._xfade_job = self.root.after(50, lambda: _fade(n+1))
        _fade()

    # ── FOLDER WATCHER ────────────────────
    def _on_watcher_new_file(self, path):
        """Called from watcher thread when a new audio file appears."""
        def _add():
            # Check not already in library
            existing = {t["path"] for t in self.library}
            if path not in existing:
                meta = self.engine.get_metadata(path)
                meta["path"] = path
                self.library.append(meta)
                self._save()
                self._refresh_tracks()
                self._set_status("NEW TRACK")
        self.root.after(0, _add)

    def _open_watch_dirs(self):
        dirs = self.settings.get("watch_dirs", [])
        win = tk.Toplevel(self.root)
        win.title("WATCH FOLDERS")
        win.configure(bg=C["bg"])
        win.geometry("460x320")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="AUTO-SCAN FOLDERS", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(pady=(18,4), padx=20, anchor="w")
        tk.Label(win, text="New audio files in these folders are added automatically.",
                 font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        lf = tk.Frame(win, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20)
        self._watch_listbox = tk.Listbox(lf, bg=C["panel"], fg=C["white"],
            font=FM, selectbackground=C["select2"], selectforeground=C["white"],
            bd=0, highlightthickness=1, highlightbackground=C["border"],
            activestyle="none")
        self._watch_listbox.pack(fill="both", expand=True)
        for d in dirs:
            self._watch_listbox.insert("end", d)

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(fill="x", padx=20, pady=10)
        def _add_dir():
            d = filedialog.askdirectory(parent=win)
            if d and d not in dirs:
                dirs.append(d)
                self._watch_listbox.insert("end", d)
                self.settings["watch_dirs"] = dirs
                self._watcher.watch(d)
                self._save()
        def _rem_dir():
            sel = self._watch_listbox.curselection()
            if sel:
                d = self._watch_listbox.get(sel[0])
                dirs.remove(d)
                self._watch_listbox.delete(sel[0])
                self.settings["watch_dirs"] = dirs
                self._save()
        for txt, cmd in [("+ Add Folder", _add_dir), ("− Remove", _rem_dir)]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=4)
            b.pack(side="left", padx=(0,6))
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

    # ── WAVEFORM SEEKBAR ──────────────────
    def _load_waveform(self, path):
        """Load audio waveform in background for the seekbar."""
        self._waveform_data = None
        def _worker():
            try:
                if not SCIPY_AVAILABLE: return
                import wave, struct
                # Only process WAV directly; skip MP3 to avoid blocking
                if not str(path).lower().endswith(".wav"): return
                with wave.open(str(path), "rb") as wf:
                    n_ch  = wf.getnchannels()
                    sw    = wf.getsampwidth()
                    rate  = wf.getframerate()
                    n     = wf.getnframes()
                    if n > rate * 600: return   # skip files > 10min
                    raw   = wf.readframes(n)
                pcm = _np.frombuffer(raw, dtype=_np.int16).astype(_np.float32)
                if n_ch == 2:
                    pcm = pcm.reshape(-1,2).mean(axis=1)
                # Downsample to 400 points
                buckets = 400
                size    = len(pcm) // buckets
                if size < 1: return
                peaks = [float(_np.abs(pcm[i*size:(i+1)*size]).max()) / 32768
                         for i in range(buckets)]
                self._waveform_data = peaks
                self.root.after(0, self._draw_waveform_seekbar)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _draw_waveform_seekbar(self):
        """Redraw the progress bar with waveform overlay."""
        if not getattr(self, "_waveform_data", None): return
        cv   = self.prog_cv
        peaks = self._waveform_data
        w    = cv.winfo_width()
        h    = cv.winfo_height() or 4
        if w < 10: return
        cv.delete("waveform")
        # Draw waveform behind the normal progress fill
        # Progress position
        r = self.engine._pos_cache / self.engine.duration if self.engine.duration > 0 else 0
        px = r * w
        for i, peak in enumerate(peaks):
            x   = i / len(peaks) * w
            bar = max(1, peak * h * 2.2)
            y0  = h/2 - bar/2
            y1  = h/2 + bar/2
            col = C["white"] if x <= px else C["border2"]
            cv.create_line(x, y0, x, y1, fill=col, width=1, tags="waveform")
        # Keep waveform behind the dot
        cv.tag_lower("waveform")

    # ── TAG EDITOR ────────────────────────
    def _open_tag_editor(self, lib_idx):
        if lib_idx < 0 or lib_idx >= len(self.library): return
        track = self.library[lib_idx]
        win = tk.Toplevel(self.root)
        win.title("EDIT TAGS")
        win.configure(bg=C["bg"])
        win.geometry("420x300")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="EDIT TAGS", font=FMX, fg=C["white"],
                 bg=C["bg"]).pack(pady=(18,4), padx=20, anchor="w")
        tk.Label(win, text=Path(track["path"]).name[:52], font=FMS,
                 fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8,12))

        fields = {}
        for label, key in [("Title","title"),("Artist","artist"),("Album","album")]:
            row = tk.Frame(win, bg=C["bg"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=f"{label:<8}", font=FM, fg=C["white3"],
                     bg=C["bg"], width=8, anchor="w").pack(side="left")
            var = tk.StringVar(value=track.get(key,""))
            e = tk.Entry(row, textvariable=var, font=FM, bg=C["panel"],
                         fg=C["white"], insertbackground=C["white"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=C["border"])
            e.pack(side="left", fill="x", expand=True, ipady=4)
            fields[key] = var

        def _save_tags():
            for key, var in fields.items():
                track[key] = var.get().strip()
                self.library[lib_idx][key] = track[key]
            # Write ID3 tags if mutagen available
            if MUTAGEN_AVAILABLE:
                try:
                    from mutagen.id3 import ID3, TIT2, TPE1, TALB, ID3NoHeaderError
                    try:    tags = ID3(track["path"])
                    except: tags = ID3()
                    tags[TIT2.__name__] = TIT2(encoding=3, text=track["title"])
                    tags[TPE1.__name__] = TPE1(encoding=3, text=track["artist"])
                    tags[TALB.__name__] = TALB(encoding=3, text=track["album"])
                    tags.save(track["path"])
                except Exception: pass
            self._save()
            self._refresh_tracks()
            win.destroy()

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(pady=16)
        for txt, cmd in [("[ SAVE ]", _save_tags), ("[ CANCEL ]", win.destroy)]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

    # ── SMART PLAYLISTS ───────────────────
    def _open_smart_playlist(self):
        win = tk.Toplevel(self.root)
        win.title("SMART PLAYLIST")
        win.configure(bg=C["bg"])
        win.geometry("460x380")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="SMART PLAYLIST", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(pady=(18,4), padx=20, anchor="w")
        tk.Label(win, text="Auto-fills based on rules applied to your library.",
                 font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8,12))

        # Name
        nf = tk.Frame(win, bg=C["bg"])
        nf.pack(fill="x", padx=20, pady=4)
        tk.Label(nf, text="Name    ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        name_var = tk.StringVar(value="Smart Mix")
        tk.Entry(nf, textvariable=name_var, font=FM, bg=C["panel"], fg=C["white"],
                 insertbackground=C["white"], relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=C["border"]
                 ).pack(side="left", fill="x", expand=True, ipady=4)

        # Rule
        rf = tk.Frame(win, bg=C["bg"])
        rf.pack(fill="x", padx=20, pady=8)
        tk.Label(rf, text="Rule    ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        field_var  = tk.StringVar(value="artist")
        op_var     = tk.StringVar(value="contains")
        val_var    = tk.StringVar()
        tk.OptionMenu(rf, field_var, "artist","title","album").pack(side="left")
        tk.OptionMenu(rf, op_var, "contains","starts with","ends with").pack(side="left", padx=4)
        tk.Entry(rf, textvariable=val_var, font=FM, bg=C["panel"], fg=C["white"],
                 insertbackground=C["white"], relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=C["border"], width=18
                 ).pack(side="left", ipady=4)

        # Limit
        lf2 = tk.Frame(win, bg=C["bg"])
        lf2.pack(fill="x", padx=20, pady=4)
        tk.Label(lf2, text="Limit   ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        limit_var = tk.IntVar(value=25)
        tk.Spinbox(lf2, from_=5, to=500, textvariable=limit_var,
                   font=FM, bg=C["panel"], fg=C["white"], width=6,
                   buttonbackground=C["border"], relief="flat").pack(side="left")
        tk.Label(lf2, text=" tracks", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")

        # Sort
        sf2 = tk.Frame(win, bg=C["bg"])
        sf2.pack(fill="x", padx=20, pady=4)
        tk.Label(sf2, text="Sort by ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        sort_var = tk.StringVar(value="title")
        tk.OptionMenu(sf2, sort_var, "title","artist","album","random").pack(side="left")

        def _create():
            name  = name_var.get().strip()
            field = field_var.get()
            op    = op_var.get()
            val   = val_var.get().strip().lower()
            limit = limit_var.get()
            sort  = sort_var.get()
            if not name or not val: return

            matches = []
            for i, t in enumerate(self.library):
                fv = t.get(field,"").lower()
                hit = (op == "contains"   and val in fv) or \
                      (op == "starts with" and fv.startswith(val)) or \
                      (op == "ends with"   and fv.endswith(val))
                if hit: matches.append(i)

            if sort == "random":
                random.shuffle(matches)
            elif sort in ("title","artist","album"):
                matches.sort(key=lambda i: self.library[i].get(sort,"").lower())

            matches = matches[:limit]
            self.playlists[name] = matches
            self._refresh_pl_sidebar()
            self._save()
            self._set_status(f"SMART: {len(matches)} TRACKS")
            win.destroy()

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(pady=16)
        for txt, cmd in [("[ CREATE ]", _create), ("[ CANCEL ]", win.destroy)]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

    # ── DUPLICATE DETECTOR ────────────────
    def _open_duplicate_detector(self):
        # Group by (title.lower, artist.lower)
        from collections import defaultdict
        groups = defaultdict(list)
        for i, t in enumerate(self.library):
            key = (t.get("title","").lower().strip(),
                   t.get("artist","").lower().strip())
            groups[key].append(i)
        dupes = {k: v for k, v in groups.items() if len(v) > 1}

        win = tk.Toplevel(self.root)
        win.title("DUPLICATE DETECTOR")
        win.configure(bg=C["bg"])
        win.geometry("560x400")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="DUPLICATE TRACKS", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(pady=(18,4), padx=20, anchor="w")
        count_txt = f"{len(dupes)} duplicate group(s) found" if dupes else "No duplicates found."
        tk.Label(win, text=count_txt, font=FMS, fg=C["white3"],
                 bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8,0))

        lf = tk.Frame(win, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=10, pady=8)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                          width=6, bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(lf, bg=C["bg"], fg=C["white"], font=FM,
                        selectbackground=C["select2"], bd=0,
                        highlightthickness=0, activestyle="none",
                        yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        to_remove = []
        for (title, artist), idxs in dupes.items():
            lb.insert("end", f"  {title[:36]}  —  {artist[:24]}")
            for i, idx in enumerate(idxs):
                p = Path(self.library[idx]["path"])
                label = f"    {'[KEEP] ' if i==0 else '[DUPE] '}{p.name[:50]}"
                lb.insert("end", label)
                if i > 0:
                    to_remove.append(idx)
            lb.insert("end", "")

        def _remove_dupes():
            keep = set(range(len(self.library))) - set(to_remove)
            self.library = [self.library[i] for i in sorted(keep)]
            self._save()
            self._refresh_tracks()
            win.destroy()
            self._set_status(f"REMOVED {len(to_remove)}")

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(pady=8)
        if to_remove:
            b = tk.Label(bf, text=f"[ REMOVE {len(to_remove)} DUPES ]",
                         font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e: _remove_dupes())
            b.bind("<Enter>",    lambda e: b.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e: b.config(fg=C["white3"]))
        tk.Label(bf, text="[ CLOSE ]", font=FM, fg=C["white3"], bg=C["panel"],
                 cursor="hand2", padx=10, pady=5
                 ).pack(side="left", padx=6
                 ).bind("<Button-1>", lambda e: win.destroy())

    # ── EXPORT PLAYLIST ───────────────────
    def _export_playlist_m3u(self, name=None):
        tracks = []
        if name and name in self.playlists:
            tracks = [self.library[i] for i in self.playlists[name]
                      if i < len(self.library)]
        elif self.active_playlist and self.active_playlist in self.playlists:
            tracks = [self.library[i] for i in self.playlists[self.active_playlist]
                      if i < len(self.library)]
        else:
            tracks = self.library

        out = filedialog.asksaveasfilename(
            defaultextension=".m3u",
            filetypes=[("M3U Playlist","*.m3u"),("All files","*")],
            initialfile=(name or "oternos_export") + ".m3u",
            parent=self.root)
        if not out: return
        try:
            lines = ["#EXTM3U"]
            for t in tracks:
                dur = int(t.get("duration",0))
                lines.append(f"#EXTINF:{dur},{t.get('artist','')} - {t.get('title','')}")
                lines.append(t["path"])
            Path(out).write_text("\n".join(lines), encoding="utf-8")
            self._set_status("EXPORTED")
        except Exception:
            self._set_status("EXPORT ERR")

    # ── NEW VISUALIZER MODES ──────────────
    def _viz_spectrum(self, cv, W, H, t, playing, bars):
        """Classic mirrored spectrum analyser."""
        cx, cy = W/2, H/2
        n   = len(bars)
        bw  = W / n
        for i, b in enumerate(bars):
            amp = b
            h2  = max(2, amp * H * 0.85)
            br  = min(255, int(60 + amp * 195))
            col = f"#{br:02x}{br:02x}{br:02x}"
            x   = i * bw
            # Mirrored top + bottom
            cv.create_rectangle(x+1, cy-h2/2, x+bw-1, cy+h2/2,
                                 fill=col, outline="")
        # Centre line
        cv.create_line(0, cy, W, cy, fill=C["border"], width=1)

    def _viz_oscilloscope(self, cv, W, H, t, playing, bars):
        """Smooth oscilloscope waveform drawn as a connected line."""
        cy = H / 2
        n  = len(bars)
        points = []
        for i, b in enumerate(bars):
            x = i / (n-1) * W
            # Alternate positive/negative for waveform feel
            sign = math.sin(i * 0.65 + t * 0.08)
            y    = cy + sign * b * cy * 0.85
            points.append(x)
            points.append(y)
        if len(points) >= 4:
            br  = min(255, int(80 + self._viz_glow * 175))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(points, fill=col, width=2, smooth=True)
        # Scan line
        scan_x = (t % (W or 1))
        cv.create_line(scan_x, 0, scan_x, H, fill=C["border"], width=1)

    def _viz_particles(self, cv, W, H, t, playing, bars):
        """Particles that explode outward on beat."""
        cx, cy = W/2, H/2
        energy = sum(bars[:8]) / 8
        # Update particle positions
        for p in self._viz_grid_particles:
            speed = 0.008 + energy * 0.025
            p[0] += p[2] * speed
            p[1] += p[3] * speed
            # Bounce off edges
            if p[0] < 0 or p[0] > 1: p[2] *= -1
            if p[1] < 0 or p[1] > 1: p[3] *= -1
            p[0] = max(0, min(1, p[0]))
            p[1] = max(0, min(1, p[1]))
        # Draw particles
        for i, p in enumerate(self._viz_grid_particles):
            x, y = p[0]*W, p[1]*H
            # Size pulses with beat
            sz  = 2 + energy * 6 + math.sin(t*0.04 + i*0.5) * 1.5
            br  = min(255, int(50 + energy * 200))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_oval(x-sz, y-sz, x+sz, y+sz, fill=col, outline="")
        # Connect nearby particles
        pts = self._viz_grid_particles
        thresh = 0.18
        for i in range(len(pts)):
            for j in range(i+1, len(pts)):
                dist = math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1])
                if dist < thresh:
                    alpha = int((1-dist/thresh) * 60)
                    col   = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
                    cv.create_line(pts[i][0]*W, pts[i][1]*H,
                                   pts[j][0]*W, pts[j][1]*H,
                                   fill=col, width=1)

    # ══════════════════════════════════════
    #  MIKU VIZ: TWIN TAILS
    #  Two massive swaying tail arcs + spectrum ring + floating notes
    # ══════════════════════════════════════
    def _viz_miku_tails(self, cv, W, H, t, playing, bars):
        cx    = W / 2
        bass  = sum(bars[:8]) / 8 if bars else 0
        energy= sum(bars) / len(bars) if bars else 0

        # ── Head centred at top-third ──
        hcy = H * 0.28
        hr  = min(W, H) * 0.058

        # ── Subtle spectrum bars at very bottom ──
        n   = len(bars)
        bw  = W / n
        bar_max = H * 0.08
        for i, h in enumerate(bars):
            bh  = max(1, h * bar_max)
            x   = i * bw
            if (i / n) < 0.5:
                v = int(8 + h * 55)
                col = f"#{v//6:02x}{min(255,v+40):02x}{min(255,v+36):02x}"
            else:
                v = int(7 + h * 50)
                col = f"#{min(255,v+55):02x}{v//6:02x}{min(255,v+44):02x}"
            cv.create_rectangle(x, H*0.92 - bh, x + bw - 1, H*0.92,
                                fill=col, outline="")

        # ── Twin tails using explicit bezier interpolation ──
        # Control points are defined in canvas coordinates so we can
        # see exactly what shape they make:
        #   P0 = bun (start, beside head)
        #   P1 = control 1 (pull slightly OUT and a bit down)
        #   P2 = control 2 (pull far DOWN and slightly back in)
        #   P3 = tip (end, hanging low)
        # This guarantees the tail goes DOWN with a gentle outward lean.

        sway_l = math.sin(t * 0.026) * (W * 0.018 + bass * W * 0.025)
        sway_r = math.sin(t * 0.021 + 1.1) * (W * 0.016 + bass * W * 0.022)

        bun_x_off = hr * 0.70   # buns sit left/right of head centre
        bun_y     = hcy - hr * 0.4

        def _bezier4(p0, p1, p2, p3, segs=48):
            """Cubic bezier curve through 4 control points."""
            pts = []
            for i in range(segs):
                t2 = i / (segs - 1)
                mt = 1 - t2
                x = (mt**3*p0[0] + 3*mt**2*t2*p1[0] +
                     3*mt*t2**2*p2[0] + t2**3*p3[0])
                y = (mt**3*p0[1] + 3*mt**2*t2*p1[1] +
                     3*mt*t2**2*p2[1] + t2**3*p3[1])
                pts.extend([x, y])
            return pts

        def _draw_tail(bun_x, sign, sway, c_dark, c_bright):
            # P0: bun position
            p0 = (bun_x, bun_y)
            # P1: pull outward a little, barely down yet
            p1 = (bun_x + sign * W * 0.10 + sway * 0.3,
                  bun_y + H * 0.08)
            # P2: now mostly down, still leaning out slightly
            p2 = (bun_x + sign * W * 0.14 + sway * 0.7,
                  bun_y + H * 0.40)
            # P3: tip — hanging at ~75% of canvas height
            p3 = (bun_x + sign * W * 0.08 + sway,
                  bun_y + H * 0.58)

            pts = _bezier4(p0, p1, p2, p3)
            if len(pts) >= 4:
                cv.create_line(pts, fill=c_dark,   width=8, smooth=True, capstyle="round")
                cv.create_line(pts, fill=c_bright, width=3, smooth=True, capstyle="round")

        _draw_tail(cx - bun_x_off, -1, sway_l, "#093830", "#39c5bb")
        _draw_tail(cx + bun_x_off, +1, sway_r, "#093830", "#4dd8d0")

        # ── Head drawn on top of tail bases ──
        hv = int(70 + bass * 110)
        cv.create_oval(cx - hr, hcy - hr, cx + hr, hcy + hr,
                       fill=C["bg"],
                       outline=f"#{hv//6:02x}{min(255,hv):02x}{min(255,hv-3):02x}",
                       width=2)

        # ── ♪ inside head ──
        nv = int(90 + bass * 140)
        cv.create_text(cx, hcy, text="♪",
                       font=("Consolas", max(8, int(hr * 0.95))),
                       fill=f"#{nv//6:02x}{min(255,nv):02x}{min(255,nv-3):02x}",
                       anchor="center")

        # ── Bun circles ──
        br2 = hr * 0.32
        for bx in (cx - bun_x_off, cx + bun_x_off):
            cv.create_oval(bx - br2, bun_y - br2,
                           bx + br2, bun_y + br2,
                           fill=C["bg"],
                           outline=f"#{hv//6:02x}{min(255,hv):02x}{min(255,hv-3):02x}",
                           width=1)

        # ── Floating ♪ notes ──
        if not hasattr(self, "_mt_notes"):
            self._mt_notes = []
        if bass > 0.38 and t % max(1, int(16 - bass * 10)) == 0:
            import random as _r
            self._mt_notes.append({
                "x": cx + _r.uniform(-W * 0.40, W * 0.40),
                "y": H * 0.80,
                "vy": _r.uniform(1.0, 2.2) + bass * 1.0,
                "age": 0,
                "sym": _r.choice(["♪", "♫", "♬", "✦"]),
                "pink": _r.random() > 0.5,
            })
        dead = []
        for n_ in self._mt_notes:
            n_["y"]  -= n_["vy"]
            n_["age"] += 1
            life = n_["age"] / 60
            if life > 1 or n_["y"] < 0:
                dead.append(n_); continue
            alpha = int((1 - life) * 200)
            if n_["pink"]:
                nc = f"#{min(255,alpha+55):02x}{alpha//5:02x}{min(255,alpha+44):02x}"
            else:
                nc = f"#{alpha//6:02x}{min(255,alpha+28):02x}{min(255,alpha+22):02x}"
            cv.create_text(n_["x"], n_["y"], text=n_["sym"],
                           font=("Consolas", max(8, int(11 - life * 3))),
                           fill=nc, anchor="center")
        for d in dead:
            self._mt_notes.remove(d)

    # ══════════════════════════════════════
    #  MIKU VIZ: SAKURA
    #  Cherry blossom storm + soft wave + name glow
    # ══════════════════════════════════════
    def _viz_miku_sakura(self, cv, W, H, t, playing, bars):
        bass   = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0

        # Soft gradient backdrop — horizontal teal-to-dark strips
        strips = 8
        for i in range(strips):
            y1 = H * i / strips
            y2 = H * (i+1) / strips
            frac = i / (strips-1)
            gv = int(4 + frac * 12 + bass * 10)
            cv.create_rectangle(0, y1, W, y2,
                fill=f"#{gv:02x}{min(255,gv*4):02x}{min(255,gv*4-2):02x}", outline="")

        # Gentle sine wave across centre
        pts = []
        steps = 80
        amp   = H * (0.06 + energy * 0.12)
        for i in range(steps + 1):
            x = W * i / steps
            y = H/2 + amp * math.sin(t*0.035 + x * 0.018)
            pts.extend([x, y])
        if len(pts) >= 4:
            wv = int(20 + energy * 50)
            cv.create_line(pts, fill=f"#{wv//4:02x}{min(255,wv+20):02x}{min(255,wv+15):02x}",
                           width=2, smooth=True)

        # Petal shower
        if not hasattr(self, "_sk_petals"):
            import random as _r
            self._sk_petals = [
                {"x": _r.uniform(0,W), "y": _r.uniform(-H, H),
                 "vx": _r.uniform(-0.6,0.6), "vy": _r.uniform(0.5,1.8),
                 "a": _r.uniform(0,math.pi*2), "va": _r.uniform(-0.05,0.05),
                 "sz": _r.uniform(3,8), "pink": _r.random()>0.4}
                for _ in range(30 + int(energy * 20))
            ]
        for p in self._sk_petals:
            p["x"] += p["vx"] + math.sin(t*0.018)*0.5 + bass*0.4
            p["y"] += p["vy"] + bass * 0.6
            p["a"] += p["va"]
            if p["y"] > H + 12:
                import random as _r
                p["x"] = _r.uniform(0, W); p["y"] = -10
            pts = []
            for i in range(4):
                a2 = p["a"] + i * math.pi/2
                pts += [p["x"] + p["sz"]*math.cos(a2),
                        p["y"] + p["sz"]*0.55*math.sin(a2)]
            pv = int(18 + energy * 55)
            if p["pink"]:
                col = f"#{min(255,pv+90):02x}{pv//3:02x}{min(255,pv+75):02x}"
            else:
                col = f"#{pv//4:02x}{min(255,pv+45):02x}{min(255,pv+40):02x}"
            cv.create_polygon(pts, fill=col, outline="")

        # "初音ミク" glow text
        tv = int(40 + bass * 120)
        cv.create_text(W/2, H*0.22, text="初音ミク",
                       font=("Yu Gothic UI", max(14, int(min(W,H)*0.055)))
                             if self._font_exists("Yu Gothic UI")
                             else ("Consolas", max(12, int(min(W,H)*0.048))),
                       fill=f"#{tv//5:02x}{min(255,tv+20):02x}{min(255,tv+15):02x}",
                       anchor="center")
        cv.create_text(W/2, H*0.78, text="HATSUNE MIKU",
                       font=("Consolas", max(8, int(min(W,H)*0.028))),
                       fill=f"#{tv//8:02x}{min(255,tv//2):02x}{min(255,tv//2-3):02x}",
                       anchor="center")

    # ══════════════════════════════════════
    #  MIKU VIZ: STARFALL
    #  Falling ✦ stars + twin-tail silhouette + beat flash
    # ══════════════════════════════════════
    def _viz_miku_starfall(self, cv, W, H, t, playing, bars):
        bass   = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        cx, cy = W/2, H/2

        # Beat flash background
        if bass > 0.6:
            fv = int(bass * 18)
            cv.create_rectangle(0, 0, W, H,
                fill=f"#{fv//4:02x}{min(255,fv*3):02x}{min(255,fv*3-3):02x}")

        # Falling stars
        if not hasattr(self, "_sf_stars"):
            import random as _r
            self._sf_stars = [
                {"x": _r.uniform(0,W), "y": _r.uniform(-H, H),
                 "vy": _r.uniform(1.0, 3.5), "sym": _r.choice(["✦","✧","★","♪","✦"]),
                 "sz": _r.randint(7,14), "pink": _r.random()>0.5,
                 "twinkle_phase": _r.uniform(0,math.pi*2)}
                for _ in range(40)
            ]
        for s in self._sf_stars:
            s["y"] += s["vy"] * (1 + bass * 1.8)
            if s["y"] > H + 20:
                import random as _r
                s["x"] = _r.uniform(0, W); s["y"] = -15
                s["sym"] = _r.choice(["✦","✧","★","♪","✦"])
            twinkle = (math.sin(t * 0.08 + s["twinkle_phase"]) * 0.5 + 0.5)
            sv = int(18 + twinkle * 80 + bass * 60)
            if s["pink"]:
                col = f"#{min(255,sv+80):02x}{sv//3:02x}{min(255,sv+65):02x}"
            else:
                col = f"#{sv//4:02x}{min(255,sv+30):02x}{min(255,sv+25):02x}"
            cv.create_text(s["x"], s["y"], text=s["sym"],
                           font=("Consolas", s["sz"]), fill=col, anchor="center")

        # Miku silhouette twin tails (simple outline, faint)
        sway = math.sin(t * 0.028) * (0.15 + bass * 0.22)
        tl = min(W, H) * 0.38

        def _outline_tail(bx, by, sign, sw, col):
            pts = []
            for i in range(30):
                frac = i / 29
                a = math.pi * (0.55 + sign * 0.78 * frac**0.7) + sw * frac**0.7
                r = tl * frac
                pts.extend([bx + r*math.cos(a)*sign, by + r*math.sin(a)*1.1])
            if len(pts) >= 4:
                cv.create_line(pts, fill=col, width=2, smooth=True, capstyle="round")

        ov = int(16 + bass * 40)
        tc = f"#{ov//4:02x}{min(255,ov+20):02x}{min(255,ov+16):02x}"
        _outline_tail(cx-W*0.06, cy-H*0.05, -1, sway,  tc)
        _outline_tail(cx+W*0.06, cy-H*0.05, +1, -sway, tc)

        # ── Centre ♪ pulse dot ──
        cr  = 5 + bass * 14
        cpv = int(45 + bass * 145)
        cv.create_oval(cx - cr, H*0.25 - cr, cx + cr, H*0.25 + cr,
                       fill=f"#{cpv//5:02x}{min(255,cpv):02x}{min(255,cpv-4):02x}",
                       outline="")

    # ══════════════════════════════════════
    #  MIKU VIZ: RIBBON
    #  Flowing teal/pink ribbons that dance with the music
    # ══════════════════════════════════════
    def _viz_miku_ribbon(self, cv, W, H, t, playing, bars):
        bass   = sum(bars[:8]) / 8 if bars else 0
        mid    = sum(bars[8:24]) / 16 if len(bars) >= 24 else 0
        treble = sum(bars[32:]) / 16 if len(bars) >= 48 else 0
        energy = (bass + mid + treble) / 3

        # Multiple ribbon paths weaving across the screen
        ribbon_defs = [
            # (y_centre_frac, speed, amp_frac, freq, color_mode, width)
            (0.35, 0.028, 0.18, 0.016, "teal",  4),
            (0.50, 0.022, 0.22, 0.012, "pink",  4),
            (0.65, 0.032, 0.16, 0.020, "teal",  3),
            (0.42, 0.018, 0.12, 0.009, "dim",   2),
            (0.58, 0.024, 0.14, 0.011, "dim",   2),
        ]
        for yf, spd, ampf, freq, mode, lw in ribbon_defs:
            cy_r = H * yf
            amp  = H * (ampf + energy * ampf * 1.5)
            pts  = []
            steps = 100
            for i in range(steps + 1):
                x = W * i / steps
                phase = t * spd + x * freq
                y = cy_r + amp * math.sin(phase) + (bass * H * 0.06 * math.sin(phase*2))
                pts.extend([x, y])
            if len(pts) < 4: continue
            # color
            frac = (math.sin(t * spd * 2) * 0.5 + 0.5)
            if mode == "teal":
                v = int(20 + frac * 60 + energy * 80)
                col = f"#{v//5:02x}{min(255,v+25):02x}{min(255,v+20):02x}"
            elif mode == "pink":
                v = int(15 + frac * 55 + energy * 70)
                col = f"#{min(255,v+75):02x}{v//4:02x}{min(255,v+60):02x}"
            else:
                v = int(10 + frac * 25)
                col = f"#{v//4:02x}{min(255,v+15):02x}{min(255,v+12):02x}"
            cv.create_line(pts, fill=col, width=lw, smooth=True)

        # Sparkle dots on ribbon peaks
        if t % 3 == 0:
            import random as _r
            for _ in range(int(2 + energy * 5)):
                sx = _r.uniform(0, W)
                sy = H/2 + _r.uniform(-H*0.25, H*0.25)
                sr = _r.uniform(1.5, 3.5 + energy * 3)
                sv = int(30 + energy * 120)
                if _r.random() > 0.5:
                    sc = f"#{min(255,sv+60):02x}{sv//4:02x}{min(255,sv+48):02x}"
                else:
                    sc = f"#{sv//5:02x}{min(255,sv+22):02x}{min(255,sv+18):02x}"
                cv.create_oval(sx-sr, sy-sr, sx+sr, sy+sr, fill=sc, outline="")

        # "VOCALOID" label at bottom
        lv = int(14 + energy * 35)
        cv.create_text(W/2, H*0.90,
                       text="V O C A L O I D",
                       font=("Consolas", max(8, int(min(W,H)*0.022))),
                       fill=f"#{lv//5:02x}{min(255,lv+12):02x}{min(255,lv+10):02x}",
                       anchor="center")

    # ══════════════════════════════════════
    #  MIKU VIZ: WAVEFORM
    #  Twin mirrored waveforms + teal/pink fill + beat pulse ring
    # ══════════════════════════════════════
    def _viz_miku_wave(self, cv, W, H, t, playing, bars):
        bass   = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        cx, cy = W/2, H/2

        # Centre line
        lv = int(8 + energy * 20)
        cv.create_line(0, cy, W, cy,
                       fill=f"#{lv//4:02x}{min(255,lv*3):02x}{min(255,lv*3-2):02x}", width=1)

        # Upper waveform (teal) — bars mapped to wave shape
        n = len(bars)
        upper = []
        lower = []
        for i in range(n):
            x = W * i / (n - 1)
            h = bars[i] * H * 0.40
            upper.extend([x, cy - h])
            lower.extend([x, cy + h])

        # Fill between centre and upper
        if len(upper) >= 4:
            fill_pts_top = [0, cy] + upper + [W, cy]
            tv = int(12 + energy * 45)
            cv.create_polygon(fill_pts_top,
                fill=f"#{tv//5:02x}{min(255,tv+20):02x}{min(255,tv+16):02x}",
                outline="")
            cv.create_line(upper, fill="#39c5bb", width=2, smooth=True)

        # Fill between centre and lower (pink)
        if len(lower) >= 4:
            fill_pts_bot = [0, cy] + lower + [W, cy]
            pv = int(10 + energy * 40)
            cv.create_polygon(fill_pts_bot,
                fill=f"#{min(255,pv+50):02x}{pv//4:02x}{min(255,pv+40):02x}",
                outline="")
            cv.create_line(lower, fill="#ff6eb4", width=2, smooth=True)

        # Beat pulse ring at centre
        pr = min(W, H) * (0.05 + bass * 0.18)
        pv = int(40 + bass * 160)
        cv.create_oval(cx-pr, cy-pr, cx+pr, cy+pr,
                       outline=f"#{pv//5:02x}{min(255,pv+15):02x}{min(255,pv+10):02x}",
                       fill="", width=2)
        if bass > 0.3:
            pr2 = pr * 1.6
            pv2 = int(pv * 0.4)
            cv.create_oval(cx-pr2, cy-pr2, cx+pr2, cy+pr2,
                           outline=f"#{min(255,pv2+30):02x}{pv2//4:02x}{min(255,pv2+24):02x}",
                           fill="", width=1)

        # Scrolling note strip at top
        note_syms = "♪ ♫ ✦ ♩ ♬ ✧ ♪ ♫ ✦"
        nv = int(12 + energy * 30)
        cv.create_text(((W//2 + t*2) % (W+100)) - 50, H*0.06,
                       text=note_syms,
                       font=("Consolas", max(7, int(min(W,H)*0.022))),
                       fill=f"#{nv//5:02x}{min(255,nv+15):02x}{min(255,nv+12):02x}",
                       anchor="center")

    # ── HOTKEY CUSTOMISER ─────────────────
    def _open_hotkey_editor(self):
        win = tk.Toplevel(self.root)
        win.title("HOTKEYS")
        win.configure(bg=C["bg"])
        win.geometry("400x320")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="HOTKEY CUSTOMISER", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(pady=(18,4), padx=20, anchor="w")
        tk.Label(win, text="Press a key combo to assign. Global media keys always active.",
                 font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8,12))

        actions = [
            ("Play / Pause",  "play_pause"),
            ("Next track",    "next"),
            ("Previous",      "prev"),
            ("Volume up",     "vol_up"),
            ("Volume down",   "vol_down"),
        ]
        hk = self.settings.get("hotkeys", {})
        vars_ = {}
        for label, key in actions:
            row = tk.Frame(win, bg=C["bg"])
            row.pack(fill="x", padx=20, pady=3)
            tk.Label(row, text=f"{label:<18}", font=FM, fg=C["white3"],
                     bg=C["bg"], width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value=hk.get(key, ""))
            e = tk.Entry(row, textvariable=var, font=FM, bg=C["panel"],
                         fg=C["white"], insertbackground=C["white"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=C["border"], width=16)
            e.pack(side="left", ipady=4)
            vars_[key] = var
            def _capture(event, v=var):
                parts = []
                if event.state & 0x4:  parts.append("Ctrl")
                if event.state & 0x1:  parts.append("Shift")
                if event.state & 0x8:  parts.append("Alt")
                parts.append(event.keysym)
                v.set("+".join(parts))
                return "break"
            e.bind("<KeyPress>", _capture)

        def _save_hk():
            for key, var in vars_.items():
                hk[key] = var.get()
            self.settings["hotkeys"] = hk
            self._save()
            win.destroy()

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(pady=14)
        for txt, cmd in [("[ SAVE ]", _save_hk), ("[ CANCEL ]", win.destroy)]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

    def _discord_connect(self):
        if not self.settings.get("discord_enabled", False):
            return
        ok = self._discord.connect()
        self._discord_enabled = ok

    # ══════════════════════════════════════
    #  SPECTRUM ANALYZER (player bar strip)
    # ══════════════════════════════════════
    def _spec_tick(self):
        """Update the RMS norm meter from FFT data."""
        try:
            playing = self.engine.is_playing or self._sp_playing
            fft = getattr(self, "_fft_bars", None)
            if fft and playing:
                rms  = min(1.0, sum(fft[:32]) / 32 * 3.5)
                peak = min(1.0, max(fft[:32]) * 2.8)
                self._norm_meter.update(rms, peak)
            else:
                self._norm_meter.update(0, None)
        except Exception:
            pass
        self.root.after(80 if HW_ACCEL else 500, self._spec_tick)

    # ══════════════════════════════════════
    #  PLAYBACK SPEED
    # ══════════════════════════════════════
    SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    def _cycle_speed(self):
        steps = self.SPEED_STEPS
        idx   = steps.index(self._playback_speed) if self._playback_speed in steps else 2
        self._playback_speed = steps[(idx + 1) % len(steps)]
        self._speed_lbl.config(text=f"{self._playback_speed}×")
        # MCI doesn't support speed natively; we expose the value for
        # future ffmpeg-based engine. For now, display only + warn.
        if self._playback_speed != 1.0:
            self._set_status(f"SPEED {self._playback_speed}×")
        else:
            self._set_status("SPEED NORMAL")

    # ══════════════════════════════════════
    #  A-B LOOP
    # ══════════════════════════════════════
    def _ab_set_a(self):
        pos = self.engine._pos_cache if not self._sp_mode else self._sp_pos_ms / 1000
        self._ab_a = pos
        self._ab_active = bool(self._ab_a is not None and self._ab_b is not None)
        self._ab_lbl.config(text=f"{self._fmt(self._ab_a)}–?")
        self._set_status(f"A: {self._fmt(self._ab_a)}")

    def _ab_set_b(self):
        pos = self.engine._pos_cache if not self._sp_mode else self._sp_pos_ms / 1000
        if self._ab_a is not None and pos > self._ab_a:
            self._ab_b = pos
            self._ab_active = True
            self._ab_lbl.config(
                text=f"{self._fmt(self._ab_a)}–{self._fmt(self._ab_b)}")
            self._set_status(f"A-B LOOP ON")
        else:
            self._set_status("SET A FIRST")

    def _ab_clear(self):
        self._ab_a = self._ab_b = None
        self._ab_active = False
        self._ab_lbl.config(text="—")
        self._set_status("A-B CLEAR")

    def _ab_check(self):
        """Called from _poll. Loops back to A when position passes B."""
        if not self._ab_active or self._ab_b is None:
            return
        if self._sp_mode:
            pos = self._sp_pos_ms / 1000
        else:
            pos = self.engine._pos_cache
        if pos >= self._ab_b:
            if self._sp_mode:
                ms = int(self._ab_a * 1000)
                threading.Thread(target=lambda: self.sp_api.seek(ms), daemon=True).start()
            else:
                self.engine.seek(self._ab_a)

    # ══════════════════════════════════════
    #  BOOKMARKS
    # ══════════════════════════════════════
    def _add_bookmark(self):
        if self.current_idx < 0:
            return
        pos = self.engine._pos_cache if not self._sp_mode else self._sp_pos_ms / 1000
        label = self._fmt(pos)
        bk = self._bookmarks.setdefault(self.current_idx, [])
        bk.append((pos, label))
        self._save()
        self._set_status(f"BKM @ {label}")

    def _open_bookmarks(self):
        idx = self.current_idx
        bk  = self._bookmarks.get(idx, [])
        win = tk.Toplevel(self.root)
        win.title("BOOKMARKS")
        win.configure(bg=C["bg"])
        win.geometry("340x300")
        win.transient(self.root)
        win.grab_set()

        title = self.library[idx]["title"] if 0 <= idx < len(self.library) else "—"
        tk.Label(win, text="BOOKMARKS", font=FMX, fg=C["white"],
                 bg=C["bg"]).pack(pady=(16,2), padx=20, anchor="w")
        tk.Label(win, text=title[:40], font=FMS, fg=C["white3"],
                 bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        lf = tk.Frame(win, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=16)
        if not bk:
            tk.Label(lf, text="No bookmarks for this track.",
                     font=FM, fg=C["white3"], bg=C["bg"]).pack(pady=12)
        else:
            for i, (sec, lbl) in enumerate(bk):
                row = tk.Frame(lf, bg=C["bg"], cursor="hand2")
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"⊹ {lbl}", font=FM, fg=C["white"],
                         bg=C["bg"], anchor="w").pack(side="left", padx=6)
                def _seek_bk(s=sec):
                    self.engine.seek(s)
                    win.destroy()
                def _del_bk(ii=i):
                    self._bookmarks[idx].pop(ii)
                    self._save()
                    win.destroy()
                    self._open_bookmarks()
                go = tk.Label(row, text="[ GO ]", font=FMS, fg=C["white3"],
                              bg=C["bg"], cursor="hand2")
                go.pack(side="right", padx=4)
                go.bind("<Button-1>", lambda e, f=_seek_bk: f())
                dl = tk.Label(row, text="[ × ]", font=FMS, fg=C["white3"],
                              bg=C["bg"], cursor="hand2")
                dl.pack(side="right", padx=2)
                dl.bind("<Button-1>", lambda e, f=_del_bk: f())

        tk.Label(win, text="[ CLOSE ]", font=FM, fg=C["white3"], bg=C["panel"],
                 cursor="hand2", padx=10, pady=5
                 ).pack(pady=10).bind("<Button-1>", lambda e: win.destroy())

    # ══════════════════════════════════════
    #  GAPLESS PLAYBACK
    # ══════════════════════════════════════
    def _gapless_preload(self):
        """Start pre-loading the next track 5s before end."""
        if self._sp_mode or not self.queue:
            return
        next_pos = self.queue_pos + 1
        if self.repeat_mode == "all" and next_pos >= len(self.queue):
            next_pos = 0
        if next_pos < 0 or next_pos >= len(self.queue):
            return
        lib_idx = self.queue[next_pos]
        if lib_idx >= len(self.library):
            return
        path = self.library[lib_idx]["path"]
        # Pre-open the file in a background thread so it's cached by OS
        def _preload():
            try:
                with open(path, "rb") as f:
                    f.read(65536)   # read first 64KB to warm FS cache
            except Exception:
                pass
        threading.Thread(target=_preload, daemon=True).start()

    # ══════════════════════════════════════
    #  TRACK RECOMMENDATIONS
    # ══════════════════════════════════════
    def _open_recommendations(self):
        rec = TrackRecommender(self.library, self._history)
        idxs = rec.recommend(30)

        win = tk.Toplevel(self.root)
        win.title("RECOMMENDATIONS")
        win.configure(bg=C["bg"])
        win.geometry("500x440")
        win.transient(self.root)

        tk.Label(win, text="RECOMMENDED FOR YOU", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(pady=(18,4), padx=20, anchor="w")
        tk.Label(win, text="Based on your listening history",
                 font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8,0))

        lf = tk.Frame(win, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=0, pady=6)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                          width=6, bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(lf, bg=C["bg"], fg=C["white"], font=FM,
                        selectbackground=C["select2"], bd=0,
                        highlightthickness=0, activestyle="none",
                        yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        for i in idxs:
            t = self.library[i]
            lb.insert("end", f"  {t.get('title','')[:36]:<38} {t.get('artist','')[:24]}")

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(pady=10)

        def _play_all():
            if idxs:
                self.queue     = list(idxs)
                self.queue_pos = 0
                self._play_item(0)
                win.destroy()

        def _play_sel():
            sel = lb.curselection()
            if sel:
                i = idxs[sel[0]]
                self.queue     = [i]
                self.queue_pos = 0
                self._play_item(0)
                win.destroy()

        def _add_all():
            self.queue.extend(idxs)
            self._set_status(f"+{len(idxs)} QUEUED")
            win.destroy()

        for txt, cmd in [("[ PLAY ALL ]", _play_all),
                         ("[ PLAY SEL ]", _play_sel),
                         ("[ ADD TO QUEUE ]", _add_all)]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"],
                         bg=C["panel"], cursor="hand2", padx=8, pady=5)
            b.pack(side="left", padx=4)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

    # ══════════════════════════════════════
    #  THEME / COLOR EDITOR
    # ══════════════════════════════════════
    def _open_theme_editor(self):
        win = tk.Toplevel(self.root)
        win.title("OTERNOS // THEMES")
        win.configure(bg=C["bg"])
        win.geometry("620x680")
        win.resizable(True, True)
        win.minsize(500, 500)
        win.transient(self.root)

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=C["panel"], height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border2"], height=1).pack(side="bottom", fill="x")
        tk.Label(hdr, text="◈ THEME STUDIO", font=FML,
                 fg=C["white"], bg=C["panel"]).pack(side="left", padx=18, pady=10)
        cl = tk.Label(hdr, text="[X]", font=("Courier New",11), fg=C["white3"],
                      bg=C["panel"], cursor="hand2", padx=14)
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda e: win.destroy())
        cl.bind("<Enter>", lambda e: cl.config(fg=C["white"]))
        cl.bind("<Leave>", lambda e: cl.config(fg=C["white3"]))

        # ── Tab bar ───────────────────────────────────────────────
        tab_bar = tk.Frame(win, bg=C["panel"])
        tab_bar.pack(fill="x")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x")
        _tab_btns = {}
        _tab_frames = {}
        _active_tab = tk.StringVar(value="presets")

        body_host = tk.Frame(win, bg=C["bg"])
        body_host.pack(fill="both", expand=True)

        def _switch_tab(name):
            _active_tab.set(name)
            for k, f in _tab_frames.items():
                f.pack_forget()
            _tab_frames[name].pack(fill="both", expand=True)
            for k, b in _tab_btns.items():
                b.config(fg=C["white"] if k==name else C["white3"],
                         bg=C["panel"])

        def _make_tab(key, label):
            b = tk.Label(tab_bar, text=label, font=("Courier New",7,"bold"),
                         fg=C["white3"], bg=C["panel"], cursor="hand2",
                         padx=14, pady=9)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: _switch_tab(k))
            b.bind("<Enter>",    lambda e, w=b, k=key: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b, k=key: w.config(
                fg=C["white"] if _active_tab.get()==k else C["white3"]))
            _tab_btns[key] = b
            f = tk.Frame(body_host, bg=C["bg"])
            _tab_frames[key] = f
            return f

        # ══════════════════════════════════════════════════════════
        #  TAB 1 — PRESETS
        # ══════════════════════════════════════════════════════════
        pf = _make_tab("presets", "PRESETS")

        tk.Label(pf, text="SELECT A PRESET THEME", font=("Courier New",7),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", padx=20, pady=(16,8))
        tk.Frame(pf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0,12))

        grid = tk.Frame(pf, bg=C["bg"])
        grid.pack(padx=20, fill="x")

        def _do_apply_preset(c, n):
            C.update(c)
            C["panel2"]  = C["panel"]
            self.settings["active_theme"] = n
            self._rebuild_ui_colors()
            self._save()
            self._toast(f"Theme: {n}")

        col = 0
        row_f = None
        for name, colors in self._theme_presets.items():
            if col % 4 == 0:
                row_f = tk.Frame(grid, bg=C["bg"])
                row_f.pack(fill="x", pady=4)
            col += 1
            card = tk.Frame(row_f, bg=colors["bg"], width=120, height=80,
                            cursor="hand2", highlightthickness=1,
                            highlightbackground=colors["border2"])
            card.pack(side="left", padx=4)
            card.pack_propagate(False)
            # Mini UI mock inside card
            mock_panel = tk.Frame(card, bg=colors["panel"], height=18)
            mock_panel.pack(fill="x")
            tk.Label(mock_panel, text=name, font=("Courier New",6,"bold"),
                     fg=colors["glow"], bg=colors["panel"]).pack(side="left", padx=4)
            mock_body = tk.Frame(card, bg=colors["bg"])
            mock_body.pack(fill="both", expand=True, padx=4, pady=2)
            for txt, fg in [("▬▬▬▬▬▬▬", colors["white2"]),
                            ("▬▬▬▬▬",   colors["white3"]),
                            ("▬▬▬▬▬▬",  colors["white3"])]:
                tk.Label(mock_body, text=txt, font=("Courier New",5),
                         fg=fg, bg=colors["bg"]).pack(anchor="w")
            mock_bar = tk.Frame(card, bg=colors["panel"], height=12)
            mock_bar.pack(fill="x")
            tk.Label(mock_bar, text="▶", font=("Courier New",5),
                     fg=colors["glow"], bg=colors["panel"]).pack(side="left", padx=3)
            def _bind_card(w, c=colors, n=name):
                w.bind("<Button-1>", lambda e, c=c, n=n: _do_apply_preset(c, n))
                w.bind("<Enter>",    lambda e, w=w: w.config(
                    highlightbackground=colors["glow"]) if hasattr(w,"config") else None)
                for ch in w.winfo_children():
                    _bind_card(ch, c, n)
            card.bind("<Button-1>", lambda e, c=colors, n=name: _do_apply_preset(c, n))
            for ch in card.winfo_children():
                for w in [ch] + list(ch.winfo_children()):
                    w.bind("<Button-1>", lambda e, c=colors, n=name: _do_apply_preset(c, n))

        # Active indicator
        tk.Frame(pf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(16,6))
        active_lbl = tk.Label(pf, text=f"Active: {self.settings.get('active_theme','VOID')}",
                              font=("Courier New",7), fg=C["white3"], bg=C["bg"])
        active_lbl.pack(anchor="w", padx=20)

        # ══════════════════════════════════════════════════════════
        #  TAB 2 — COLORS  (full token editor)
        # ══════════════════════════════════════════════════════════
        cf = _make_tab("colors", "COLORS")

        c_outer = tk.Frame(cf, bg=C["bg"])
        c_outer.pack(fill="both", expand=True)
        c_sb = tk.Scrollbar(c_outer, orient="vertical", bg=C["panel"],
                            troughcolor=C["bg"], width=6, relief="flat", bd=0)
        c_sb.pack(side="right", fill="y")
        c_cv = tk.Canvas(c_outer, bg=C["bg"], highlightthickness=0,
                         yscrollcommand=c_sb.set)
        c_cv.pack(side="left", fill="both", expand=True)
        c_sb.config(command=c_cv.yview)
        c_inner = tk.Frame(c_cv, bg=C["bg"])
        c_win = c_cv.create_window(0, 0, anchor="nw", window=c_inner)
        c_inner.bind("<Configure>", lambda e: c_cv.configure(scrollregion=c_cv.bbox("all")))
        c_cv.bind("<Configure>",    lambda e: c_cv.itemconfig(c_win, width=e.width))
        def _c_scroll(e): c_cv.yview_scroll(int(-1*(e.delta/120))*3, "units")
        c_cv.bind("<MouseWheel>", _c_scroll)
        c_inner.bind("<MouseWheel>", _c_scroll)

        ALL_TOKENS = [
            ("BACKGROUNDS",  [
                ("bg",      "Main background"),
                ("panel",   "Panel / sidebar"),
                ("select",  "Selection bg"),
                ("select2", "Deep selection"),
            ]),
            ("BORDERS",  [
                ("border",  "Border (dim)"),
                ("border2", "Border (bright)"),
            ]),
            ("TEXT",  [
                ("white",   "Primary text"),
                ("white2",  "Secondary text"),
                ("white3",  "Muted text"),
                ("glow",    "Accent / hover"),
            ]),
            ("ACCENTS",  [
                ("red",     "Error / warning"),
            ]),
        ]

        self._theme_vars = {}

        def _make_color_entry(parent, key, label):
            rf = tk.Frame(parent, bg=C["bg"])
            rf.pack(fill="x", padx=20, pady=2)
            # Swatch
            sw = tk.Frame(rf, bg=C.get(key,"#000000"), width=18, height=18,
                          highlightthickness=1, highlightbackground=C["border"])
            sw.pack(side="left", padx=(0,8))
            sw.pack_propagate(False)
            # Label
            tk.Label(rf, text=f"{label:<20}", font=("Courier New",8),
                     fg=C["white2"], bg=C["bg"], width=20, anchor="w").pack(side="left")
            # Entry
            var = tk.StringVar(value=C.get(key,"#000000"))
            self._theme_vars[key] = var
            ent = tk.Entry(rf, textvariable=var, font=("Courier New",8),
                           bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                           relief="flat", bd=0, highlightthickness=1,
                           highlightbackground=C["border2"], width=9)
            ent.pack(side="left", ipady=3)
            # Color picker button
            def _pick(k=key, v=var, s=sw):
                try:
                    from tkinter import colorchooser
                    result = colorchooser.askcolor(color=v.get(), title=f"Pick {k}")
                    if result and result[1]:
                        v.set(result[1])
                        try: s.config(bg=result[1])
                        except: pass
                except Exception:
                    pass
            pick_btn = tk.Label(rf, text="⬛", font=("Courier New",9),
                                fg=C["white3"], bg=C["bg"], cursor="hand2")
            pick_btn.pack(side="left", padx=4)
            pick_btn.bind("<Button-1>", lambda e, f=_pick: f())
            # Live swatch update
            def _upd(v=var, s=sw):
                try: s.config(bg=v.get() if v.get().startswith("#") else C["bg"])
                except: pass
            var.trace_add("write", lambda *a, f=_upd: f())
            # Bind scroll to canvas
            for w in (rf, sw, ent, pick_btn):
                w.bind("<MouseWheel>", _c_scroll)

        for section_name, tokens in ALL_TOKENS:
            sf = tk.Frame(c_inner, bg=C["bg"])
            sf.pack(fill="x", pady=(14,2))
            tk.Label(sf, text=section_name, font=("Courier New",6,"bold"),
                     fg=C["white3"], bg=C["bg"]).pack(anchor="w", padx=20)
            tk.Frame(c_inner, bg=C["border2"], height=1).pack(fill="x", padx=20, pady=(2,4))
            sf.bind("<MouseWheel>", _c_scroll)
            for key, label in tokens:
                _make_color_entry(c_inner, key, label)

        tk.Frame(c_inner, bg=C["bg"], height=16).pack()

        def _apply_colors():
            for key, var in self._theme_vars.items():
                try:
                    val = var.get().strip()
                    if val and not val.startswith("#"): val = "#" + val
                    if val: C[key] = val
                except Exception: pass
            C["panel2"] = C["panel"]
            self._rebuild_ui_colors()
            self._save()
            self._toast("Colors applied")

        c_foot = tk.Frame(cf, bg=C["panel"])
        c_foot.pack(fill="x", side="bottom")
        tk.Frame(c_foot, bg=C["border"], height=1).pack(fill="x")
        for txt, cmd in [("[ APPLY ]", _apply_colors),
                         ("[ RESET ]", lambda: (_do_apply_preset(
                             self._theme_presets["VOID"], "VOID")))]:
            b = tk.Label(c_foot, text=txt, font=FM, fg=C["white3"],
                         bg=C["panel"], cursor="hand2", padx=10, pady=8)
            b.pack(side="left", padx=8)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

        # ══════════════════════════════════════════════════════════
        #  TAB 3 — TYPOGRAPHY
        # ══════════════════════════════════════════════════════════
        tf = _make_tab("type", "TYPOGRAPHY")

        tk.Label(tf, text="FONT SETTINGS", font=("Courier New",7),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", padx=20, pady=(16,8))
        tk.Frame(tf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0,12))

        font_families = ["Courier New", "Consolas", "Lucida Console",
                         "Terminal", "Fixedsys", "OCR A Extended"]
        font_var  = tk.StringVar(value="Courier New")
        size_var  = tk.IntVar(value=9)

        def _font_row(label, options, var, width=20):
            r = tk.Frame(tf, bg=C["bg"])
            r.pack(fill="x", padx=20, pady=5)
            tk.Label(r, text=label, font=("Courier New",8), fg=C["white2"],
                     bg=C["bg"], width=18, anchor="w").pack(side="left")
            lbl = tk.Label(r, text=f"[ {var.get()} ]", font=("Courier New",8),
                           fg=C["white"], bg=C["panel"], cursor="hand2",
                           padx=8, pady=3)
            lbl.pack(side="left")
            def _cycle(e=None):
                if isinstance(options[0], str):
                    idx = options.index(var.get()) if var.get() in options else 0
                    var.set(options[(idx+1) % len(options)])
                else:
                    idx = options.index(var.get()) if var.get() in options else 0
                    var.set(options[(idx+1) % len(options)])
                lbl.config(text=f"[ {var.get()} ]")
            lbl.bind("<Button-1>", _cycle)
            return var

        _font_row("Font family",  font_families, font_var)
        _font_row("Base size",    [7, 8, 9, 10, 11, 12], size_var)

        tk.Frame(tf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(16,8))

        # Preview box
        prev_f = tk.Frame(tf, bg=C["panel"], highlightthickness=1,
                          highlightbackground=C["border2"])
        prev_f.pack(fill="x", padx=20, pady=4)
        prev_lbl = tk.Label(prev_f, text="OTERNOS  //  NOW PLAYING\nTrack Title  --  Artist Name\n0:00 ----------- 3:45",
                            font=(font_var.get(), size_var.get()),
                            fg=C["white"], bg=C["panel"],
                            justify="left", padx=12, pady=10)
        prev_lbl.pack(anchor="w")

        def _apply_font():
            fam  = font_var.get()
            sz   = int(size_var.get())
            global FM, FMS, FML, FMX
            FM  = (fam, sz)
            FMS = (fam, sz-1)
            FML = (fam, sz+1, "bold")
            FMX = (fam, sz+4, "bold")
            prev_lbl.config(font=(fam, sz))
            self.settings["font_family"] = fam
            self.settings["font_size"]   = sz
            self._save()
            self._toast(f"Font: {fam} {sz}pt")

        t_foot = tk.Frame(tf, bg=C["panel"])
        t_foot.pack(fill="x", side="bottom")
        tk.Frame(t_foot, bg=C["border"], height=1).pack(fill="x")
        ap = tk.Label(t_foot, text="[ APPLY FONT ]", font=FM,
                      fg=C["white3"], bg=C["panel"], cursor="hand2", padx=10, pady=8)
        ap.pack(side="left", padx=8)
        ap.bind("<Button-1>", lambda e: _apply_font())
        ap.bind("<Enter>",    lambda e: ap.config(fg=C["white"]))
        ap.bind("<Leave>",    lambda e: ap.config(fg=C["white3"]))

        # ══════════════════════════════════════════════════════════
        #  TAB 4 — EXPORT / IMPORT
        # ══════════════════════════════════════════════════════════
        ef = _make_tab("export", "EXPORT")

        tk.Label(ef, text="SAVE & SHARE THEMES", font=("Courier New",7),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", padx=20, pady=(16,8))
        tk.Frame(ef, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0,12))

        # Export current theme as hex string
        import json as _json
        def _export():
            data = {k: C[k] for k in ("bg","panel","border","border2",
                                       "white","white2","white3","glow","select","select2","red")}
            txt = _json.dumps(data, separators=(",",":"))
            export_var.set(txt)

        def _import():
            try:
                txt = export_var.get().strip()
                data = _json.loads(txt)
                C.update(data)
                C["panel2"] = C["panel"]
                self._rebuild_ui_colors()
                self._save()
                self._toast("Theme imported")
            except Exception as ex:
                self._toast(f"Import failed: {ex}")

        tk.Label(ef, text="Theme JSON  (copy to share, paste to import):",
                 font=("Courier New",7), fg=C["white2"], bg=C["bg"]).pack(anchor="w", padx=20)
        export_var = tk.StringVar()
        _export()
        txt_box = tk.Entry(ef, textvariable=export_var, font=("Courier New",7),
                           bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                           relief="flat", bd=0, highlightthickness=1,
                           highlightbackground=C["border2"])
        txt_box.pack(fill="x", padx=20, pady=6, ipady=4)

        e_foot = tk.Frame(ef, bg=C["panel"])
        e_foot.pack(fill="x", side="bottom")
        tk.Frame(e_foot, bg=C["border"], height=1).pack(fill="x")
        for txt, cmd in [("[ EXPORT ]", _export), ("[ IMPORT ]", _import)]:
            b = tk.Label(e_foot, text=txt, font=FM, fg=C["white3"],
                         bg=C["panel"], cursor="hand2", padx=10, pady=8)
            b.pack(side="left", padx=8)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))

        # ── Start on presets tab ──────────────────────────────────
        _switch_tab("presets")

    def _apply_theme_preset(self, name):
        colors = self._theme_presets.get(name)
        if colors:
            C.update(colors)
            C["panel2"] = C["panel"]
            self._rebuild_ui_colors()

    def _rebuild_ui_colors(self):
        """
        Remap every widget color to the new palette.
        If switching away from Miku, restore cybercore widgets first.
        If switching to Miku, apply Miku-specific overrides after.
        The two themes never bleed into each other.
        """
        active = self.settings.get("active_theme", "").upper()
        going_to_miku = (active == "MIKU")
        going_to_nerv = (active == "NERV")
        self._restore_cybercore()

        ALL_TOKENS = ("bg", "panel", "panel2", "border", "border2",
                      "white", "white2", "white3", "glow", "select", "select2", "red")

        _all_theme_colors=set(); _all_theme_panel=set()
        for preset in self._theme_presets.values():
            for tok in ALL_TOKENS:
                v=preset.get(tok,"");
                if v: _all_theme_colors.add(v.lower())
            for tok in ("panel","panel2"):
                v=preset.get(tok,"");
                if v: _all_theme_panel.add(v.lower())
        _all_theme_panel.add(C["panel2"].lower())
        _cur_panel={C["panel"].lower(),C["panel2"].lower()}

        def _recolor(w):
            try:
                cls=w.winfo_class()
                if cls in ("Frame","Labelframe","Canvas"):
                    cur_bg=w.cget("bg").lower()
                    if cur_bg in _cur_panel: w.config(bg=C["panel"])
                    elif cur_bg in _all_theme_colors: w.config(bg=C["bg"])
                    if cls=="Canvas": w.config(highlightbackground=C["border"])
                elif cls=="Label":
                    cur_bg=w.cget("bg").lower(); cur_fg=w.cget("fg").lower()
                    new_bg=C["panel"] if cur_bg in _cur_panel else C["bg"] if cur_bg in _all_theme_colors else None
                    new_fg=C["white"] if cur_fg in _all_theme_colors else None
                    cfg={}
                    if new_bg is not None: cfg["bg"]=new_bg
                    if new_fg is not None: cfg["fg"]=new_fg
                    if cfg: w.config(**cfg)
                elif cls=="Entry":
                    w.config(bg=C["panel"],fg=C["white"],insertbackground=C["glow"],highlightbackground=C["border2"])
                elif cls=="Text":
                    w.config(bg=C["panel"],fg=C["white"],insertbackground=C["glow"],selectbackground=C["select2"],highlightbackground=C["border"])
                elif cls=="Listbox":
                    w.config(bg=C["bg"],fg=C["white"],selectbackground=C["select2"],selectforeground=C["glow"],highlightthickness=0)
                elif cls=="Scrollbar":
                    w.config(bg=C["panel"],troughcolor=C["bg"],activebackground=C["border2"])
                elif cls=="Scale":
                    w.config(bg=C["bg"],fg=C["white"],troughcolor=C["panel"],activebackground=C["glow"])
                elif cls=="Button":
                    w.config(bg=C["panel"],fg=C["white"],activebackground=C["select2"],activeforeground=C["glow"],highlightbackground=C["border"])
            except Exception:
                pass
            for child in w.winfo_children():
                _recolor(child)

        self.root.configure(bg=C["bg"])
        _recolor(self.root)

        for w in self.root.winfo_children():
            if w.winfo_class() == "Toplevel":
                try:
                    w.configure(bg=C["bg"])
                    _recolor(w)
                except Exception:
                    pass

        if going_to_miku:
            self.root.after(50, self._apply_miku_theme)
        elif going_to_nerv:
            self.root.after(50, self._apply_nerv_theme)

        self._set_status("THEME APPLIED")

    # ══════════════════════════════════════
    #  RESTORE CYBERCORE — undo any Miku overrides
    # ══════════════════════════════════════
    def _restore_cybercore(self):
        """
        Called when switching away from Miku back to any cybercore theme.
        Restores all Miku-swapped widgets back to their original cybercore versions.
        Does NOT touch colors — _rebuild_ui_colors handles that afterward.
        """
        global FM, FMS, FML, FMX
        # ── Restore Courier New fonts ──
        FM  = ("Courier New", 9)
        FMS = ("Courier New", 8)
        FML = ("Courier New", 10, "bold")
        FMX = ("Courier New", 13, "bold")

        # ── Sidebar logo: swap MikuLogo → OternosLogo ──
        try:
            if isinstance(self._sidebar_logo, MikuLogo):
                parent = self._sidebar_logo.master
                self._sidebar_logo.destroy()
                self._sidebar_logo = OternosLogo(parent, size=52, bg=C["panel"])
                self._sidebar_logo.pack(side="left", padx=(14, 8))
                self._sidebar_logo.is_playing = getattr(self.engine, "playing", False)
        except Exception:
            pass

        # ── Sidebar wordmark ──
        try:
            for w in self._side_frame.winfo_children():
                for child in (w.winfo_children() if hasattr(w,"winfo_children") else []):
                    if isinstance(child,tk.Label):
                        t=child.cget("text")
                        if t in ("初音ミク","NERV"): child.config(text="OTERNOS",font=("Courier New",8,"bold"),fg=C["white"])
                        elif any(x in str(t) for x in ("VOCALOID","God's In His Heaven","MAGI v")): child.config(text="SYS v1.0",font=("Courier New",6),fg=C["white3"])
        except Exception:
            pass

        # ── Topbar wordmark ──
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for child in w.winfo_children():
                        if isinstance(child, tk.Label):
                            t = str(child.cget("text"))
                            if "M I K U" in t or "N E R V" in t:
                                child.config(text="O T E R N O S",font=("Courier New",9,"bold"),fg=C["white3"])
                                break
                    break
        except Exception:
            pass

        # ── Tab bar: restore ──
        try:
            for key,btn in self.tab_btns.items():
                btn.config(font=("Courier New",7,"bold"))
                btn.unbind("<Enter>"); btn.unbind("<Leave>")
                btn.bind("<Enter>",lambda e,w=btn: w.config(fg=C["white"]))
                btn.bind("<Leave>",lambda e,w=btn,k=key: w.config(fg=C["glow"] if k==getattr(self,"view","") else C["white3"]))
        except Exception:
            pass

        # ── Now-playing labels: restore Courier New ──
        try:
            self.now_title.config(font=("Courier New", 9, "bold"))
            self.now_artist.config(font=("Courier New", 8))
            self.now_album.config(font=("Courier New", 7))
        except Exception:
            pass

        # ── Progress bar: restore ──
        try:
            self.prog_cv.config(bg=C["bg"])
            self.prog_cv.itemconfig(self.prog_fill,fill=C["white2"])
            self.prog_cv.itemconfig(self.prog_dot,fill=C["white"])
        except Exception:
            pass

        # ── Player control buttons: restore Courier New + white hover ──
        try:
            for btn in (self.btn_shuf, self.btn_prev, self.btn_play,
                        self.btn_next, self.btn_repeat):
                sz = 16 if btn is self.btn_play else 12
                btn.config(font=("Courier New", sz), fg=C["white3"])
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, w=btn: ColorAnim.run(
                    self.root, w, "fg", C["white3"], C["white"], duration_ms=40))
                btn.bind("<Leave>", lambda e, w=btn: ColorAnim.run(
                    self.root, w, "fg", C["white"], C["white3"], duration_ms=40))
        except Exception:
            pass

        # ── DataTicker: swap MikuTicker → DataTicker ──
        try:
            if hasattr(self, "_ticker") and isinstance(self._ticker, MikuTicker) \
                    and self._ticker.winfo_exists():
                parent = self._ticker.master
                self._ticker.destroy()
                self._ticker = DataTicker(parent, width=900, height=10, bg=C["panel"])
                self._ticker.pack(fill="x")
        except Exception:
            pass

        # ── CornerBrackets: swap MikuCornerDeco → CornerBrackets ──
        try:
            hdr = self.lib_frame.winfo_children()[0]
            for child in list(hdr.winfo_children()):
                if isinstance(child, MikuCornerDeco):
                    child.destroy()
                    brackets = CornerBrackets(hdr, size=28, bg=C["bg"])
                    brackets.pack(side="left", padx=(0, 6))
                    break
        except Exception:
            pass

        # ── Track list: restore Courier New ──
        try:
            self.track_list.config(font=("Courier New", 9))
        except Exception:
            pass

        # ── Sidebar section labels: restore Courier New ──
        try:
            def _restore_side_fonts(w):
                if isinstance(w, tk.Label):
                    try:
                        f = w.cget("font")
                        if "Consolas" in str(f):
                            sz = 8
                            try:
                                parts = self.root.tk.splitlist(f)
                                sz = int(parts[1]) if len(parts) > 1 else 8
                            except Exception:
                                pass
                            w.config(font=("Courier New", sz))
                    except Exception:
                        pass
                for ch in (w.winfo_children() if hasattr(w, "winfo_children") else []):
                    _restore_side_fonts(ch)
            _restore_side_fonts(self._side_frame)
        except Exception:
            pass

        try:
            self._sidebar_status_lbl.config(font=("Courier New", 6))
        except Exception:
            pass

        # ── Restore viz bar ──
        try:
            self._viz_mf_miku.pack_forget()
            self._viz_mf_nerv.pack_forget()
            self._viz_mf_cyber.pack(side="right")
            if getattr(self,"_viz_mode","").startswith(("miku","nerv_")):
                self._set_viz_mode("hexcore")
        except Exception:
            pass

        # ── Restore viz info bar fonts ──
        try:
            self.viz_track_lbl.config(font=("Courier New", 8), fg=C["white2"])
            self.viz_pos_lbl.config(font=("Courier New", 8),   fg=C["white3"])
            self.viz_mode_lbl.config(font=("Courier New", 8),  fg=C["white3"])
        except Exception:
            pass

        # ── Strip theme prefixes ──
        try:
            cur=self.now_title.cget("text")
            if cur and cur.startswith("♪  "): self.now_title.config(text=cur[3:])
            elif cur and cur.startswith("[NERV] "): self.now_title.config(text=cur[7:])
        except Exception:
            pass

    # ══════════════════════════════════════
    #  MIKU THEME — independent full override
    # ══════════════════════════════════════
    def _apply_miku_theme(self):
        """
        Fully independent Miku theme pass. Runs AFTER _rebuild_ui_colors
        has already applied the Miku color palette. Swaps every cybercore
        widget for its Miku equivalent without touching any cybercore state.
        """
        global FM, FMS, FML, FMX
        # Pick the softest available font on Windows for Miku
        _miku_body = next(
            (f for f in ("Yu Gothic UI", "Meiryo UI", "Microsoft YaHei UI",
                         "Segoe UI", "Consolas")
             if self._font_exists(f)), "Consolas")
        FM  = (_miku_body, 9)
        FMS = (_miku_body, 8)
        FML = (_miku_body, 10, "bold")
        FMX = (_miku_body, 13, "bold")

        # ── Sidebar logo → MikuLogo ──
        try:
            if not isinstance(self._sidebar_logo, MikuLogo):
                parent = self._sidebar_logo.master
                self._sidebar_logo.destroy()
                self._sidebar_logo = MikuLogo(parent, size=52, bg=C["panel"])
                self._sidebar_logo.pack(side="left", padx=(14, 8))
                self._sidebar_logo.is_playing = getattr(self.engine, "playing", False)
        except Exception:
            pass

        # ── Sidebar wordmark ──
        try:
            for w in self._side_frame.winfo_children():
                for child in (w.winfo_children() if hasattr(w, "winfo_children") else []):
                    if isinstance(child, tk.Label):
                        t = child.cget("text")
                        if t == "OTERNOS":
                            child.config(text="初音ミク", font=("Consolas", 8, "bold"),
                                         fg=C["glow"])
                        elif "SYS v" in str(t):
                            child.config(text="VOCALOID ♪", font=("Consolas", 6),
                                         fg=C["white3"])
        except Exception:
            pass

        # ── Topbar wordmark ──
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for child in w.winfo_children():
                        if isinstance(child, tk.Label) and "OTERNOS" in str(child.cget("text")):
                            child.config(text="✦ M I K U  P L A Y E R ✦",
                                         font=("Consolas", 9, "bold"),
                                         fg=C["glow"])
                            break
                    break
        except Exception:
            pass

        # ── Tab bar ──
        try:
            for key, btn in self.tab_btns.items():
                is_active = (key == getattr(self, "view", ""))
                btn.config(font=("Consolas", 7, "bold"),
                           fg=C["glow"] if is_active else C["white3"])
        except Exception:
            pass

        # ── Now-playing labels ──
        try:
            self.now_title.config(font=("Consolas", 9, "bold"), fg=C["white"])
            self.now_artist.config(font=("Consolas", 8), fg=C["glow"])
            self.now_album.config(font=("Consolas", 7), fg=C["white3"])
        except Exception:
            pass

        # ── Progress bar: teal fill, pink dot ──
        try:
            self.prog_cv.config(bg=C["border"])
            self.prog_cv.itemconfig(self.prog_fill, fill=C["glow"])
            self.prog_cv.itemconfig(self.prog_dot,  fill=C["red"])
        except Exception:
            pass

        # ── Player controls: pink hover ──
        try:
            for btn in (self.btn_shuf, self.btn_prev, self.btn_play,
                        self.btn_next, self.btn_repeat):
                sz = 16 if btn is self.btn_play else 12
                btn.config(font=("Consolas", sz), fg=C["white2"])
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, w=btn: ColorAnim.run(
                    self.root, w, "fg", C["white2"], C["red"], duration_ms=60))
                btn.bind("<Leave>", lambda e, w=btn: ColorAnim.run(
                    self.root, w, "fg", C["red"], C["white2"], duration_ms=60))
        except Exception:
            pass

        # ── DataTicker → MikuTicker ──
        try:
            if hasattr(self, "_ticker") and not isinstance(self._ticker, MikuTicker) \
                    and self._ticker.winfo_exists():
                parent = self._ticker.master
                self._ticker.destroy()
                self._ticker = MikuTicker(parent, width=900, height=10, bg=C["panel"])
                self._ticker.pack(fill="x")
        except Exception:
            pass

        # ── CornerBrackets → MikuCornerDeco ──
        try:
            hdr = self.lib_frame.winfo_children()[0]
            for child in list(hdr.winfo_children()):
                if isinstance(child, CornerBrackets):
                    child.destroy()
                    MikuCornerDeco(hdr, size=28, bg=C["bg"]).pack(side="left", padx=(0, 6))
                    break
        except Exception:
            pass

        # ── Track list ──
        try:
            self.track_list.config(font=("Consolas", 9),
                                   fg=C["white2"],
                                   selectbackground=C["select2"],
                                   selectforeground=C["glow"])
        except Exception:
            pass

        # ── Sidebar labels → Consolas ──
        try:
            def _miku_fonts(w):
                if isinstance(w, tk.Label):
                    try:
                        f = w.cget("font")
                        if "Courier" in str(f):
                            sz = 8
                            try:
                                parts = self.root.tk.splitlist(f)
                                sz = int(parts[1]) if len(parts) > 1 else 8
                            except Exception:
                                pass
                            w.config(font=("Consolas", sz))
                    except Exception:
                        pass
                for ch in (w.winfo_children() if hasattr(w, "winfo_children") else []):
                    _miku_fonts(ch)
            _miku_fonts(self._side_frame)
        except Exception:
            pass

        try:
            self._sidebar_status_lbl.config(font=("Consolas", 6), fg=C["white3"])
        except Exception:
            pass

        # ── Switch viz button bar: hide cybercore, show miku ──
        try:
            self._viz_mf_cyber.pack_forget()
            self._viz_mf_miku.pack(side="right")
            # Restyle miku buttons with current palette
            miku_font = ("Yu Gothic UI", 8, "bold") if self._font_exists("Yu Gothic UI") \
                        else ("Consolas", 8, "bold")
            for mode, btn in self._viz_mode_btns.items():
                if mode.startswith("miku"):
                    btn.config(font=miku_font, bg=C["bg"])
            self._set_viz_mode("miku_tails")
        except Exception:
            pass

        # ── Viz info bar: teal Consolas text ──
        try:
            miku_font_sm = ("Yu Gothic UI", 8) if self._font_exists("Yu Gothic UI") \
                           else ("Consolas", 8)
            self.viz_track_lbl.config(font=miku_font_sm, fg=C["glow"])
            self.viz_pos_lbl.config(font=miku_font_sm,   fg=C["white3"])
            self.viz_mode_lbl.config(font=miku_font_sm,  fg=C["white2"])
        except Exception:
            pass

        # ── Now-playing: prefix track title with ♪ ──
        try:
            cur = self.now_title.cget("text")
            if cur and not cur.startswith("♪"):
                self.now_title.config(text="♪  " + cur)
        except Exception:
            pass

        # ── Sidebar section dividers: teal instead of dim white ──
        try:
            def _teal_dividers(w):
                if w.winfo_class() == "Frame":
                    try:
                        if w.cget("bg").lower() in (C["border2"].lower(), C["border"].lower()):
                            w.config(bg=C["glow"])
                    except Exception:
                        pass
                for ch in (w.winfo_children() if hasattr(w, "winfo_children") else []):
                    _teal_dividers(ch)
            _teal_dividers(self._side_frame)
        except Exception:
            pass


    # ═══════════════════════════════════════════════════
    #  NERV THEME
    # ═══════════════════════════════════════════════════
    def _apply_nerv_theme(self):
        global FM,FMS,FML,FMX
        _nf=next((f for f in ("Consolas","Lucida Console","Courier New") if self._font_exists(f)),"Courier New")
        FM=(_nf,9); FMS=(_nf,8); FML=(_nf,10,"bold"); FMX=(_nf,13,"bold")
        RED="#ff0000"; DKRED="#660000"; WHITE="#f0f0f0"
        try:
            for w in self.root.winfo_children():
                if w.winfo_class()=="Frame":
                    for ch in w.winfo_children():
                        if hasattr(ch,"cget") and "OTERNOS" in str(ch.cget("text")):
                            ch.config(text="N E R V",font=(_nf,11,"bold"),fg=RED); break
                    break
        except Exception: pass
        try:
            for w in self._side_frame.winfo_children():
                for ch in (w.winfo_children() if hasattr(w,"winfo_children") else []):
                    if isinstance(ch,tk.Label):
                        t=ch.cget("text")
                        if t=="OTERNOS": ch.config(text="NERV",font=(_nf,8,"bold"),fg=RED)
                        elif "SYS v" in str(t): ch.config(text="God's In His Heaven",font=(_nf,6),fg=DKRED)
        except Exception: pass
        try:
            for key,btn in self.tab_btns.items():
                btn.config(font=(_nf,7,"bold"),fg=RED if key==getattr(self,"view","") else DKRED)
                btn.unbind("<Enter>"); btn.unbind("<Leave>")
                btn.bind("<Enter>",lambda e,w=btn: w.config(fg=RED))
                btn.bind("<Leave>",lambda e,w=btn,k=key: w.config(fg=RED if k==getattr(self,"view","") else DKRED))
        except Exception: pass
        try:
            self.now_title.config(font=(_nf,9,"bold"),fg=WHITE)
            self.now_artist.config(font=(_nf,8),fg=RED); self.now_album.config(font=(_nf,7),fg=DKRED)
            cur=self.now_title.cget("text")
            if cur and not cur.startswith("[NERV]"): self.now_title.config(text="[NERV] "+cur)
        except Exception: pass
        try:
            self.prog_cv.config(bg="#0a0000")
            self.prog_cv.itemconfig(self.prog_fill,fill=RED); self.prog_cv.itemconfig(self.prog_dot,fill=WHITE)
        except Exception: pass
        try:
            for btn in (self.btn_shuf,self.btn_prev,self.btn_play,self.btn_next,self.btn_repeat):
                sz=16 if btn is self.btn_play else 12; btn.config(font=(_nf,sz),fg=DKRED)
                btn.unbind("<Enter>"); btn.unbind("<Leave>")
                btn.bind("<Enter>",lambda e,w=btn: ColorAnim.run(self.root,w,"fg",DKRED,RED,duration_ms=60))
                btn.bind("<Leave>",lambda e,w=btn: ColorAnim.run(self.root,w,"fg",RED,DKRED,duration_ms=60))
        except Exception: pass
        try:
            self.track_list.config(font=(_nf,9),fg=WHITE,selectbackground="#3a0000",selectforeground=RED)
        except Exception: pass
        try:
            self._viz_mf_cyber.pack_forget(); self._viz_mf_miku.pack_forget()
            self._viz_mf_nerv.pack(side="right")
            for mode,btn in self._viz_mode_btns.items():
                if mode.startswith("nerv_"): btn.config(font=(_nf,8,"bold"),bg=C["bg"])
            self._set_viz_mode("nerv_magi")
        except Exception: pass
        try:
            self.viz_track_lbl.config(font=(_nf,8),fg=WHITE)
            self.viz_pos_lbl.config(font=(_nf,8),fg=DKRED); self.viz_mode_lbl.config(font=(_nf,8),fg=RED)
        except Exception: pass

    def _viz_nerv_magi(self,cv,W,H,t,playing,bars):
        import math as _m
        bass=sum(bars[:8])/8 if bars else 0; energy=sum(bars)/len(bars) if bars else 0
        for fx,fy,fr,fl in [(0.06,0.18,0.09,True),(0.88,0.09,0.08,False),(0.72,0.06,0.07,False),(0.04,0.55,0.07,False),(0.30,0.85,0.08,True)]:
            pts=[]
            for k in range(6):
                a=k*_m.pi/3; pts.extend([fx*W+fr*min(W,H)*_m.cos(a),fy*H+fr*min(W,H)*_m.sin(a)])
            bv=int(50+bass*140)
            cv.create_polygon(pts,outline=f"#{bv:02x}0000",fill=f"#{bv:02x}0000" if fl else "",width=2)
        col_w=W//3
        for ci,(lbl,seg) in enumerate(zip(["MELCHIOR","BALTHASAR","CASPER"],[bars[:16],bars[16:32],bars[32:]])):
            seg=seg or [0]; avg=sum(seg)/len(seg); cx0=ci*col_w
            bv=int(40+avg*160); hv=int(130+avg*120)
            cv.create_rectangle(cx0+4,32,cx0+col_w-6,H-12,outline=f"#{bv:02x}0000",fill="",width=1)
            cv.create_text(cx0+col_w//2,22,text=f"[ {lbl} ]",font=("Consolas",max(7,int(W*0.016))),fill=f"#{hv:02x}0000",anchor="center")
            n=len(seg); bw_=(col_w-20)/max(n,1)
            for i,h in enumerate(seg):
                bh=max(2,h*(H-80)); bx=cx0+10+i*bw_; fv=int(55+h*195)
                cv.create_rectangle(bx,H-30-bh,bx+bw_-1,H-30,fill=f"#{fv:02x}0000",outline="")
        er=min(W,H)*(0.042+bass*0.05); ev=int(120+bass*130)
        cv.create_oval(W//2-er,H//2-er,W//2+er,H//2+er,outline=f"#{ev:02x}0000",fill="",width=2)
        cv.create_text(W//2,H//2,text="NERV",font=("Consolas",max(8,int(er*0.85))),fill=f"#{ev:02x}0000",anchor="center")
        msgs=["God's In His Heaven","All's Right With The World","MAGI ONLINE","ANGEL DETECTED","PATTERN: BLUE","SYNC RATE: 400%"]
        mv=int(80+energy*100)
        cv.create_text(W//2,H*0.94,text=f"// {msgs[(t//140)%len(msgs)]} //",font=("Consolas",max(7,int(W*0.014))),fill=f"#{mv:02x}0000",anchor="center")

    def _viz_nerv_angel(self,cv,W,H,t,playing,bars):
        import math as _m
        bass=sum(bars[:8])/8 if bars else 0; energy=sum(bars)/len(bars) if bars else 0
        cx,cy=W/2,H/2; ang=t*0.008; max_r=min(W,H)*0.44
        for fx,fy,fr,fl in [(0.07,0.12,0.09,True),(0.86,0.08,0.08,False),(0.06,0.78,0.07,False),(0.88,0.80,0.09,True)]:
            pts=[]
            for k in range(6):
                a=ang*0.25+k*_m.pi/3; pts.extend([fx*W+fr*min(W,H)*_m.cos(a),fy*H+fr*min(W,H)*_m.sin(a)])
            bv=int(35+bass*90)
            cv.create_polygon(pts,outline=f"#{bv:02x}0000",fill=f"#{bv//2:02x}0000" if fl else "",width=2)
        for ring in range(1,6):
            frac=ring/5; amp=bars[min(len(bars)-1,int(frac*len(bars)))] if bars else 0
            r=max_r*frac*(0.9+amp*0.22); rv=int(55+amp*200); pts=[]
            for k in range(6):
                a=ang+k*_m.pi/3; pts.extend([cx+r*_m.cos(a),cy+r*_m.sin(a)])
            pts.extend(pts[:2])
            cv.create_line(pts,fill=f"#{rv:02x}0000",width=max(1,int(3.5-ring*0.5)))
        cr=min(W,H)*(0.05+bass*0.07); fv=int(160+bass*90); pts=[]
        for k in range(6):
            a=ang*2+k*_m.pi/3; pts.extend([cx+cr*_m.cos(a),cy+cr*_m.sin(a)])
        cv.create_polygon(pts,fill=f"#{fv:02x}0000",outline=f"#{min(255,fv+60):02x}0000",width=2)
        cv2=int(50+energy*80)
        for tx,ty,anch,lbl in [(8,8,"nw","PATTERN: BLUE"),(W-8,8,"ne","ANGEL CLASS: ?"),(8,H-8,"sw","A.T. LVL: MAX"),(W-8,H-8,"se","NEUTRALIZE")]:
            cv.create_text(tx,ty,text=lbl,font=("Consolas",max(6,int(W*0.012))),fill=f"#{cv2:02x}0000",anchor=anch)

    def _viz_nerv_eva(self,cv,W,H,t,playing,bars):
        import math as _m
        bass=sum(bars[:8])/8 if bars else 0; energy=sum(bars)/len(bars) if bars else 0
        for fx,fy,fr in [(0.10,0.18,0.07),(0.87,0.14,0.08),(0.09,0.82,0.06),(0.88,0.78,0.07)]:
            pts=[]
            for k in range(6):
                a=k*_m.pi/3; pts.extend([fx*W+fr*min(W,H)*_m.cos(a),fy*H+fr*min(W,H)*_m.sin(a)])
            bv=int(18+bass*30)
            cv.create_polygon(pts,outline=f"#{bv:02x}0000",fill="",width=1)
        hv=int(130+energy*120)
        cv.create_text(W//2,14,text="EVA-01  //  UNIT STATUS  //  NERV HQ",font=("Consolas",max(7,int(W*0.016))),fill=f"#{hv:02x}0000",anchor="center")
        cv.create_line(10,26,W-10,26,fill=f"#{hv//2:02x}0000",width=1)
        sync=min(1.0,energy*1.4+bass*0.4); sy_top=36; sy_bot=H-60; sy_h=sy_bot-sy_top; sx0=16; sx1=48
        cv.create_rectangle(sx0,sy_top,sx1,sy_bot,outline="#550000",fill="",width=1)
        sv=int(80+sync*170)
        cv.create_rectangle(sx0+2,sy_bot-int(sync*sy_h),sx1-2,sy_bot-2,fill=f"#{sv:02x}0000",outline="")
        cv.create_text((sx0+sx1)//2,sy_top-8,text="SYNC",font=("Consolas",max(6,int(W*0.012))),fill="#660000",anchor="center")
        cv.create_text((sx0+sx1)//2,sy_bot+8,text=f"{int(sync*400)}%",font=("Consolas",max(6,int(W*0.013))),fill=f"#{sv:02x}0000",anchor="center")
        batt=max(0.0,1.0-(t%600)/600.0) if playing else 1.0; bx0=W-50; bx1=W-18
        cv.create_rectangle(bx0,sy_top,bx1,sy_bot,outline="#550000",fill="",width=1)
        bv2=int(200*batt)
        cv.create_rectangle(bx0+2,sy_bot-int(batt*sy_h),bx1-2,sy_bot-2,fill=f"#{bv2:02x}0000",outline="")
        cv.create_text((bx0+bx1)//2,sy_top-8,text="PWR",font=("Consolas",max(6,int(W*0.012))),fill="#660000",anchor="center")
        cv.create_text((bx0+bx1)//2,sy_bot+8,text=f"{int(batt*100)}%",font=("Consolas",max(6,int(W*0.013))),fill=f"#{bv2:02x}0000",anchor="center")
        n=len(bars); bw_=(W-120)/max(n,1)
        for i,h in enumerate(bars):
            bh=max(1,h*(H-100)*0.68); fv=int(50+h*200)
            cv.create_rectangle(60+i*bw_,H-60-bh,60+(i+1)*bw_-1,H-60,fill=f"#{fv:02x}0000",outline="")
        for si,line in enumerate(["PILOT: IKARI SHINJI",f"A.T. FIELD: {'ACTIVE' if bass>0.3 else 'STANDBY'}",f"THREAT: {'CRITICAL' if energy>0.7 else 'NOMINAL'}",f"CORE TEMP: {int(20+energy*80)}°C"]):
            lv=int(55+energy*90); hot=any(x in line for x in ("CRITICAL","ACTIVE"))
            cv.create_text(W//2,H-52+si*13,text=line,font=("Consolas",max(6,int(W*0.013))),fill=f"#{min(255,lv+60):02x}0000" if hot else f"#{lv:02x}0000",anchor="center")
        if bass>0.6 and (t//8)%2==0:
            cv.create_rectangle(0,0,W,H,outline=f"#{min(255,int(bass*200)+60):02x}0000",fill="",width=3)
            cv.create_text(W//2,H//2-20,text="⚠  ANGEL ALERT  ⚠",font=("Consolas",max(10,int(W*0.025))),fill="#ff0000",anchor="center")

    # ══════════════════════════════════════
    #  COMMAND PALETTE
    # ══════════════════════════════════════

    # ══════════════════════════════════════════════════════
    #  AUTO-PLAYLIST FROM SEED TRACK
    # ══════════════════════════════════════════════════════
    def _open_auto_playlist(self):
        idx = self.current_idx
        if idx < 0 or idx >= len(self.library):
            self._set_status("PLAY A TRACK FIRST"); return
        seed = self.library[idx]
        win = tk.Toplevel(self.root); win.title("AUTO-PLAYLIST")
        win.configure(bg=C["bg"]); win.geometry("520x460"); win.transient(self.root)
        tk.Label(win,text="AUTO-PLAYLIST",font=FMX,fg=C["white"],bg=C["bg"]).pack(pady=(16,2),anchor="w",padx=20)
        tk.Label(win,text=f"Seed: {seed['title']} — {seed.get('artist','')}",
                 font=FMS,fg=C["glow"],bg=C["bg"]).pack(anchor="w",padx=20)
        tk.Frame(win,bg=C["border"],height=1).pack(fill="x",padx=20,pady=6)
        lf=tk.Frame(win,bg=C["bg"]); lf.pack(fill="both",expand=True,padx=12,pady=4)
        sb=tk.Scrollbar(lf,bg=C["panel"],troughcolor=C["bg"],activebackground=C["border2"],width=8)
        sb.pack(side="right",fill="y")
        lb=tk.Listbox(lf,bg=C["bg"],fg=C["white2"],font=FM,selectbackground=C["select"],
                      relief="flat",bd=0,highlightthickness=0,yscrollcommand=sb.set)
        lb.pack(fill="both",expand=True); sb.config(command=lb.yview)
        seed_path=seed["path"]; seed_bpm=self._bpm_cache.get(seed_path,0)
        seed_mood=self._mood_cache.get(seed_path,"")
        scored=[]
        for i,t in enumerate(self.library):
            if i==idx: continue
            p=t.get("path",""); bpm=self._bpm_cache.get(p,0); mood=self._mood_cache.get(p,"")
            score=0
            if seed_bpm and bpm: score+=max(0,30-abs(bpm-seed_bpm))
            if mood and mood==seed_mood: score+=25
            score+=min(10,sum(1 for e in self._history if e.get("title")==t.get("title",""))*2)
            score-=self._skip_counts.get(p,0)*8
            scored.append((score,i,t))
        scored.sort(key=lambda x:-x[0])
        result_indices=[i for _,i,_ in scored[:30]]
        for _,_,t in scored[:30]:
            lb.insert("end",f"  {t['title'][:42]}  —  {t.get('artist','')[:22]}")
        def _load():
            self.queue=[idx]+result_indices; self.queue_pos=0; self._play_item(0)
            self._set_status(f"AUTO-PLAYLIST: {len(result_indices)+1} TRACKS"); win.destroy()
        tk.Button(win,text="▶  PLAY THIS PLAYLIST",font=FM,fg=C["white"],bg=C["border"],
                  relief="flat",bd=0,command=_load,cursor="hand2",pady=6).pack(padx=20,pady=8,fill="x")

    # ══════════════════════════════════════════════════════
    #  FLOW MODE
    # ══════════════════════════════════════════════════════
    def _toggle_flow_mode(self):
        self._flow_mode=not self._flow_mode
        self._set_status("🌊 FLOW MODE ON" if self._flow_mode else "🌊 FLOW MODE OFF")

    def _flow_enqueue(self, current_track):
        if len(self.queue)-self.queue_pos > 3: return
        path=current_track.get("path",""); cur_bpm=self._bpm_cache.get(path,0)
        cur_mood=self._mood_cache.get(path,""); in_queue=set(self.queue); scored=[]
        for i,t in enumerate(self.library):
            if i in in_queue: continue
            p=t.get("path",""); bpm=self._bpm_cache.get(p,0); mood=self._mood_cache.get(p,"")
            score=0
            if cur_bpm and bpm: score+=max(0,20-abs(bpm-cur_bpm))
            if mood==cur_mood: score+=20
            score+=random.randint(0,8)-self._skip_counts.get(p,0)*8
            scored.append((score,i))
        scored.sort(key=lambda x:-x[0])
        adds=[i for _,i in scored[:3]]
        self.queue.extend(adds)
        if adds: self._set_status(f"FLOW: +{len(adds)} QUEUED")

    # ══════════════════════════════════════════════════════
    #  SMART SKIP
    # ══════════════════════════════════════════════════════
    def _toggle_smart_skip(self):
        self._smart_skip_on=not self._smart_skip_on
        self._set_status("⚡ SMART SKIP ON" if self._smart_skip_on else "⚡ SMART SKIP OFF")

    # ══════════════════════════════════════════════════════
    #  VOICE COMMANDS
    # ══════════════════════════════════════════════════════
    def _toggle_voice_control(self):
        self._voice_on=not self._voice_on
        if self._voice_on:
            self._set_status("🎙 VOICE ON"); self._start_voice_thread()
        else:
            self._set_status("🎙 VOICE OFF")

    def _start_voice_thread(self):
        def _listen():
            try:
                import subprocess
                ps=(
                    'Add-Type -AssemblyName System.Speech;'
                    '$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine;'
                    '$r.SetInputToDefaultAudioDevice();'
                    '$c=New-Object System.Speech.Recognition.Choices;'
                    '@("skip","next","previous","pause","play","louder","softer","shuffle","stop","ambient","repeat","flow mode") | ForEach-Object { $c.Add($_) };'
                    '$g=New-Object System.Speech.Recognition.GrammarBuilder($c);'
                    '$gr=New-Object System.Speech.Recognition.Grammar($g);'
                    '$r.LoadGrammar($gr);'
                    'while($true){try{$res=$r.Recognize([timespan]::FromSeconds(5));if($res){Write-Output $res.Text}}catch{}}'
                )
                proc=subprocess.Popen(["powershell","-NoProfile","-Command",ps],
                    stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=0x08000000)
                while self._voice_on:
                    line=proc.stdout.readline().decode(errors="ignore").strip().lower()
                    if line: self.root.after(0,lambda l=line: self._handle_voice(l))
                proc.terminate()
            except Exception:
                self.root.after(0,lambda: self._set_status("🎙 VOICE: UNAVAILABLE"))
        threading.Thread(target=_listen,daemon=True).start()

    def _handle_voice(self, cmd):
        self._set_status(f"🎙 {cmd.upper()}")
        if cmd in ("skip","next"):    self._next()
        elif cmd=="previous":          self._prev()
        elif cmd in ("pause","play"):  self._toggle_play()
        elif cmd=="louder":            self.volume=min(1.0,self.volume+0.1); self._upd_vol()
        elif cmd=="softer":            self.volume=max(0.0,self.volume-0.1); self._upd_vol()
        elif cmd=="shuffle":           self._toggle_shuffle()
        elif cmd=="stop":              self.engine.stop()
        elif cmd=="ambient":           self._open_ambient_mode()
        elif cmd=="repeat":            self._toggle_repeat()
        elif "flow" in cmd:            self._toggle_flow_mode()

    # ══════════════════════════════════════════════════════
    #  MINI LYRICS TICKER
    # ══════════════════════════════════════════════════════
    def _start_lyric_ticker(self):
        if self._lyric_ticker_job:
            try: self.root.after_cancel(self._lyric_ticker_job)
            except: pass
        self._lyric_ticker_job=None

    def _sync_lyric_ticker(self):
        if not hasattr(self,"lyric_ticker_lbl"): return
        idx=self.current_idx
        if idx<0 or idx>=len(self.library): return
        t=self.library[idx]
        key=(t.get("artist","").lower().strip(),t.get("title","").lower().strip())
        synced=self._synced_cache.get(key)
        if not synced:
            try: self.lyric_ticker_lbl.config(text="")
            except: pass
            return
        pos_ms=int(self.engine.get_position()*1000) if self.engine.is_playing else 0
        cur_line=""
        for ms,text in synced:
            if ms<=pos_ms: cur_line=text
            else: break
        try: self.lyric_ticker_lbl.config(text=f"♪  {cur_line}" if cur_line else "")
        except: pass

    # ══════════════════════════════════════════════════════
    #  AMBIENT MODE
    # ══════════════════════════════════════════════════════
    def _open_ambient_mode(self):
        if self._ambient_win and self._ambient_win.winfo_exists():
            self._ambient_win.destroy(); self._ambient_win = None; return
        win = tk.Toplevel(self.root)
        win.title("AMBIENT")
        win.configure(bg="#000000")
        win.attributes("-fullscreen", True)
        win.wm_attributes("-topmost", True)
        self._ambient_win = win
        cv = tk.Canvas(win, bg="#000000", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        win.bind("<Escape>",    lambda e: (win.destroy(), setattr(self, "_ambient_win", None)))
        cv.bind("<Button-1>",  lambda e: (win.destroy(), setattr(self, "_ambient_win", None)))
        self._ambient_cv = cv
        self._ambient_t  = 0

        # Pre-generate static noise field for CRT texture (reused every frame)
        self._ambient_noise = []
        import random as _rnd
        for _ in range(320):
            self._ambient_noise.append((_rnd.randint(0, 1920), _rnd.randint(0, 1080),
                                        _rnd.randint(1, 3), _rnd.uniform(0.01, 0.06)))

        # Pre-generate floating hex glyph positions
        self._ambient_glyphs = []
        HEX_CHARS = "0123456789ABCDEF◈◉○●□■▪▫▸▹△▽◇◆"
        for _ in range(55):
            self._ambient_glyphs.append({
                "x":    _rnd.uniform(0.02, 0.98),
                "y":    _rnd.uniform(0.05, 0.92),
                "char": _rnd.choice(HEX_CHARS),
                "speed": _rnd.uniform(0.00008, 0.00025),
                "phase": _rnd.uniform(0, math.pi * 2),
                "size":  _rnd.choice([7, 8, 9, 10]),
            })

        self._ambient_tick()

    def _ambient_tick(self):
        if not (self._ambient_win and self._ambient_win.winfo_exists()):
            return
        cv  = self._ambient_cv
        cv.delete("all")
        W   = cv.winfo_width()  or 1920
        H   = cv.winfo_height() or 1080
        t   = self._ambient_t

        # ── Background void ──────────────────────────────────────────────────
        cv.configure(bg="#000000")

        # ── CRT scanlines (every 3px, very subtle) ───────────────────────────
        for yy in range(0, H, 3):
            cv.create_line(0, yy, W, yy, fill="#060606", width=1)

        # ── Floating hex glyphs — drift vertically, fade in/out ──────────────
        for g in self._ambient_glyphs:
            gy  = (g["y"] + t * g["speed"]) % 1.0
            alpha_t = math.sin(t * 0.012 + g["phase"])
            # Map to brightness: 0.02–0.10 range (very dim)
            bright = int((0.06 + 0.04 * alpha_t) * 255)
            col = f"#{bright:02x}{bright:02x}{bright:02x}"
            cv.create_text(int(g["x"] * W), int(gy * H),
                           text=g["char"],
                           font=("Courier New", g["size"]),
                           fill=col, anchor="center")

        # ── Subtle vignette border ────────────────────────────────────────────
        vpad = 60
        for i in range(6):
            alpha = int(18 - i * 2)
            col   = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
            cv.create_rectangle(i*vpad//6, i*vpad//6,
                                W - i*vpad//6, H - i*vpad//6,
                                outline=col, fill="", width=vpad//6)

        # ── Track info ───────────────────────────────────────────────────────
        idx = self.current_idx
        if 0 <= idx < len(self.library):
            tr     = self.library[idx]
            title  = tr.get("title", "")
            artist = tr.get("artist", "")
        elif self._sp_mode:
            title  = self.now_title.cget("text")
            artist = self.now_artist.cget("text")
            tr     = {}
        else:
            title  = "OTERNOS  P L A Y E R"
            artist = ""
            tr     = {}

        # Breathing scale on title
        breath = 1.0 + 0.018 * math.sin(t * 0.025)
        title_fs  = max(28, int(W * 0.034 * breath))
        artist_fs = max(14, int(title_fs * 0.46))

        # ── System prefix line ───────────────────────────────────────────────
        cv.create_text(W // 2, H * 0.36,
                       text="[ OTERNOS  //  AMBIENT ]",
                       font=("Courier New", 9),
                       fill="#1e1e1e", anchor="center")

        # ── Thin horizontal rule above title ─────────────────────────────────
        rule_y = H * 0.415
        rule_w = min(W * 0.55, 700)
        cv.create_line(W//2 - rule_w//2, rule_y,
                       W//2 + rule_w//2, rule_y,
                       fill="#1c1c1c", width=1)
        cv.create_line(W//2 - rule_w//2, rule_y + 3,
                       W//2 + rule_w//2, rule_y + 3,
                       fill="#0e0e0e", width=1)

        # ── Title — white glow with dim shadow ───────────────────────────────
        # Shadow
        cv.create_text(W // 2 + 2, H * 0.47 + 2,
                       text=title[:52],
                       font=("Courier New", title_fs, "bold"),
                       fill="#0a0a0a", anchor="center")
        # Main text
        cv.create_text(W // 2, H * 0.47,
                       text=title[:52],
                       font=("Courier New", title_fs, "bold"),
                       fill="#e8e8e8", anchor="center")

        # ── Artist — dimmer, tracked spacing ─────────────────────────────────
        if artist:
            spaced = "  ".join(artist.upper()[:36])
            cv.create_text(W // 2, H * 0.47 + title_fs + 22,
                           text=spaced,
                           font=("Courier New", artist_fs),
                           fill="#383838", anchor="center")

        # ── Thin rule below artist ────────────────────────────────────────────
        below_rule_y = H * 0.47 + title_fs + 22 + artist_fs + 14
        cv.create_line(W//2 - rule_w//2, below_rule_y,
                       W//2 + rule_w//2, below_rule_y,
                       fill="#141414", width=1)

        # ── Synced lyric line ─────────────────────────────────────────────────
        key = (tr.get("artist","").lower().strip(), tr.get("title","").lower().strip())
        synced = self._synced_cache.get(key)
        if synced and (self.engine.is_playing or self._sp_playing):
            if self._sp_mode and self._sp_dur_ms > 0:
                pos_ms = self._sp_pos_ms
            else:
                pos_ms = int(self.engine.get_position() * 1000)
            cur_line = ""
            for ms, line in synced:
                if ms <= pos_ms: cur_line = line
                else: break
            if cur_line:
                lyric_y = below_rule_y + 38
                cv.create_text(W // 2, lyric_y,
                               text=cur_line[:80],
                               font=("Courier New", max(13, int(W * 0.016))),
                               fill="#2a2a2a", anchor="center")

        # ── Progress bar — slim, monochrome, Signalis-style ──────────────────
        if self._sp_mode and self._sp_dur_ms > 0:
            dur = self._sp_dur_ms / 1000.0
            pos = self._sp_pos_ms / 1000.0
        else:
            dur = self.engine.duration
            pos = self.engine.get_position() if self.engine.is_playing else getattr(self.engine, "_pos_cache", 0)
        r_prog = min(1.0, pos / dur) if dur > 0 else 0

        bar_w  = W * 0.52
        bar_x  = (W - bar_w) / 2
        bar_y  = H - 54
        # Track bg
        cv.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + 2,
                            fill="#111111", outline="")
        # Fill — white, no color
        if r_prog > 0:
            cv.create_rectangle(bar_x, bar_y, bar_x + bar_w * r_prog, bar_y + 2,
                                fill="#2e2e2e", outline="")
        # Playhead dot
        px = bar_x + bar_w * r_prog
        cv.create_rectangle(px - 3, bar_y - 2, px + 3, bar_y + 4,
                            fill="#484848", outline="")

        # Time readout
        def _fmt(s):
            m, s2 = divmod(int(max(0, s)), 60)
            return f"{m}:{s2:02d}"
        cv.create_text(bar_x - 10, bar_y + 1,
                       text=_fmt(pos), font=("Courier New", 8),
                       fill="#1e1e1e", anchor="e")
        cv.create_text(bar_x + bar_w + 10, bar_y + 1,
                       text=_fmt(dur), font=("Courier New", 8),
                       fill="#1e1e1e", anchor="w")

        # ── Clock — bottom right, very dim ───────────────────────────────────
        import time as _ti
        cv.create_text(W - 32, H - 22,
                       text=_ti.strftime("%H:%M"),
                       font=("Courier New", 11),
                       fill="#1a1a1a", anchor="se")

        # ── System status string — bottom left ───────────────────────────────
        playing_sym = "▶" if (self.engine.is_playing or self._sp_playing) else "⏸"
        cv.create_text(32, H - 22,
                       text=f"{playing_sym}  SYS::AMBIENT  //  ESC to exit",
                       font=("Courier New", 8),
                       fill="#161616", anchor="sw")

        self._ambient_t += 1
        cv.after(50, self._ambient_tick)

    # ══════════════════════════════════════════════════════
    #  CONTEXT-AWARE SIDEBAR
    # ══════════════════════════════════════════════════════
    def _update_context_sidebar(self, track):
        if not hasattr(self,"_ctx_frame"): return
        for w in self._ctx_frame.winfo_children(): w.destroy()
        if not track: return
        tk.Label(self._ctx_frame,text="NOW PLAYING",font=("Courier New",6),
                 fg=C["white3"],bg=C["panel"]).pack(anchor="w",padx=8,pady=(4,0))
        path=track.get("path",""); bpm=self._bpm_cache.get(path,0)
        mood=self._mood_cache.get(path,""); skips=self._skip_counts.get(path,0)
        for text,val in [(f"BPM: {bpm}" if bpm else "",C["glow"]),(mood,C["white2"]),
                          (f"⏭ skipped {skips}×" if skips else "",C["white3"])]:
            if text:
                tk.Label(self._ctx_frame,text=f"  {text}",font=("Courier New",7),
                         fg=val,bg=C["panel"]).pack(anchor="w",padx=8)
        artist=track.get("artist","").lower()
        similar=[t for t in self.library
                 if t.get("artist","").lower()==artist and t.get("title","")!=track.get("title","")][:4]
        if similar:
            tk.Label(self._ctx_frame,text="MORE BY ARTIST",font=("Courier New",6),
                     fg=C["white3"],bg=C["panel"]).pack(anchor="w",padx=8,pady=(6,0))
            for st in similar:
                lbl=tk.Label(self._ctx_frame,text=f"  {st['title'][:22]}",font=("Courier New",7),
                             fg=C["white3"],bg=C["panel"],cursor="hand2",anchor="w")
                lbl.pack(fill="x")
                def _ps(e,t=st):
                    i=next((j for j,x in enumerate(self.library) if x is t),-1)
                    if i>=0: self.queue=[i]; self.queue_pos=0; self._play_item(0)
                lbl.bind("<Button-1>",_ps)
                lbl.bind("<Enter>",lambda e,w=lbl: w.config(fg=C["white"]))
                lbl.bind("<Leave>",lambda e,w=lbl: w.config(fg=C["white3"]))

    # ══════════════════════════════════════════════════════
    #  SMART FOLDERS
    # ══════════════════════════════════════════════════════
    def _open_smart_folders(self):
        win=tk.Toplevel(self.root); win.title("SMART FOLDERS")
        win.configure(bg=C["bg"]); win.geometry("640x540"); win.transient(self.root)
        tk.Label(win,text="SMART FOLDERS",font=FMX,fg=C["white"],bg=C["bg"]).pack(pady=(16,4),anchor="w",padx=20)
        tk.Label(win,text="Auto-populated folders based on rules",font=FMS,fg=C["white3"],bg=C["bg"]).pack(anchor="w",padx=20)
        tk.Frame(win,bg=C["border"],height=1).pack(fill="x",padx=20,pady=6)
        folders=[
            ("⚡ High Energy",     lambda t: self._mood_cache.get(t.get("path",""),"") in ("⚡ EUPHORIC","🔥 ENERGETIC")),
            ("🌙 Late Night",      lambda t: self._mood_cache.get(t.get("path",""),"") in ("🌙 CHILL","💤 MELLOW")),
            ("🔥 Fast >130 BPM",   lambda t: self._bpm_cache.get(t.get("path",""),0)>130),
            ("💤 Slow <80 BPM",    lambda t: 0<self._bpm_cache.get(t.get("path",""),0)<80),
            ("⭐ Most Played",     lambda t: sum(1 for e in self._history if e.get("title")==t.get("title",""))>=3),
            ("⏭ Never Skipped",   lambda t: self._skip_counts.get(t.get("path",""),0)==0 and t.get("duration",0)>60),
            ("🆕 Recently Added",  lambda t: self.library.index(t)>=max(0,len(self.library)-50)),
        ]
        nb=tk.Frame(win,bg=C["bg"]); nb.pack(fill="x",padx=20,pady=(0,4))
        ca=tk.Frame(win,bg=C["bg"]); ca.pack(fill="both",expand=True,padx=12,pady=4)
        def _show(name,rule):
            for w in ca.winfo_children(): w.destroy()
            matches=[t for t in self.library if rule(t)]
            tk.Label(ca,text=f"{name}  ({len(matches)} tracks)",font=FM,fg=C["glow"],bg=C["bg"]).pack(anchor="w",padx=8,pady=(4,2))
            lf2=tk.Frame(ca,bg=C["bg"]); lf2.pack(fill="both",expand=True)
            sb2=tk.Scrollbar(lf2,bg=C["panel"],troughcolor=C["bg"],width=8); sb2.pack(side="right",fill="y")
            lb2=tk.Listbox(lf2,bg=C["bg"],fg=C["white2"],font=FM,selectbackground=C["select"],
                           relief="flat",bd=0,highlightthickness=0,yscrollcommand=sb2.set)
            lb2.pack(fill="both",expand=True); sb2.config(command=lb2.yview)
            idxs=[]
            for t in matches:
                lb2.insert("end",f"  {t['title'][:42]}  —  {t.get('artist','')[:22]}")
                try: idxs.append(self.library.index(t))
                except: pass
            def _pa():
                if idxs: self.queue=list(idxs); self.queue_pos=0; self._play_item(0); self._set_status(f"PLAYING: {name}")
            tk.Button(ca,text=f"▶  PLAY ALL ({len(matches)})",font=FM,fg=C["white"],bg=C["border"],
                      relief="flat",bd=0,command=_pa,cursor="hand2",pady=4).pack(padx=8,pady=6,fill="x")
        for name,rule in folders:
            b=tk.Label(nb,text=name,font=FMS,fg=C["white3"],bg=C["panel"],cursor="hand2",padx=6,pady=3)
            b.pack(side="left",padx=2,pady=2)
            b.bind("<Button-1>",lambda e,n=name,r=rule: _show(n,r))
            b.bind("<Enter>",lambda e,w=b: w.config(fg=C["white"]))
            b.bind("<Leave>",lambda e,w=b: w.config(fg=C["white3"]))
        if folders: _show(*folders[0])

    def _open_palette(self):
        if self._palette_win and self._palette_win.winfo_exists():
            self._palette_win.focus()
            return

        win = tk.Toplevel(self.root)
        win.title("")
        win.configure(bg=C["bg"])
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        # Centre over main window
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        pw, ph = 480, 340
        win.geometry(f"{pw}x{ph}+{rx + rw//2 - pw//2}+{ry + rh//4}")
        self._palette_win = win

        # Border frame
        outer = tk.Frame(win, bg=C["glow"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # Search input
        tk.Label(inner, text="⌨  COMMAND PALETTE", font=FMS,
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", padx=14, pady=(10,4))
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=0)

        search_var = tk.StringVar()
        entry = tk.Entry(inner, textvariable=search_var, font=FML,
                         bg=C["panel"], fg=C["white"],
                         insertbackground=C["glow"],
                         relief="flat", bd=0, highlightthickness=0)
        entry.pack(fill="x", padx=16, pady=(10, 6), ipady=6)
        entry.focus_set()

        # Results list
        results_frame = tk.Frame(inner, bg=C["bg"])
        results_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Build command registry
        COMMANDS = [
            ("▶ Play / Pause",          self._toggle_play),
            ("⏭ Next track",            self._next),
            ("⏮ Previous track",        self._prev),
            ("◈ All Tracks",            lambda: self._switch_view("library")),
            ("◈ Queue",                 lambda: self._switch_view("queue")),
            ("◈ Visualizer",            lambda: self._switch_view("visualizer")),
            ("◈ Lyrics",                lambda: self._switch_view("lyrics")),
            ("◈ History",               lambda: self._switch_view("history")),
            ("◈ Spotify",               lambda: self._switch_view("spotify")),
            ("◈ YouTube",               lambda: self._switch_view("youtube")),
            ("⊡ Mini Player",          self._toggle_mini_player),
            ("⏾ Sleep Timer",          self._open_sleep_timer),
            ("✎ Edit Tags",             lambda: self._open_tag_editor(self.current_idx)),
            ("⊹ Add Bookmark",         self._add_bookmark),
            ("⊗ View Bookmarks",       self._open_bookmarks),
            ("⇌ Toggle Shuffle",       self._toggle_shuffle),
            ("↺ Toggle Repeat",        self._toggle_repeat),
            ("⊞ Find Duplicates",      self._open_duplicate_detector),
            ("↗ Export M3U",           self._export_playlist_m3u),
            ("◫ Smart Playlist",       self._open_smart_playlist),
            ("⧗ Watch Folders",        self._open_watch_dirs),
            ("★ Recommendations",      self._open_recommendations),
            ("🎨 Theme Editor",         self._open_theme_editor),
            ("⌨ Hotkeys",              self._open_hotkey_editor),
            ("⚙ Settings",             self._open_settings),
            ("A-B Set A",              self._ab_set_a),
            ("A-B Set B",              self._ab_set_b),
            ("A-B Clear",              self._ab_clear),
            ("Speed cycle",            self._cycle_speed),
            ("🎙 Voice Control",        self._toggle_voice_control),
            ("🌊 Flow Mode",            self._toggle_flow_mode),
            ("⚡ Smart Skip",           self._toggle_smart_skip),
            ("🌌 Ambient Mode",         self._open_ambient_mode),
            ("🎵 Auto-Playlist",        self._open_auto_playlist),
            ("📁 Smart Folders",        self._open_smart_folders),
        ]
        # Add playlist entries dynamically
        for pl_name in list(self.playlists.keys())[:20]:
            name = pl_name
            COMMANDS.append((f"♦ Playlist: {name}",
                             lambda n=name: self._load_playlist(n)))

        result_btns = []

        def _refresh(q=""):
            for w in results_frame.winfo_children():
                w.destroy()
            result_btns.clear()
            q = q.lower().strip()
            shown = [(lbl, cmd) for lbl, cmd in COMMANDS
                     if not q or q in lbl.lower()] [:12]
            for i, (lbl, cmd) in enumerate(shown):
                bg = C["select2"] if i == 0 else C["bg"]
                row = tk.Frame(results_frame, bg=bg, cursor="hand2")
                row.pack(fill="x")
                tk.Label(row, text=lbl, font=FM, fg=C["white"],
                         bg=bg, anchor="w", padx=16, pady=5).pack(fill="x")
                def _run(c=cmd):
                    win.destroy()
                    self._palette_win = None
                    c()
                for w in (row,) + tuple(row.winfo_children()):
                    w.bind("<Button-1>", lambda e, f=_run: f())
                    w.bind("<Enter>",    lambda e, r=row: r.config(bg=C["select2"]))
                    w.bind("<Leave>",    lambda e, r=row, b=bg: r.config(bg=b))
                result_btns.append((row, cmd))

        search_var.trace_add("write", lambda *a: _refresh(search_var.get()))
        _refresh()

        def _key(e):
            if e.keysym == "Escape":
                win.destroy()
                self._palette_win = None
            elif e.keysym == "Return" and result_btns:
                win.destroy()
                self._palette_win = None
                result_btns[0][1]()
        entry.bind("<KeyPress>", _key)

        win.bind("<FocusOut>", lambda e: (win.destroy(),
                                          setattr(self, "_palette_win", None)))

    # ══════════════════════════════════════
    #  ALBUM VIEW
    # ══════════════════════════════════════
    def _build_album_view(self):
        self.album_frame = tk.Frame(self.content, bg=C["bg"])

        hdr = tk.Frame(self.album_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="ALBUMS", font=FMX, fg=C["white"],
                 bg=C["bg"]).pack(side="left")
        tk.Frame(self.album_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(8, 0))

        lf = tk.Frame(self.album_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                          width=6, bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        self._alb_cv = tk.Canvas(lf, bg=C["bg"], highlightthickness=0,
                                  yscrollcommand=sb.set)
        self._alb_cv.pack(side="left", fill="both", expand=True)
        sb.config(command=self._alb_cv.yview)
        self._alb_inner = tk.Frame(self._alb_cv, bg=C["bg"])
        self._alb_win   = self._alb_cv.create_window(
            0, 0, anchor="nw", window=self._alb_inner)
        self._alb_inner.bind("<Configure>",
            lambda e: self._alb_cv.configure(scrollregion=self._alb_cv.bbox("all")))
        self._alb_cv.bind("<Configure>",
            lambda e: self._alb_cv.itemconfig(self._alb_win, width=e.width))
        self._alb_cv.bind("<MouseWheel>",
            lambda e: self._alb_cv.yview_scroll(-3 if e.delta > 0 else 3, "units"))

    def _refresh_album_view(self):
        for w in self._alb_inner.winfo_children():
            w.destroy()

        # Group tracks by album
        from collections import defaultdict
        albums = defaultdict(list)
        for i, t in enumerate(self.library):
            al = t.get("album","") or "Unknown Album"
            albums[al].append(i)

        COLS   = 4
        CELL_W = 148
        CELL_H = 170

        row_frame = None
        for col_idx, (album_name, idxs) in enumerate(sorted(albums.items())):
            if col_idx % COLS == 0:
                row_frame = tk.Frame(self._alb_inner, bg=C["bg"])
                row_frame.pack(fill="x", padx=16, pady=4)

            cell = tk.Frame(row_frame, bg=C["panel2"], width=CELL_W,
                            height=CELL_H, cursor="hand2")
            cell.pack(side="left", padx=4)
            cell.pack_propagate(False)

            # Art square
            art_cv = tk.Canvas(cell, bg=C["panel"], width=CELL_W, height=100,
                               highlightthickness=0)
            art_cv.pack()

            # Draw mosaic / placeholder
            self._draw_album_art_async(art_cv, idxs, CELL_W, 100)

            # Album name
            lbl = tk.Label(cell, text=album_name[:22], font=FMS,
                           fg=C["white"], bg=C["panel2"], wraplength=CELL_W-8,
                           justify="left", anchor="w")
            lbl.pack(fill="x", padx=6, pady=(4,0))

            # Artist + track count
            artist = self.library[idxs[0]].get("artist","") if idxs else ""
            tk.Label(cell, text=f"{artist[:18]}  ·  {len(idxs)} tracks",
                     font=("Courier New",7), fg=C["white3"],
                     bg=C["panel2"], anchor="w").pack(fill="x", padx=6)

            def _play_album(idx_list=idxs):
                self.queue     = list(idx_list)
                self.queue_pos = 0
                self._play_item(0)

            for w in (cell, lbl) + tuple(cell.winfo_children()):
                w.bind("<Double-Button-1>", lambda e, f=_play_album: f())
                w.bind("<Enter>",
                    lambda e, c=cell: c.config(bg=C["select2"],
                        highlightbackground=C["glow"],
                        highlightthickness=1))
                w.bind("<Leave>",
                    lambda e, c=cell: c.config(bg=C["panel2"],
                        highlightthickness=0))

    def _draw_album_art_async(self, cv, idxs, w, h):
        """Draw a simple geometric placeholder; could be extended with real art."""
        cv.delete("all")
        import random as _r
        seed = hash(str(idxs[:2])) % 10000
        _rng = _r.Random(seed)
        # Unique geometric pattern per album
        for _ in range(6):
            x = _rng.randint(0, w)
            y = _rng.randint(0, h)
            r = _rng.randint(10, 40)
            br = _rng.randint(30, 60)
            cv.create_oval(x-r, y-r, x+r, y+r,
                           fill=f"#{br:02x}{br:02x}{br:02x}", outline="")
        # Overlay album initial
        for i, idx in enumerate(idxs[:4]):
            t = self.library[idx]
            al = t.get("album","?")[:1].upper()
            cv.create_text(w//2, h//2, text=al,
                           font=("Courier New",32,"bold"),
                           fill=C["white3"])
            break

    # ══════════════════════════════════════
    #  PLAYLIST MOSAIC ART
    # ══════════════════════════════════════
    def _refresh_pl_sidebar(self):
        for w in self.pl_sidebar.winfo_children():
            w.destroy()
        for name, idxs in self.playlists.items():
            # Mosaic swatch (16×16 colored dot derived from playlist hash)
            h = abs(hash(name)) % 200 + 55
            dot_col = f"#{h:02x}{h:02x}{h:02x}"

            f = tk.Frame(self.pl_sidebar, bg=C["panel"], cursor="hand2")
            f.pack(fill="x")

            # Small colored dot
            dot = tk.Canvas(f, bg=C["panel"], width=8, height=8,
                            highlightthickness=0)
            dot.pack(side="left", padx=(14,4), pady=6)
            dot.create_oval(0, 0, 8, 8, fill=dot_col, outline="")

            l = tk.Label(f, text=f"{name[:18]}  [{len(idxs)}]",
                         font=FMS, fg=C["white2"], bg=C["panel"],
                         anchor="w", pady=5)
            l.pack(side="left", fill="x", expand=True, padx=(0,14))

            def _enter(e, fr=f, lb=l):
                ColorAnim.run(self.root, lb, "fg", C["white2"], C["white"], duration_ms=50)
                ColorAnim.run(self.root, lb, "bg", C["panel"], C["select2"], duration_ms=50)
                ColorAnim.run(self.root, fr, "bg", C["panel"], C["select2"], duration_ms=50)
            def _leave(e, fr=f, lb=l):
                ColorAnim.run(self.root, lb, "fg", C["white"], C["white2"], duration_ms=50)
                ColorAnim.run(self.root, lb, "bg", C["select2"], C["panel"], duration_ms=50)
                ColorAnim.run(self.root, fr, "bg", C["select2"], C["panel"], duration_ms=50)

            def _load(n=name):
                self._load_playlist(n)

            for w in (f, l, dot):
                w.bind("<Button-1>", lambda e, c=_load: c())
                w.bind("<Enter>",    _enter)
                w.bind("<Leave>",    _leave)
                if hasattr(self, "_side_scroll_fn"):
                    w.bind("<MouseWheel>", self._side_scroll_fn)

    # ── POLL LOOP ─────────────────────────
    def _poll(self):
        if self._sp_mode:
            if not self.seeking and self._sp_dur_ms > 0:
                r = min(1.0, self._sp_pos_ms / self._sp_dur_ms)
                self._draw_prog(r)
                self.lbl_cur.config(text=self._fmt(self._sp_pos_ms / 1000))
                self.lbl_tot.config(text=self._fmt(self._sp_dur_ms / 1000))
            if self._sp_playing:
                self._sp_pos_ms += 100
        elif self.engine.is_playing and not self.seeking:
            pos = self.engine.get_position()
            dur = self.engine.duration
            if dur > 0:
                self._draw_prog(min(1.0, pos/dur))
                self.lbl_cur.config(text=self._fmt(pos))
                # Gapless: preload next track when 5s remain
                if dur - pos < 5.0:
                    self._gapless_preload()
            if self.engine.is_done():
                self.engine.is_playing = False
                self.wavevis.set_active(False)
                self.btn_play.config(text="▶")
                self.status_lbl.config(text="[ IDLE ]")
                if self.repeat_mode == "one":
                    self._play_item(self.queue_pos)
                elif self.repeat_mode == "all" or self.queue_pos < len(self.queue)-1:
                    self._next()
                else:
                    # Queue exhausted — release the source lock so Spotify/etc can take over
                    self._active_source = "none"
                    self._set_source_badge("none")
        # Lyric ticker sync
        self._sync_lyric_ticker()
        # A-B loop check
        self._ab_check()
        self.root.after(100 if HW_ACCEL else 250, self._poll)

    def _fmt(self, s):
        s = max(0, int(s))
        return f"{s//60}:{s%60:02d}"

    # ── HELP VIEW ─────────────────────────
    def _build_help_view(self):
        self.help_frame = tk.Frame(self.content, bg=C["bg"])
        top = tk.Frame(self.help_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="HELP", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        tk.Label(top, text="how to use oternos player", font=FMS, fg=C["white3"], bg=C["bg"]).pack(side="left", padx=12)
        tk.Frame(self.help_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        outer = tk.Frame(self.help_frame, bg=C["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=(8, 8))
        sb = tk.Scrollbar(outer, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        cv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.config(command=cv.yview)
        self._help_cv = cv  # store direct reference for scroll routing
        inner = tk.Frame(cv, bg=C["bg"])
        win = cv.create_window(0, 0, anchor="nw", window=inner)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(win, width=e.width))
        def _help_scroll(e):
            cv.yview_scroll(int(-1*(e.delta/120))*3, "units")
        cv.bind("<MouseWheel>", _help_scroll)
        inner.bind("<MouseWheel>", _help_scroll)
        # Bind to all children recursively after they're created
        def _bind_all(w):
            w.bind("<MouseWheel>", _help_scroll)
            for child in w.winfo_children():
                _bind_all(child)
        self.help_frame.bind("<Configure>", lambda e: _bind_all(inner))

        def _sec(t):
            tk.Label(inner, text=t, font=("Courier New", 10, "bold"),
                fg=C["white"], bg=C["bg"]).pack(anchor="w", pady=(18, 2))
            tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", pady=(0, 6))

        def _sub(t):
            tk.Label(inner, text="  " + t, font=("Courier New", 9, "bold"),
                fg=C["white2"], bg=C["bg"]).pack(anchor="w", pady=(10, 2))

        def _dot(t):
            row = tk.Frame(inner, bg=C["bg"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text="  ·", font=FM, fg=C["white3"], bg=C["bg"], width=3, anchor="w").pack(side="left", padx=(8,0))
            tk.Label(row, text=t, font=FMS, fg=C["white2"], bg=C["bg"], anchor="w", wraplength=660, justify="left").pack(side="left", fill="x", expand=True)
            row.bind("<MouseWheel>", lambda e: cv.yview_scroll(int(-1*(e.delta/120))*3, "units"))

        _sec("GETTING STARTED")
        _sub("Adding Music")
        _dot("Click \'Add Files\' in the sidebar to add MP3, WAV, FLAC, or M4A files.")
        _dot("Click \'Add Folder\' to scan an entire folder and add all audio files at once.")
        _dot("Your library saves automatically — tracks stay next time you open the app.")
        _sub("Playing a Track")
        _dot("Double-click any track in the Library to start playing it.")
        _dot("Press SPACE to play/pause at any time.")
        _dot("Use the ▶ button at the bottom center to play/pause.")

        _sec("PLAYBACK CONTROLS")
        _sub("Buttons")
        _dot("▶ / ⏸  —  Play or pause the current track.")
        _dot("⏮  —  Previous track (or restart if past 3 seconds).")
        _dot("⏭  —  Skip to next track.")
        _dot("⇌  —  Toggle shuffle — plays tracks in random order.")
        _dot("↺  —  Toggle repeat: off → repeat all → repeat one.")
        _sub("Progress Bar")
        _dot("Click anywhere on the bar to jump to that position.")
        _dot("Click and drag to scrub through the track.")
        _sub("Volume")
        _dot("Click the volume bar on the right to set volume.")
        _dot("Scroll the mouse wheel over the volume bar to adjust.")
        _sub("Keyboard Shortcuts")
        _dot("SPACE — Play / Pause")
        _dot("LEFT / RIGHT ARROW — Previous / Next track")
        _dot("CTRL + LEFT / RIGHT — Seek back / forward 10 seconds")
        _dot("UP / DOWN ARROW — Volume up / down")

        _sec("LIBRARY")
        _sub("Managing Tracks")
        _dot("Right-click any track to Play, Add to Queue, Add to Playlist, Edit Tags, or Remove.")
        _dot("Click a column header (TITLE, ARTIST, ALBUM, TIME) to sort by that field. Click again to reverse order.")
        _dot("Search also filters by album name.")
        _sub("Tag Editor")
        _dot("Right-click a track → Edit Tags to change title, artist, and album.")
        _dot("Changes are saved directly to the file.")

        _sec("PLAYLISTS")
        _sub("Creating a Playlist")
        _dot("Click \'+ New Playlist\' in the sidebar, type a name, press Enter.")
        _sub("Adding Tracks")
        _dot("Right-click a track in the Library → Add to Playlist → select playlist.")
        _sub("Managing")
        _dot("Click a playlist name in the sidebar to open it.")
        _dot("Right-click tracks inside to remove them or reorder by dragging.")

        _sec("QUEUE")
        _dot("Right-click any track → Add to Queue to add it to the play queue.")
        _dot("Click the QUEUE tab to see and manage upcoming tracks.")
        _dot("Drag tracks up or down in the queue to reorder them.")
        _dot("Tracks play in queue order after the current track finishes.")

        _sec("VISUALIZER")
        _dot("Click the VISUALIZER tab — it animates automatically when music plays.")
        _dot("Change the visualizer style in Settings (⚙ top right).")

        _sec("LYRICS")
        _dot("Click the LYRICS tab while a track is playing.")
        _dot("Lyrics are fetched automatically from the internet based on title and artist.")
        _dot("If not found automatically, you can paste them in manually.")

        _sec("HISTORY")
        _dot("The HISTORY tab shows every track you have played with timestamps.")
        _dot("Click any entry to play that track again.")

        _sec("ALBUMS")
        _dot("The ALBUMS tab groups your library by album automatically.")
        _dot("Click an album to see all its tracks.")

        _sec("SIDEBAR TOOLS")
        _sub("Sleep Timer")
        _dot("Set a timer — the player stops automatically when it runs out.")
        _sub("Mini Player")
        _dot("Compact view showing just controls and track info.")
        _sub("Watch Folders")
        _dot("Set folders to monitor — new audio files appear in your library instantly.")
        _sub("Smart Playlist")
        _dot("Create a playlist based on rules (artist, duration, date added, etc).")
        _dot("Updates automatically as your library changes.")
        _sub("Find Dupes")
        _dot("Scans your library for duplicate tracks and shows them side by side.")
        _sub("Export M3U")
        _dot("Save your current playlist as an M3U file for use in other media players.")
        _sub("Hotkeys")
        _dot("View and customize global keyboard shortcuts for playback control.")
        _sub("Recommend")
        _dot("Get track suggestions based on your listening history.")
        _sub("Themes")
        _dot("Change the color scheme — pick a preset or build a custom theme.")
        _sub("Bookmarks")
        _dot("Save a position in a track to resume at that exact point later.")

        _sec("STREAMING")
        _sub("Spotify")
        _dot("Click SPOTIFY tab → connect your account to browse and play your playlists.")
        _dot("Requires a Spotify Premium account for full playback control.")
        _sub("SoundCloud")
        _dot("Click SOUNDCLOUD tab to search and stream SoundCloud tracks.")
        _dot("No account required to search. Log in to access your liked tracks.")
        _sub("YouTube")
        _dot("Click YOUTUBE tab → search for any song → double-click to play.")
        _dot("Requires yt-dlp: run  pip install yt-dlp  in your terminal.")
        _dot("Played tracks are cached locally so they load instantly next time.")

        _sec("SETTINGS  (⚙)")
        _sub("EQ / Equalizer")
        _dot("Boost or cut frequency bands with presets: Bass Boost, Treble, Rock, Classical, and more.")
        _dot("Select \'flat\' to disable EQ processing.")
        _sub("Last.fm")
        _dot("Enter your Last.fm API key to enable automatic scrobbling of every track you play.")
        _sub("Audio Device")
        _dot("Select which output device to use for audio playback.")

        tk.Frame(inner, bg=C["bg"], height=20).pack()



# ─────────────────────────────────────────
#  SOUND ENGINE — disabled
# ─────────────────────────────────────────
import threading
import tempfile
import os as _os

_SND = {}
def _init_sounds(): pass
def _play_wav(path): pass

# ─────────────────────────────────────────
#  SPOTIFY CLIENT
# ─────────────────────────────────────────
# Credentials are read from environment variables.
# Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your environment,
# or create a .env file and load it before running.
SPOTIFY_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID",     "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES        = (
    "user-read-playback-state user-modify-playback-state "
    "user-read-currently-playing playlist-read-private "
    "user-library-read user-top-read"
)

class SpotifyAuth:
    TOKEN_FILE = str(Path.home() / ".oternos_spotify.json")

    def __init__(self):
        self.access_token  = None
        self.refresh_token = None
        self.expires_at    = 0
        self._code_verifier= None
        self._auth_code    = None
        self._server       = None
        self._load_token()

    def _load_token(self):
        try:
            d = json.loads(Path(self.TOKEN_FILE).read_text())
            self.access_token  = d.get("access_token")
            self.refresh_token = d.get("refresh_token")
            self.expires_at    = d.get("expires_at", 0)
        except: pass

    def _save_token(self):
        try:
            Path(self.TOKEN_FILE).write_text(json.dumps({
                "access_token":  self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at":    self.expires_at,
            }))
        except: pass

    def is_authenticated(self):
        return bool(self.access_token)

    def token_valid(self):
        return self.access_token and time.time() < self.expires_at - 30

    def get_auth_url(self):
        """Generate PKCE auth URL."""
        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        self._code_verifier = verifier
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        params = urllib.parse.urlencode({
            "client_id":             SPOTIFY_CLIENT_ID,
            "response_type":         "code",
            "redirect_uri":          SPOTIFY_REDIRECT_URI,
            "scope":                 SPOTIFY_SCOPES,
            "code_challenge_method": "S256",
            "code_challenge":        challenge,
        })
        return f"https://accounts.spotify.com/authorize?{params}"

    def start_callback_server(self, on_code):
        """Start local HTTP server to catch OAuth callback."""
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                qs     = urllib.parse.parse_qs(parsed.query)
                if "code" in qs:
                    outer._auth_code = qs["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type","text/html")
                    self.end_headers()
                    self.wfile.write(b"<html><body style='background:#000;color:#fff;font-family:monospace;padding:40px'>"
                                     b"<h2>OTERNOS // SPOTIFY AUTH OK</h2>"
                                     b"<p>You can close this window.</p></body></html>")
                    on_code(qs["code"][0])
                else:
                    self.send_response(400)
                    self.end_headers()
            def log_message(self, *a): pass

        self._server = HTTPServer(("127.0.0.1", 8888), Handler)
        t = threading.Thread(target=self._server.handle_request, daemon=True)
        t.start()

    def exchange_code(self, code, callback=None):
        """Exchange auth code for tokens using PKCE."""
        def _do():
            try:
                data = urllib.parse.urlencode({
                    "grant_type":    "authorization_code",
                    "code":          code,
                    "redirect_uri":  SPOTIFY_REDIRECT_URI,
                    "client_id":     SPOTIFY_CLIENT_ID,
                    "code_verifier": self._code_verifier,
                }).encode()
                req = urllib.request.Request(
                    "https://accounts.spotify.com/api/token",
                    data=data,
                    headers={"Content-Type":"application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req) as r:
                    d = json.loads(r.read())
                self.access_token  = d["access_token"]
                self.refresh_token = d.get("refresh_token")
                self.expires_at    = time.time() + d.get("expires_in", 3600)
                self._save_token()
                if callback: callback(True)
            except Exception as e:
                if callback: callback(False, str(e))
        threading.Thread(target=_do, daemon=True).start()

    def refresh(self, callback=None):
        """Refresh access token via PKCE (no client secret needed)."""
        if not self.refresh_token: return
        def _do():
            try:
                data = urllib.parse.urlencode({
                    "grant_type":    "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id":     SPOTIFY_CLIENT_ID,
                }).encode()
                req = urllib.request.Request(
                    "https://accounts.spotify.com/api/token",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    d = json.loads(r.read())
                self.access_token = d["access_token"]
                self.expires_at   = time.time() + d.get("expires_in", 3600)
                if "refresh_token" in d:
                    self.refresh_token = d["refresh_token"]
                self._save_token()
                if callback: callback(True)
            except Exception as e:
                if callback: callback(False, str(e))
        threading.Thread(target=_do, daemon=True).start()


class SpotifyAPI:
    BASE = "https://api.spotify.com/v1"

    def __init__(self, auth: SpotifyAuth):
        self.auth = auth

    def _get(self, endpoint, params=None):
        # Auto-refresh if token expired but refresh token exists
        if not self.auth.token_valid():
            if self.auth.refresh_token:
                # Synchronous refresh attempt
                try:
                    data = urllib.parse.urlencode({
                        "grant_type":    "refresh_token",
                        "refresh_token": self.auth.refresh_token,
                        "client_id":     SPOTIFY_CLIENT_ID,
                    }).encode()
                    req = urllib.request.Request(
                        "https://accounts.spotify.com/api/token",
                        data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        d = json.loads(r.read())
                    self.auth.access_token = d["access_token"]
                    self.auth.expires_at   = time.time() + d.get("expires_in", 3600)
                    if "refresh_token" in d:
                        self.auth.refresh_token = d["refresh_token"]
                    self.auth._save_token()
                except Exception:
                    return None
            else:
                return None
        url = f"{self.BASE}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.auth.access_token}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            self._last_error = f"HTTP {e.code}: {e.read().decode()[:300]}"
            if e.code == 401:
                self.auth.access_token = None
            return None
        except Exception as e:
            self._last_error = f"request error: {e}"
            return None

    def _post(self, endpoint, body=None):
        if not self.auth.token_valid(): return None
        url  = f"{self.BASE}{endpoint}"
        data = json.dumps(body or {}).encode()
        req  = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type":  "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status
        except: return None

    def _put(self, endpoint, body=None):
        if not self.auth.token_valid(): return None
        url  = f"{self.BASE}{endpoint}"
        data = json.dumps(body or {}).encode()
        req  = urllib.request.Request(url, data=data, method="PUT", headers={
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type":  "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status
        except: return None

    def me(self):
        return self._get("/me")

    def playlists(self, limit=50):
        return self._get("/me/playlists", {"limit": limit})

    def playlist_tracks(self, playlist_id, limit=50, offset=0):
        return self._get(f"/playlists/{playlist_id}/tracks",
                         {"limit": limit, "offset": offset, "fields":
                          "items(track(name,artists,album,duration_ms,uri)),total"})

    def liked_songs(self, limit=50, offset=0):
        return self._get("/me/tracks", {"limit": limit, "offset": offset})

    def search(self, q, limit=20):
        # Development mode apps are limited — fetch multiple pages and combine
        all_tracks = []
        offsets = [0, 5, 10, 15, 20, 25, 30, 35]
        for offset in offsets:
            data = self._get("/search", {"q": q, "type": "track", "offset": offset})
            if not data:
                break
            items = data.get("tracks", {}).get("items", [])
            if not items:
                break
            all_tracks.extend(items)
        if not all_tracks:
            return None
        # Return in the same format the caller expects
        return {"tracks": {"items": all_tracks}}

    def now_playing(self):
        return self._get("/me/player/currently-playing")

    def play(self, uris=None, context_uri=None, offset=None):
        body = {}
        if uris:        body["uris"]        = uris
        if context_uri: body["context_uri"] = context_uri
        if offset:      body["offset"]      = offset
        return self._put("/me/player/play", body)

    def pause(self):
        return self._put("/me/player/pause")

    def next_track(self):
        return self._post("/me/player/next")

    def prev_track(self):
        return self._post("/me/player/previous")

    def seek(self, ms):
        return self._put(f"/me/player/seek?position_ms={int(ms)}")

    def volume(self, pct):
        return self._put(f"/me/player/volume?volume_percent={int(pct)}")

    def top_tracks(self, limit=30):
        return self._get("/me/top/tracks", {"limit": limit, "time_range": "short_term"})

    def devices(self):
        return self._get("/me/player/devices")

    def transfer(self, device_id, play=True):
        return self._put("/me/player", {"device_ids": [device_id], "play": play})

    def play_on(self, device_id, uris=None, offset=None):
        body = {"device_id": device_id}
        if uris:   body["uris"]   = uris
        if offset: body["offset"] = offset
        return self._put(f"/me/player/play?device_id={device_id}", body)

    def _put_full(self, url, body=None):
        if not self.auth.token_valid(): return None, 0
        data = json.dumps(body or {}).encode()
        req  = urllib.request.Request(url, data=data, method="PUT", headers={
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type":  "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return None, r.status
        except urllib.error.HTTPError as e:
            try:
                body_err = e.read().decode()
            except:
                body_err = ""
            return body_err, e.code


# ─────────────────────────────────────────
#  SOUNDCLOUD CLIENT
# ─────────────────────────────────────────
SC_TOKEN_FILE = str(Path.home() / ".oternos_soundcloud.json")

def _sc_fetch_client_id():
    """
    Scrape a live client_id from SoundCloud's web JS bundles.
    SoundCloud embeds a rotating client_id in their frontend JS — this
    finds it at runtime so we never rely on a hardcoded (dead) value.
    Returns a string client_id, or None on failure.
    """
    import re as _re
    try:
        # 1. Fetch the SoundCloud homepage
        req = urllib.request.Request(
            "https://soundcloud.com",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/120.0.0.0 Safari/537.36"})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="replace")

        # 2. Find all versioned JS bundle URLs
        scripts = _re.findall(
            r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"',
            html)

        # 3. Search each bundle (newest first) for client_id
        for script_url in reversed(scripts):
            try:
                jreq = urllib.request.Request(
                    script_url,
                    headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(jreq, timeout=10) as jr:
                    js = jr.read().decode("utf-8", errors="replace")
                match = _re.search(r'client_id\s*:\s*"([a-zA-Z0-9]{20,})"', js)
                if match:
                    return match.group(1)
            except Exception:
                continue
    except Exception:
        pass
    return None


class SoundCloudAPI:
    BASE          = "https://api-v2.soundcloud.com"
    _cached_cid   = None   # class-level cache — fetched once per session

    def __init__(self):
        self.oauth_token = None
        self._load_token()
        # Resolve client_id: prefer cached, then fetch live, then hard fallback
        if not SoundCloudAPI._cached_cid:
            fetched = _sc_fetch_client_id()
            SoundCloudAPI._cached_cid = fetched or ""
        self.client_id = SoundCloudAPI._cached_cid

    # ── token persistence ──────────────────
    def _load_token(self):
        try:
            d = json.loads(Path(SC_TOKEN_FILE).read_text())
            self.oauth_token = d.get("oauth_token")
        except Exception:
            pass

    def _save_token(self):
        try:
            Path(SC_TOKEN_FILE).write_text(
                json.dumps({"oauth_token": self.oauth_token}))
        except Exception:
            pass

    # ── refresh client_id on demand ────────
    def refresh_client_id(self):
        """Force a fresh scrape — call this if requests start failing."""
        SoundCloudAPI._cached_cid = None
        fetched = _sc_fetch_client_id()
        SoundCloudAPI._cached_cid = fetched or ""
        self.client_id = SoundCloudAPI._cached_cid
        return bool(self.client_id)

    @property
    def ready(self):
        return bool(self.client_id)

    # ── internal helpers ───────────────────
    def _headers(self):
        h = {
            "Accept":     "application/json; charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        }
        if self.oauth_token:
            h["Authorization"] = f"OAuth {self.oauth_token}"
        return h

    def _get(self, endpoint, params=None):
        if not self.client_id:
            return None
        p = dict(params or {})
        p["client_id"] = self.client_id
        url = f"{self.BASE}{endpoint}?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # client_id is stale — clear cache so next call re-fetches
                SoundCloudAPI._cached_cid = None
            return None
        except Exception:
            return None

    # ── public API ─────────────────────────
    def search(self, q, limit=40):
        data = self._get("/search/tracks", {"q": q, "limit": limit})
        return (data or {}).get("collection", [])

    def likes(self, limit=100):
        """Fetch the authenticated user's liked tracks."""
        if not self.oauth_token:
            return []
        # Use api-v2 for /me (old v1 endpoint is dead)
        me_data = self._get("/me")
        if not me_data:
            return []
        uid = me_data.get("id")
        if not uid:
            return []
        data = self._get(f"/users/{uid}/likes", {"limit": limit})
        items = (data or {}).get("collection", [])
        tracks = []
        for it in items:
            t = it.get("track") or (it if it.get("kind") == "track" else None)
            if t:
                tracks.append(t)
        return tracks

    def get_stream_url(self, track):
        """
        Resolve the best direct MP3 stream URL for a track.
        Prefers progressive (direct MP3) transcodings; falls back to
        re-fetching the track via /resolve if no transcodings present.
        """
        # -- Try transcodings from the track object first --
        url = self._best_progressive(track)
        if url:
            return url

        # -- If no transcodings, re-fetch the full track from API --
        permalink = track.get("permalink_url") or track.get("uri")
        if permalink:
            resolved = self._resolve(permalink)
            if resolved:
                url = self._best_progressive(resolved)
                if url:
                    return url

        return None

    def _best_progressive(self, track):
        """Extract and resolve a progressive (direct MP3) stream from transcodings."""
        media = (track.get("media") or {}).get("transcodings", [])
        for tc in media:
            fmt = (tc.get("format") or {})
            if fmt.get("protocol") == "progressive":
                raw_url = tc.get("url")
                if raw_url:
                    resolved = self._resolve_stream(raw_url)
                    if resolved:
                        return resolved
        return None

    def _resolve(self, permalink_url):
        """Use /resolve to fetch full track data including transcodings."""
        if not self.client_id:
            return None
        url = (f"{self.BASE}/resolve?"
               + urllib.parse.urlencode({"url": permalink_url,
                                         "client_id": self.client_id}))
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def _resolve_stream(self, transcoding_url):
        """Hit a transcoding URL to get the actual CDN stream URL."""
        if not self.client_id:
            return None
        full = (transcoding_url + "?"
                + urllib.parse.urlencode({"client_id": self.client_id}))
        if self.oauth_token:
            full += f"&oauth_token={self.oauth_token}"
        req = urllib.request.Request(full, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read())
            return d.get("url")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                SoundCloudAPI._cached_cid = None
            return None
        except Exception:
            return None


# ─────────────────────────────────────────
#  YOUTUBE CLIENT
# ─────────────────────────────────────────
class YouTubeAPI:
    """
    YouTube search and streaming via yt-dlp — no API key required.
    Install: pip install yt-dlp
    """

    @staticmethod
    def _ffmpeg_dir():
        """Return the directory containing ffmpeg/ffprobe at runtime."""
        import sys as _sys, os as _os
        candidates = []
        # Always check next to the exe first (most reliable for end users)
        if getattr(_sys, "frozen", False):
            candidates.append(_os.path.dirname(_sys.executable))
        # Then PyInstaller temp extraction dir (for bundled binaries)
        if hasattr(_sys, "_MEIPASS"):
            candidates.append(_sys._MEIPASS)
        # Then script directory (running from source)
        try:
            candidates.append(_os.path.dirname(_os.path.abspath(__file__)))
        except Exception:
            pass
        for d in candidates:
            if _os.path.isfile(_os.path.join(d, "ffmpeg.exe")):
                return d
        # Last resort: return exe dir and hope ffmpeg is on PATH
        return candidates[0] if candidates else ""

    def search(self, query, max_results=50):
        """Search YouTube via yt-dlp. Returns list of {id, title, channel, duration}."""
        try:
            import yt_dlp
            ydl_opts = {
                "quiet":           True,
                "no_warnings":     True,
                "extract_flat":    True,
                "default_search":  "ytsearch",
                "ffmpeg_location": self._ffmpeg_dir(),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            results = []
            for entry in (info or {}).get("entries", []):
                if not entry:
                    continue
                vid_id = entry.get("id", "")
                results.append({
                    "id":        vid_id,
                    "title":     entry.get("title", ""),
                    "channel":   entry.get("uploader", "") or entry.get("channel", ""),
                    "duration":  entry.get("duration") or 0,
                    "thumbnail": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else "",
                })
            return results
        except ImportError:
            return []
        except Exception:
            return []

    def ytdlp_available(self):
        try:
            import yt_dlp
            return True
        except ImportError:
            # Clear stale cache in case it was just installed
            import importlib, sys
            importlib.invalidate_caches()
            sys.modules.pop("yt_dlp", None)
            try:
                import yt_dlp
                return True
            except ImportError:
                return False



# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
def _focused_on_entry(root):
    """Return True when a text-input widget has keyboard focus."""
    try:
        return isinstance(root.focus_get(), (tk.Entry, tk.Text))
    except Exception:
        return False

# ─────────────────────────────────────────
#  TRON BOOT SEQUENCE
# ─────────────────────────────────────────
class TronBoot:
    """
    Fullscreen boot sequence synced to boot.mp3 timestamps:
      0:01 — login prompt appears
      0:03 — credentials typed
      0:07 — ACCESS GRANTED flash
      0:08-0:15 — logo fades in, holds, fades out → player launches
    Place boot.mp3 in the same folder as the exe or script.
    """
    CHAR_DELAY = 22   # ms per character
    CURSOR     = "█"

    def __init__(self, root, on_done, track_count=0):
        self.root     = root
        self.on_done  = on_done
        self.n_tracks = track_count
        self._jobs    = []
        self._done    = False

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.sw, self.sh = sw, sh

        # Fullscreen black window
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{sw}x{sh}+0+0")
        self.win.configure(bg="#000000")

        self.cv = tk.Canvas(self.win, bg="#000000", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        # Subtle CRT scanlines
        for yy in range(0, sh, 4):
            self.cv.create_line(0, yy, sw, yy, fill="#060606", width=1)

        # Terminal area — centered
        self.term_x = sw // 2 - 300
        self.term_y = sh // 2 - 120
        self._line_items      = []
        self._cursor_blink_on = True
        self._cursor_item     = self.cv.create_text(
            self.term_x, self.term_y, text=self.CURSOR,
            font=("Courier New", 11), fill="#e8e8e8", anchor="nw")

        # Logo item (hidden until phase 3)
        self._logo_item = self.cv.create_text(
            sw // 2, sh // 2,
            text="O T E R N O S", font=("Courier New", 48, "bold"),
            fill="#000000", anchor="center")
        self._sub_item = self.cv.create_text(
            sw // 2, sh // 2 + 56,
            text="P  L  A  Y  E  R     v 1 . 1",
            font=("Courier New", 14), fill="#000000", anchor="center")

        self._blink()

        # Play audio
        self._play_boot_audio()

        # Schedule all phases synced to audio
        self._schedule()

    # ── audio ──────────────────────────────
    def _play_boot_audio(self):
        try:
            import sys as _sys, os as _os, pygame as _pg
            # Init mixer independently of the main player
            if not _pg.get_init():
                _pg.init()
            if not _pg.mixer.get_init():
                _pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            candidates = []
            if getattr(_sys, "frozen", False):
                candidates.append(_os.path.dirname(_sys.executable))
            try:
                candidates.append(_os.path.dirname(_os.path.abspath(__file__)))
            except Exception:
                pass
            candidates.append(str(Path.home() / "Downloads"))
            candidates.append(str(Path.home() / "Downloads" / "dist"))
            print("[BOOT] searching for boot.mp3 in:", candidates)
            for d in candidates:
                p = _os.path.join(d, "boot.mp3")
                print(f"[BOOT] checking: {p}  exists={_os.path.exists(p)}")
                if _os.path.exists(p):
                    _pg.mixer.music.load(p)
                    _pg.mixer.music.set_volume(1.0)
                    _pg.mixer.music.play()
                    print("[BOOT] playing:", p)
                    return
            print("[BOOT] boot.mp3 not found in any candidate path")
        except Exception as e:
            print(f"[BOOT] audio error: {e}")

    # ── cursor blink ───────────────────────
    def _blink(self):
        if self._done: return
        col = "#e8e8e8" if self._cursor_blink_on else "#000000"
        try: self.cv.itemconfig(self._cursor_item, fill=col)
        except: return
        self._cursor_blink_on = not self._cursor_blink_on
        self._jobs.append(self.root.after(500, self._blink))

    # ── main schedule ──────────────────────
    def _schedule(self):
        # ── Phase 1: 0:01 — login prompt appears ──
        self._at(1000, lambda: self._show_login_prompt())

        # ── Phase 2: 0:03 — type credentials ──
        self._at(3000, lambda: self._type_credentials())

        # ── Phase 3: 0:07 — ACCESS GRANTED flash ──
        self._at(7000, lambda: self._access_granted())

        # ── Phase 4: 0:08 — clear terminal, logo fades in ──
        self._at(8000, lambda: self._show_logo())

        # ── Phase 5: 0:13 — logo fades out ──
        self._at(13000, lambda: self._fade_logo_out())

        # ── Phase 6: 0:15 — launch player ──
        self._at(15000, lambda: self._finish())

    def _at(self, ms, fn):
        self._jobs.append(self.root.after(ms, fn))

    # ── Phase 1: login prompt ──────────────
    def _show_login_prompt(self):
        if self._done: return
        lines = [
            "ENCOM OS 12  //  SECURE TERMINAL",
            "━" * 44,
            "",
            "AUTHENTICATION REQUIRED",
            "",
        ]
        for i, line in enumerate(lines):
            self._at(i * 120, lambda l=line: self._add_line(l, "#888888" if "━" in l else "#c8c8c8"))
        # After lines appear, show login fields
        self._at(len(lines) * 120 + 100, self._show_login_fields)

    def _show_login_fields(self):
        if self._done: return
        self._add_line("  LOGIN    :  _", "#e8e8e8")
        self._add_line("  PASSWORD :  _", "#e8e8e8")

    # ── Phase 2: type credentials ──────────
    def _type_credentials(self):
        if self._done: return
        # Find and update login/password lines
        items = self._line_items
        login_item    = items[-2] if len(items) >= 2 else None
        password_item = items[-1] if len(items) >= 1 else None
        import os as _os
        _uname = _os.environ.get("USERNAME", _os.environ.get("USER", "USER")).upper()
        login_text    = f"  LOGIN    :  {_uname}"
        password_text = "  PASSWORD :  ••••••••••"
        if login_item:
            self._retype(login_item, "  LOGIN    :  ", login_text, 0)
        if password_item:
            self._at(800, lambda: self._retype(password_item,
                "  PASSWORD :  ", password_text, 0))

    def _retype(self, item, prefix, full_text, i):
        if self._done: return
        try: self.cv.itemconfig(item, text=full_text[:len(prefix)+i])
        except: return
        if len(prefix) + i < len(full_text):
            self._jobs.append(self.root.after(self.CHAR_DELAY,
                lambda: self._retype(item, prefix, full_text, i+1)))

    # ── Phase 3: ACCESS GRANTED ────────────
    def _access_granted(self):
        if self._done: return
        self._add_line("", "#000000")
        self._add_line("  ✓  IDENTITY VERIFIED", "#e8e8e8")
        self._add_line("", "#000000")
        ag = self._add_line("  ██  ACCESS GRANTED  ██", "#ffffff",
                            font=("Courier New", 13, "bold"))
        # Flash it
        self._flash_item(ag, 0)

    def _flash_item(self, item, step):
        if self._done or step > 5: return
        col = "#ffffff" if step % 2 == 0 else "#333333"
        try: self.cv.itemconfig(item, fill=col)
        except: return
        self._jobs.append(self.root.after(180, lambda: self._flash_item(item, step+1)))

    # ── Phase 4: show logo ─────────────────
    def _show_logo(self):
        if self._done: return
        # Hide terminal
        for item in self._line_items:
            try: self.cv.itemconfig(item, fill="#000000")
            except: pass
        try: self.cv.itemconfig(self._cursor_item, fill="#000000")
        except: pass
        # Fade logo in
        self._fade_logo_in(0)

    def _fade_logo_in(self, step):
        if self._done: return
        steps = 30
        v = int((step / steps) * 232)
        v2 = int((step / steps) * 100)
        col  = f"#{v:02x}{v:02x}{v:02x}"
        col2 = f"#{v2:02x}{v2:02x}{v2:02x}"
        try:
            self.cv.itemconfig(self._logo_item, fill=col)
            self.cv.itemconfig(self._sub_item,  fill=col2)
        except: return
        if step < steps:
            self._jobs.append(self.root.after(16, lambda: self._fade_logo_in(step+1)))

    # ── Phase 5: fade logo out ─────────────
    def _fade_logo_out(self, step=0):
        if self._done: return
        steps = 30
        v  = int((1 - step/steps) * 232)
        v2 = int((1 - step/steps) * 100)
        col  = f"#{v:02x}{v:02x}{v:02x}"
        col2 = f"#{v2:02x}{v2:02x}{v2:02x}"
        try:
            self.cv.itemconfig(self._logo_item, fill=col)
            self.cv.itemconfig(self._sub_item,  fill=col2)
        except: return
        if step < steps:
            self._jobs.append(self.root.after(16, lambda: self._fade_logo_out(step+1)))

    # ── helpers ────────────────────────────
    def _add_line(self, text, color="#c8c8c8", font=("Courier New", 11)):
        if self._done: return None
        y = self.term_y + len(self._line_items) * 18
        item = self.cv.create_text(self.term_x, y, text=text,
            font=font, fill=color, anchor="nw")
        self._line_items.append(item)
        self.cv.coords(self._cursor_item,
                       self.term_x, self.term_y + len(self._line_items) * 18)
        return item

    # ── finish ─────────────────────────────
    def _finish(self):
        if self._done: return
        self._done = True
        for j in self._jobs:
            try: self.root.after_cancel(j)
            except: pass
        try:
            import pygame as _pg
            _pg.mixer.music.stop()
        except: pass
        try: self.win.destroy()
        except: pass
        self.on_done()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()   # hide main window during boot

    def _launch():
        root.deiconify()
        app = VoidPlayer(root)

        def _guard(fn):
            def _handler(e):
                if not _focused_on_entry(root):
                    fn()
            return _handler

        root.bind("<MouseWheel>", app._route_scroll)
        root.bind("<space>", _guard(app._toggle_play))
        root.bind("<Right>", _guard(app._next))
        root.bind("<Left>",  _guard(app._prev))
        root.bind("<Up>",    _guard(lambda: (app.engine.set_volume(app.engine.volume+0.05), app._upd_vol())))
        root.bind("<Down>",  _guard(lambda: (app.engine.set_volume(app.engine.volume-0.05), app._upd_vol())))
        root.bind("<Control-Right>", _guard(lambda: app._seek_relative(+10)))
        root.bind("<Control-Left>",  _guard(lambda: app._seek_relative(-10)))
        root.bind("<Control-p>",     _guard(app._toggle_play))

    # Count library tracks for the boot display
    _n_tracks = 0
    try:
        import json as _json
        _d = _json.loads(Path.home().joinpath(".voidplayer.json").read_text())
        _n_tracks = len(_d.get("library", []))
    except Exception:
        pass

    TronBoot(root, on_done=_launch, track_count=_n_tracks)
    root.mainloop()
