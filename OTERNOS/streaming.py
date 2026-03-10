"""
streaming.py
─────────────────────────────────────────────────────────────────────────────
OTERNOS PLAYER  —  Streaming service integrations.
  • SpotifyAuth   — OAuth2 PKCE auth + token management
  • SpotifyAPI    — Spotify Web API wrapper
  • SoundCloudAPI — SoundCloud v2 API wrapper
  • YouTubeAPI    — yt-dlp based YouTube search + stream
─────────────────────────────────────────────────────────────────────────────
"""

import os
import json
import base64
import hashlib
import threading
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler


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
SC_CLIENT_ID  = "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX"   # public fallback client ID
SC_TOKEN_FILE = str(Path.home() / ".oternos_soundcloud.json")

class SoundCloudAPI:
    BASE   = "https://api-v2.soundcloud.com"

    def __init__(self):
        self.client_id   = SC_CLIENT_ID
        self.oauth_token = None
        self._load_token()

    def _load_token(self):
        try:
            d = json.loads(Path(SC_TOKEN_FILE).read_text())
            self.oauth_token = d.get("oauth_token")
        except:
            pass

    def _save_token(self):
        try:
            Path(SC_TOKEN_FILE).write_text(
                json.dumps({"oauth_token": self.oauth_token}))
        except:
            pass

    def _headers(self):
        h = {"Accept": "application/json; charset=utf-8"}
        if self.oauth_token:
            h["Authorization"] = f"OAuth {self.oauth_token}"
        return h

    def _get(self, endpoint, params=None):
        p = dict(params or {})
        p["client_id"] = self.client_id
        url = f"{self.BASE}{endpoint}?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except:
            return None

    def search(self, q, limit=40):
        data = self._get("/search/tracks", {"q": q, "limit": limit})
        return (data or {}).get("collection", [])

    def likes(self, limit=100):
        """Fetch the authenticated user's liked tracks."""
        if not self.oauth_token:
            return []
        # First get own user ID
        req = urllib.request.Request(
            f"https://api.soundcloud.com/me?client_id={self.client_id}",
            headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                me = json.loads(r.read())
            uid = me.get("id")
        except:
            return []
        data = self._get(f"/users/{uid}/likes", {"limit": limit})
        items = (data or {}).get("collection", [])
        # Each item may be {"track": {...}} or the track directly
        tracks = []
        for it in items:
            t = it.get("track") or (it if it.get("kind") == "track" else None)
            if t:
                tracks.append(t)
        return tracks

    def get_stream_url(self, track):
        """Resolve the best streamable URL for a track."""
        # Try progressive streams first (direct MP3)
        media = (track.get("media") or {}).get("transcodings", [])
        for tc in media:
            fmt = (tc.get("format") or {})
            if fmt.get("protocol") == "progressive":
                url = tc.get("url")
                if url:
                    resolved = self._get_stream(url)
                    if resolved:
                        return resolved
        # Fallback: stream_url field
        su = track.get("stream_url")
        if su:
            return self._get_stream(su)
        return None

    def _get_stream(self, url):
        full = f"{url}?client_id={self.client_id}"
        if self.oauth_token:
            full += f"&oauth_token={self.oauth_token}"
        req = urllib.request.Request(full, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read())
            return d.get("url")
        except:
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
