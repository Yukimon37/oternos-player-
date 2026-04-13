"""
streaming.py — OTERNOS PLAYER
SpotifyAuth, SpotifyAPI, SoundCloudAPI, YouTubeAPI.
"""

import tkinter as tk
import sys
import os
import json
import time
import threading
import hashlib
import base64
import urllib.request
import urllib.parse
import urllib.error
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

if getattr(sys, "frozen", False):
    pass
else:
    pass

# ─────────────────────────────────────────
#  SOUND ENGINE — disabled
# ─────────────────────────────────────────
import os as _os

_SND = {}

# SSL context
try:
    _SSL = ssl.create_default_context()
except Exception:
    _SSL = ssl._create_unverified_context()


# ─────────────────────────────────────────
#  SPOTIFY CLIENT
# ─────────────────────────────────────────
# Credentials are read from environment variables.
# Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your environment,
# or create a .env file and load it before running.
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES = (
    "user-read-playback-state user-modify-playback-state "
    "user-read-currently-playing playlist-read-private "
    "playlist-read-collaborative user-library-read user-top-read"
)


class SpotifyAuth:
    TOKEN_FILE = str(Path.home() / ".oternos_spotify.json")

    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0
        self.rate_limited_until = 0
        self._code_verifier = None
        self._auth_code = None
        self._server = None
        self._load_token()

    def _load_token(self):
        try:
            d = json.loads(Path(self.TOKEN_FILE).read_text())
            self.access_token = d.get("access_token")
            self.refresh_token = d.get("refresh_token")
            self.expires_at = d.get("expires_at", 0)
            self.rate_limited_until = d.get("rate_limited_until", 0)
        except Exception:
            pass

    def _save_token(self):
        try:
            Path(self.TOKEN_FILE).write_text(
                json.dumps(
                    {
                        "access_token": self.access_token,
                        "refresh_token": self.refresh_token,
                        "expires_at": self.expires_at,
                        "rate_limited_until": getattr(self, "rate_limited_until", 0),
                    }
                )
            )
        except Exception:
            pass

    def is_authenticated(self):
        return bool(self.access_token)

    def token_valid(self):
        return self.access_token and time.time() < self.expires_at - 30

    def reload_from_disk(self):
        """Re-read token file — picks up manual edits."""
        self._load_token()

    def get_auth_url(self):
        """Generate PKCE auth URL."""
        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        self._code_verifier = verifier
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        params = urllib.parse.urlencode(
            {
                "client_id": SPOTIFY_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": SPOTIFY_REDIRECT_URI,
                "scope": SPOTIFY_SCOPES,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
            }
        )
        return f"https://accounts.spotify.com/authorize?{params}"

    def start_callback_server(self, on_code):
        """Start local HTTP server to catch OAuth callback."""
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                if "code" in qs:
                    outer._auth_code = qs["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body style='background:#000;color:#fff;"
                        b"font-family:monospace;padding:40px'>"
                        b"<h2>OTERNOS // SPOTIFY AUTH OK</h2>"
                        b"<p>You can close this window.</p></body></html>"
                    )
                    # Shut down server after a short delay so response is sent first
                    threading.Thread(
                        target=lambda: (time.sleep(0.5), self.server.shutdown()),
                        daemon=True,
                    ).start()
                    on_code(qs["code"][0])
                else:
                    # Ignore favicon and other stray requests — keep listening
                    self.send_response(204)
                    self.end_headers()

            def log_message(self, *a):
                pass

        self._server = HTTPServer(("127.0.0.1", 8888), Handler)
        # serve_forever handles multiple requests (favicon, etc.) until shutdown()
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

    def exchange_code(self, code, callback=None):
        """Exchange auth code for tokens using PKCE."""

        def _do():
            try:
                data = urllib.parse.urlencode(
                    {
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": SPOTIFY_REDIRECT_URI,
                        "client_id": SPOTIFY_CLIENT_ID,
                        "code_verifier": self._code_verifier,
                    }
                ).encode()
                req = urllib.request.Request(
                    "https://accounts.spotify.com/api/token",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, context=_SSL) as r:
                    d = json.loads(r.read())
                self.access_token = d["access_token"]
                self.refresh_token = d.get("refresh_token")
                self.expires_at = time.time() + d.get("expires_in", 3600)
                self._save_token()
                if callback:
                    callback(True)
            except Exception as e:
                if callback:
                    callback(False, str(e))

        threading.Thread(target=_do, daemon=True).start()

    def refresh(self, callback=None):
        """Refresh access token via PKCE (no client secret needed)."""
        if not self.refresh_token:
            return

        def _do():
            try:
                data = urllib.parse.urlencode(
                    {
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                        "client_id": SPOTIFY_CLIENT_ID,
                    }
                ).encode()
                req = urllib.request.Request(
                    "https://accounts.spotify.com/api/token",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=8, context=_SSL) as r:
                    d = json.loads(r.read())
                self.access_token = d["access_token"]
                self.expires_at = time.time() + d.get("expires_in", 3600)
                if "refresh_token" in d:
                    self.refresh_token = d["refresh_token"]
                self._save_token()
                if callback:
                    callback(True)
            except Exception as e:
                if callback:
                    callback(False, str(e))

        threading.Thread(target=_do, daemon=True).start()


class SpotifyAPI:
    BASE = "https://api.spotify.com/v1"

    def __init__(self, auth: SpotifyAuth):
        self.auth = auth
        self._last_error = ""

    def _is_rate_limited(self):
        return time.time() < self.auth.rate_limited_until

    def _set_rate_limit(self, retry_after):
        self.auth.rate_limited_until = time.time() + retry_after + 2
        self.auth._save_token()
        print(
            f"[SPOTIFY API] Rate limited — backing off {retry_after}s ({retry_after // 60}m)"
        )

    def _get(self, endpoint, params=None):
        if self._is_rate_limited():
            remaining = int(self.auth.rate_limited_until - time.time())
            self._last_error = f"Rate limited — retry in {remaining}s"
            return None
        if not self.auth.token_valid():
            if self.auth.refresh_token:
                try:
                    data = urllib.parse.urlencode(
                        {
                            "grant_type": "refresh_token",
                            "refresh_token": self.auth.refresh_token,
                            "client_id": SPOTIFY_CLIENT_ID,
                        }
                    ).encode()
                    req = urllib.request.Request(
                        "https://accounts.spotify.com/api/token",
                        data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    with urllib.request.urlopen(req, timeout=8, context=_SSL) as r:
                        d = json.loads(r.read())
                    self.auth.access_token = d["access_token"]
                    self.auth.expires_at = time.time() + d.get("expires_in", 3600)
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
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.auth.access_token}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10, context=_SSL) as r:
                raw = r.read()
                if not raw:  # 204 No Content
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            self._last_error = f"HTTP {e.code}: {body}"
            print(f"[SPOTIFY API] HTTP {e.code} on {endpoint}: {body}")
            if e.code == 429:
                retry_after = min(int(e.headers.get("Retry-After", 30)), 86400)
                self._set_rate_limit(retry_after)
            elif e.code == 401:
                self.auth.access_token = None
            return None
        except Exception as e:
            self._last_error = f"request error: {e}"
            print(f"[SPOTIFY API] error on {endpoint}: {e}")
            return None

    def _post(self, endpoint, body=None):
        if not self.auth.token_valid():
            return None
        url = f"{self.BASE}{endpoint}"
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.auth.access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8, context=_SSL) as r:
                return r.status
        except Exception:
            return None

    def _put(self, endpoint, body=None):
        if not self.auth.token_valid():
            return None
        url = f"{self.BASE}{endpoint}"
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            method="PUT",
            headers={
                "Authorization": f"Bearer {self.auth.access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8, context=_SSL) as r:
                return r.status
        except Exception:
            return None

    def me(self):
        return self._get("/me")

    def playlists(self, limit=50):
        return self._get("/me/playlists", {"limit": limit})

    def playlist_tracks(self, playlist_id, limit=50, offset=0):
        return self._get(
            f"/playlists/{playlist_id}/tracks", {"limit": limit, "offset": offset}
        )

    def liked_songs(self, limit=50, offset=0):
        return self._get("/me/tracks", {"limit": limit, "offset": offset})

    def search(self, q, limit=50):
        # Single request — multi-page hammering causes long rate bans
        return self._get("/search", {"q": q, "type": "track", "limit": limit})

    def now_playing(self):
        return self._get("/me/player/currently-playing")

    def play(self, uris=None, context_uri=None, offset=None):
        body = {}
        if uris:
            body["uris"] = uris
        if context_uri:
            body["context_uri"] = context_uri
        if offset:
            body["offset"] = offset
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

    def play_on(self, device_id, uris=None, offset=None, context_uri=None):
        body = {"device_id": device_id}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = uris[:100]
        if offset:
            body["offset"] = offset
        return self._put(f"/me/player/play?device_id={device_id}", body)

    def _put_full(self, url, body=None):
        if not self.auth.token_valid():
            return None, 0
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            method="PUT",
            headers={
                "Authorization": f"Bearer {self.auth.access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8, context=_SSL) as r:
                return None, r.status
        except urllib.error.HTTPError as e:
            try:
                body_err = e.read().decode()
            except Exception:
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
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=12, context=_SSL) as r:
            html = r.read().decode("utf-8", errors="replace")

        # 2. Find all versioned JS bundle URLs
        scripts = _re.findall(
            r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html
        )

        # 3. Search each bundle (newest first) for client_id
        for script_url in reversed(scripts):
            try:
                jreq = urllib.request.Request(
                    script_url, headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(jreq, timeout=10, context=_SSL) as jr:
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
    BASE = "https://api-v2.soundcloud.com"
    _cached_cid = None  # class-level cache — fetched once per session

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
                json.dumps({"oauth_token": self.oauth_token})
            )
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
            "Accept": "application/json; charset=utf-8",
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
            with urllib.request.urlopen(req, timeout=10, context=_SSL) as r:
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
            fmt = tc.get("format") or {}
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
        url = f"{self.BASE}/resolve?" + urllib.parse.urlencode(
            {"url": permalink_url, "client_id": self.client_id}
        )
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10, context=_SSL) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def _resolve_stream(self, transcoding_url):
        """Hit a transcoding URL to get the actual CDN stream URL."""
        if not self.client_id:
            return None
        full = (
            transcoding_url
            + "?"
            + urllib.parse.urlencode({"client_id": self.client_id})
        )
        if self.oauth_token:
            full += f"&oauth_token={self.oauth_token}"
        req = urllib.request.Request(full, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=8, context=_SSL) as r:
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
        import sys as _sys

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
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "default_search": "ytsearch",
                "ffmpeg_location": self._ffmpeg_dir(),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"ytsearch{max_results}:{query}", download=False
                )
            results = []
            for entry in (info or {}).get("entries", []):
                if not entry:
                    continue
                vid_id = entry.get("id", "")
                results.append(
                    {
                        "id": vid_id,
                        "title": entry.get("title", ""),
                        "channel": entry.get("uploader", "")
                        or entry.get("channel", ""),
                        "duration": entry.get("duration") or 0,
                        "thumbnail": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"
                        if vid_id
                        else "",
                    }
                )
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
            import importlib
            import sys

            importlib.invalidate_caches()
            sys.modules.pop("yt_dlp", None)
            try:
                import yt_dlp

                return True
            except ImportError:
                return False


# ─────────────────────────────────────────
#  DEEZER CLIENT  (no auth — 30s previews free)
# ─────────────────────────────────────────
class DeezerAPI:
    BASE = "https://api.deezer.com"

    def _get(self, endpoint, params=None):
        url = f"{self.BASE}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10, context=_SSL) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def search(self, q, limit=50):
        """Search tracks. Each result has a preview (30s MP3 URL) field."""
        data = self._get("/search", {"q": q, "limit": limit})
        return (data or {}).get("data", [])

    def chart(self, limit=50):
        """Global Deezer top chart tracks."""
        data = self._get("/chart/0/tracks", {"limit": limit})
        return (data or {}).get("data", [])

    def artist_top(self, artist_id, limit=20):
        data = self._get(f"/artist/{artist_id}/top", {"limit": limit})
        return (data or {}).get("data", [])


# ─────────────────────────────────────────
#  INTERNET ARCHIVE CLIENT
# ─────────────────────────────────────────
class InternetArchiveAPI:
    SEARCH  = "https://archive.org/advancedsearch.php"
    DETAILS = "https://archive.org/metadata"
    AUDIO_EXT = {".mp3", ".ogg", ".flac", ".wav", ".m4a", ".opus"}

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=12, context=_SSL) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def search(self, q, limit=40):
        """Search audio items. Returns list of {identifier, title, creator, year}."""
        params = urllib.parse.urlencode({
            "q":     f'({q}) AND mediatype:(audio)',
            "fl[]":  "identifier,title,creator,year,description",
            "rows":  limit,
            "output":"json",
            "page":  1,
            "sort[]":"downloads desc",
        })
        data = self._get(f"{self.SEARCH}?{params}")
        return (data or {}).get("response", {}).get("docs", [])

    def get_audio_files(self, identifier):
        """Return audio file list for an item, MP3s first."""
        data = self._get(f"{self.DETAILS}/{identifier}")
        if not data:
            return []
        files = data.get("files", [])
        audio = [f for f in files
                 if Path(f.get("name", "")).suffix.lower() in self.AUDIO_EXT]
        audio.sort(key=lambda f: (
            0 if f.get("name", "").lower().endswith(".mp3") else 1,
            f.get("name", ""),
        ))
        return audio

    def stream_url(self, identifier, filename):
        return (
            f"https://archive.org/download/{urllib.parse.quote(identifier, safe='')}/"
            + urllib.parse.quote(filename, safe="")
        )


# ─────────────────────────────────────────
#  BANDCAMP CLIENT  (scraping, no key needed)
# ─────────────────────────────────────────
class BandcampAPI:
    _HDR = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def _fetch(self, url):
        req = urllib.request.Request(url, headers=self._HDR)
        try:
            with urllib.request.urlopen(req, timeout=12, context=_SSL) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def search(self, q, limit=30):
        """Search Bandcamp for tracks. Returns list of {title, artist, url, art, album}."""
        import re as _re
        import html as _html
        src = self._fetch(
            f"https://bandcamp.com/search?q={urllib.parse.quote(q)}&item_type=t"
        )
        results = []
        for item in _re.findall(
            r'<li[^>]+class="[^"]*searchresult[^"]*"[^>]*>(.*?)</li>',
            src, _re.DOTALL
        )[:limit]:
            url_m = _re.search(
                r'<a[^>]+href="(https://[^"?#]*bandcamp\.com/track/[^"?#]+)', item
            )
            if not url_m:
                continue
            track_url = url_m.group(1)
            title_m  = _re.search(r'class="heading"[^>]*>.*?<a[^>]*>(.*?)</a>', item, _re.DOTALL)
            title    = _html.unescape(_re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""
            artist_m = _re.search(r'class="subhead"[^>]*>(.*?)</div>', item, _re.DOTALL)
            artist   = _html.unescape(_re.sub(r"<[^>]+>", "", artist_m.group(1))).strip() if artist_m else ""
            if artist.lower().startswith("by "):
                artist = artist[3:]
            _re.search(r'class="itemtype"[^>]*>.*?TRACK.*?</.*?class="result-info".*?class="subhead"[^>]*>(.*?)</div>', item, _re.DOTALL)
            art_m    = _re.search(r'<img[^>]+src="([^"]+)"', item)
            art      = art_m.group(1) if art_m else ""
            if title:
                results.append({
                    "title": title, "artist": artist,
                    "url": track_url, "art": art, "album": "",
                })
        return results

    def get_stream_url(self, track_url):
        """Fetch track page and extract mp3-128 preview stream URL."""
        import re as _re
        import html as _html
        src = self._fetch(track_url)
        if not src:
            return None, None

        # Try data-tralbum attr first (older embed style)
        m = _re.search(r'data-tralbum="([^"]+)"', src)
        if m:
            try:
                data   = json.loads(_html.unescape(m.group(1)))
                url    = self._pick_stream(data)
                title  = (data.get("trackinfo") or [{}])[0].get("title", "")
                artist = data.get("artist", "")
                return url, {"title": title, "artist": artist}
            except Exception:
                pass

        # Newer pages embed JSON in a <script> block
        for pat in (
            r'trackinfo"\s*:\s*(\[.*?\])\s*[,}]',
            r'"trackinfo"\s*:\s*(\[.+?\])',
        ):
            m = _re.search(pat, src, _re.DOTALL)
            if m:
                try:
                    tracks = json.loads(m.group(1))
                    f      = (tracks[0] if tracks else {}).get("file") or {}
                    url    = f.get("mp3-128") or f.get("mp3-v0")
                    title  = (tracks[0] if tracks else {}).get("title", "")
                    # artist from page title
                    at_m   = _re.search(r'"artist"\s*:\s*"([^"]+)"', src)
                    artist = _html.unescape(at_m.group(1)) if at_m else ""
                    if url:
                        return url, {"title": title, "artist": artist}
                except Exception:
                    pass
        return None, None

    @staticmethod
    def _pick_stream(data):
        tracks = data.get("trackinfo", [])
        if not tracks:
            return None
        f = (tracks[0] or {}).get("file") or {}
        return f.get("mp3-128") or f.get("mp3-v0")


# ─────────────────────────────────────────
#  TRON BOOT SEQUENCE
# ─────────────────────────────────────────
