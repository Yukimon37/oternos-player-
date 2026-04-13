"""
netstream.py — OTERNOS PLAYER
Local Network Streaming — serve your library to other devices on your LAN,
or connect to another OTERNOS instance and listen along.

Features:
  • NetStreamServer   — HTTP audio server + metadata broadcast (mDNS-style announce)
  • NetStreamClient   — auto-discovers and connects to LAN servers
  • NetStreamView     — tkinter UI panel (HOST tab + LISTEN tab)

Protocol:
  GET /stream          → 206-compatible infinite chunked PCM/MP3 stream
  GET /meta            → JSON {title, artist, album, bpm, position_s, duration_s}
  GET /library         → JSON list of {title, artist, duration}
  GET /cover           → current album art bytes (JPEG, or 1×1 placeholder)
  POST /control        → JSON {action: "play"|"pause"|"skip"|"seek", value}
  GET /announce        → server identity {name, version, tracks}

Discovery:
  UDP broadcast on port 45678, payload JSON {"oternos":1, "host": …, "port": …}
  Clients listen and add servers automatically.

Integration: see INTEGRATION NOTES at bottom.
"""

from __future__ import annotations

import sys
import os
import io
import json
import math
import socket
import struct
import threading
import time
import random
import hashlib
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Callable, Dict, List

# ── package imports ───────────────────────────────────────────────────────────
try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore

if getattr(sys, "frozen", False):
    from oternos.constants import C, FM, FMS, FML, FMX
    from oternos.animation import ColorAnim
    from oternos.diagnostics import log_exception, get_logger
else:
    try:
        from .constants import C, FM, FMS, FML, FMX
        from .animation import ColorAnim
        from .diagnostics import log_exception, get_logger
    except ImportError:
        C = {"bg": "#050505", "panel": "#0c0c0c", "border": "#1f1f1f",
             "border2": "#2e2e2e", "white": "#e8e8e8", "white2": "#9a9a9a",
             "white3": "#424242", "glow": "#ffffff", "select": "#1e1e1e",
             "select2": "#242424", "red": "#cc2222"}
        FM = ("Courier New", 9)
        FMS = ("Courier New", 8)
        FML = ("Courier New", 10, "bold")
        FMX = ("Courier New", 13, "bold")
        class ColorAnim:
            @classmethod
            def run(cls, *a, **kw): pass
        def log_exception(ctx, exc): pass
        def get_logger(): import logging; return logging.getLogger("netstream")

# ── Optional: pygame for re-encoding chunks ──────────────────────────────────
try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False

# ── Optional: mutagen for metadata ───────────────────────────────────────────
try:
    from mutagen import File as _MutagenFile
    _MUTAGEN_OK = True
except ImportError:
    _MUTAGEN_OK = False

_DISCOVERY_PORT = 45678
_DEFAULT_HTTP_PORT = 45679
_ANNOUNCE_INTERVAL = 8.0        # seconds between UDP announces
_META_INTERVAL = 1.0            # seconds between /meta poll (clients)
_CHUNK_SIZE = 64 * 1024         # 64 KB chunks


# ─────────────────────────────────────────────────────────────────────────────
#  STREAM SERVER
# ─────────────────────────────────────────────────────────────────────────────
class NetStreamServer:
    """
    HTTP server that:
      • Serves the currently-playing audio file as a seekable stream
      • Broadcasts track metadata as JSON
      • Accepts remote control commands (if player allows it)
      • Announces itself via UDP so clients find it automatically

    All heavy operations are threaded; the server never blocks the Tk mainloop.
    """

    def __init__(self, player, port: int = _DEFAULT_HTTP_PORT,
                 name: str = "", allow_control: bool = False):
        self.player       = player
        self.port         = port
        self.name         = name or socket.gethostname()
        self.allow_control = allow_control
        self._running     = False
        self._http        = None
        self._http_thread: Optional[threading.Thread] = None
        self._announce_thread: Optional[threading.Thread] = None
        self._clients: List[str] = []       # connected client IPs
        self._lock = threading.Lock()
        self._listener_count = 0
        self._on_status: Optional[Callable[[str], None]] = None
        self._logger = get_logger()

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def start(self) -> bool:
        if self._running:
            return True
        try:
            server_ref = self

            class _Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    try:
                        server_ref._handle_get(self)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    except Exception as e:
                        log_exception("netstream_handler", e)

                def do_POST(self):
                    try:
                        server_ref._handle_post(self)
                    except Exception as e:
                        log_exception("netstream_post", e)

                def log_message(self, *a):
                    pass

            self._http = HTTPServer(("0.0.0.0", self.port), _Handler)
            self._http.timeout = 1.0
            self._running = True

            self._http_thread = threading.Thread(
                target=self._serve_loop, daemon=True, name="netstream-http"
            )
            self._http_thread.start()

            self._announce_thread = threading.Thread(
                target=self._announce_loop, daemon=True, name="netstream-udp"
            )
            self._announce_thread.start()

            ip = self._local_ip()
            msg = f"[NET] Server live on {ip}:{self.port}"
            self._notify(msg)
            return True
        except OSError as e:
            self._notify(f"[NET] Port {self.port} unavailable — {e}")
            log_exception("netstream_start", e)
            return False

    def stop(self):
        self._running = False
        http = self._http
        self._http = None
        if http:
            # Shut down on a background thread so we never block the Tk mainloop.
            # shutdown() waits for handle_request() to finish its current 1s timeout —
            # doing this off-thread prevents the UI from freezing or deadlocking.
            def _do_shutdown(srv=http):
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception:
                    pass
            threading.Thread(target=_do_shutdown, daemon=True).start()
        self._notify("[NET] Server stopped.")

    def _serve_loop(self):
        while self._running:
            http = self._http
            if http is None:
                break
            try:
                http.handle_request()
            except Exception:
                pass

    # ── UDP announce ──────────────────────────────────────────────────────────
    def _announce_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)
        while self._running:
            try:
                payload = json.dumps({
                    "oternos": 1,
                    "host":    self._local_ip(),
                    "port":    self.port,
                    "name":    self.name,
                    "tracks":  len(getattr(self.player, "library", [])),
                }).encode()
                sock.sendto(payload, ("<broadcast>", _DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(_ANNOUNCE_INTERVAL)
        sock.close()

    # ── HTTP handlers ─────────────────────────────────────────────────────────
    def _handle_get(self, req: BaseHTTPRequestHandler):
        path = urllib.parse.urlparse(req.path).path.rstrip("/") or "/"

        if path == "/announce":
            self._send_json(req, self._get_announce())

        elif path == "/meta":
            self._send_json(req, self._get_meta())

        elif path == "/library":
            lib = [
                {"title": t.get("title","?"), "artist": t.get("artist",""),
                 "duration": t.get("duration", 0)}
                for t in getattr(self.player, "library", [])
            ]
            self._send_json(req, lib)

        elif path == "/cover":
            self._send_cover(req)

        elif path == "/stream":
            self._send_stream(req)

        else:
            req.send_response(404)
            req.end_headers()

    def _handle_post(self, req: BaseHTTPRequestHandler):
        if not self.allow_control:
            req.send_response(403)
            req.end_headers()
            return
        try:
            length = int(req.headers.get("Content-Length", 0))
            body   = json.loads(req.rfile.read(length)) if length else {}
        except Exception:
            body = {}

        action = body.get("action", "")
        value  = body.get("value")

        def _ui(fn):
            """Schedule fn on Tk main thread."""
            try:
                self.player.root.after(0, fn)
            except Exception:
                pass

        if action == "play":
            _ui(lambda: self.player._toggle_play()
                if not self.player.engine.is_playing else None)
        elif action == "pause":
            _ui(lambda: self.player._toggle_play()
                if self.player.engine.is_playing else None)
        elif action == "skip":
            _ui(self.player._next)
        elif action == "prev":
            _ui(self.player._prev)
        elif action == "seek" and value is not None:
            _ui(lambda: self.player.engine.seek(float(value)))

        self._send_json(req, {"ok": True})

    # ── response helpers ──────────────────────────────────────────────────────
    def _send_json(self, req, data):
        body = json.dumps(data).encode()
        req.send_response(200)
        req.send_header("Content-Type", "application/json")
        req.send_header("Content-Length", str(len(body)))
        req.send_header("Access-Control-Allow-Origin", "*")
        req.end_headers()
        req.wfile.write(body)

    def _send_stream(self, req: BaseHTTPRequestHandler):
        """Serve current audio file as byte range / chunked stream."""
        engine = self.player.engine
        path   = getattr(engine, "_path", None) or getattr(engine, "_current_play_path", None)
        if not path or not Path(path).exists():
            req.send_response(404)
            req.end_headers()
            return

        file_size = Path(path).stat().st_size
        range_hdr = req.headers.get("Range", "")
        start = 0
        end   = file_size - 1

        if range_hdr.startswith("bytes="):
            try:
                parts = range_hdr[6:].split("-")
                start = int(parts[0]) if parts[0] else 0
                end   = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            except Exception:
                pass

        length = end - start + 1
        ext    = Path(path).suffix.lower()
        ctype  = {
            ".mp3": "audio/mpeg", ".flac": "audio/flac", ".ogg": "audio/ogg",
            ".wav": "audio/wav",  ".m4a": "audio/mp4",  ".aac": "audio/aac",
        }.get(ext, "application/octet-stream")

        req.send_response(206 if range_hdr else 200)
        req.send_header("Content-Type",         ctype)
        req.send_header("Content-Length",        str(length))
        req.send_header("Content-Range",         f"bytes {start}-{end}/{file_size}")
        req.send_header("Accept-Ranges",         "bytes")
        req.send_header("Access-Control-Allow-Origin", "*")
        req.send_header("Cache-Control",         "no-cache")
        req.end_headers()

        client_ip = req.client_address[0]
        with self._lock:
            if client_ip not in self._clients:
                self._clients.append(client_ip)
                self._listener_count = len(self._clients)
                self._notify(f"[NET] +listener {client_ip}  (total: {self._listener_count})")

        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    req.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with self._lock:
                if client_ip in self._clients:
                    self._clients.remove(client_ip)
                    self._listener_count = len(self._clients)
                    self._notify(f"[NET] -listener {client_ip}  (total: {self._listener_count})")

    def _send_cover(self, req: BaseHTTPRequestHandler):
        """Send current album art as JPEG, or a 1×1 black placeholder."""
        art_bytes = self._get_cover_bytes()
        req.send_response(200)
        req.send_header("Content-Type", "image/jpeg")
        req.send_header("Content-Length", str(len(art_bytes)))
        req.send_header("Access-Control-Allow-Origin", "*")
        req.end_headers()
        req.wfile.write(art_bytes)

    # ── metadata helpers ──────────────────────────────────────────────────────
    def _get_meta(self) -> Dict:
        p = self.player
        try:
            title    = p.now_title.cget("text")
            artist   = p.now_artist.cget("text")
        except Exception:
            title = artist = ""
        try:
            pos = p.engine.get_position()
            dur = p.engine.duration
            playing = p.engine.is_playing
        except Exception:
            pos = dur = 0
            playing = False
        return {
            "title":      title,
            "artist":     artist,
            "position_s": round(pos, 2),
            "duration_s": round(dur, 2),
            "playing":    playing,
            "listeners":  self._listener_count,
        }

    def _get_announce(self) -> Dict:
        return {
            "name":    self.name,
            "version": "1.1",
            "tracks":  len(getattr(self.player, "library", [])),
            "host":    self._local_ip(),
            "port":    self.port,
        }

    def _get_cover_bytes(self) -> bytes:
        # Try to find cover from current track via mutagen
        try:
            engine = self.player.engine
            path = getattr(engine, "_path", None)
            if path and _MUTAGEN_OK:
                mf = _MutagenFile(path)
                if mf:
                    for tag_key in ("APIC:", "covr", "metadata_block_picture"):
                        val = mf.tags.get(tag_key) if mf.tags else None
                        if val:
                            data = val[0].data if hasattr(val[0], "data") else bytes(val[0])
                            return data
        except Exception:
            pass
        # 1×1 JPEG placeholder (minimal valid JPEG)
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'"
            b"9=82<.342\x1edL\x1b\xb9\xa3\x8d\xff\xd9"
        )

    def _local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _notify(self, msg: str):
        """Thread-safe status callback — always routes through Tk main thread."""
        if not self._on_status:
            return
        cb = self._on_status
        try:
            self.player.root.after(0, lambda m=msg: cb(m))
        except Exception:
            try:
                cb(msg)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  STREAM CLIENT  — discover + connect to LAN servers
# ─────────────────────────────────────────────────────────────────────────────
class NetStreamClient:
    """
    Listens for UDP broadcasts from OTERNOS servers and maintains a list.
    Connects to a chosen server and polls /meta for live track info.
    Uses VoidPlayer's existing AudioEngine to play the /stream URL.
    """

    def __init__(self, player):
        self.player = player
        self._servers: Dict[str, Dict] = {}   # host:port → info dict
        self._connected_server: Optional[str] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._meta_thread:   Optional[threading.Thread] = None
        self._active = False
        self._on_servers_changed: Optional[Callable] = None
        self._on_meta_update: Optional[Callable[[Dict], None]] = None
        self._on_status: Optional[Callable[[str], None]] = None
        self._current_meta: Dict = {}

    def start_discovery(self):
        if self._active:
            return
        self._active = True
        self._listen_thread = threading.Thread(
            target=self._discover_loop, daemon=True, name="netstream-discover"
        )
        self._listen_thread.start()

    def stop_discovery(self):
        self._active = False
        self._servers.clear()
        self._connected_server = None

    def _discover_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", _DISCOVERY_PORT))
        except OSError:
            self._notify("[NET] Discovery bind failed — already running?")
            return
        sock.settimeout(2.0)
        while self._active:
            try:
                data, addr = sock.recvfrom(4096)
                info = json.loads(data.decode())
                if info.get("oternos") == 1:
                    key = f"{info['host']}:{info['port']}"
                    info["_last_seen"] = time.time()
                    info["_addr"] = addr[0]
                    changed = key not in self._servers
                    self._servers[key] = info
                    # expire stale servers
                    stale = [k for k, v in self._servers.items()
                              if time.time() - v.get("_last_seen", 0) > 30]
                    for k in stale:
                        del self._servers[k]
                        changed = True
                    if changed and self._on_servers_changed:
                        self._on_servers_changed()
            except socket.timeout:
                # Expire stale
                stale = [k for k, v in self._servers.items()
                          if time.time() - v.get("_last_seen", 0) > 30]
                for k in stale:
                    del self._servers[k]
                    if self._on_servers_changed:
                        self._on_servers_changed()
            except Exception:
                pass
        sock.close()

    def connect(self, host: str, port: int):
        key = f"{host}:{port}"
        self._connected_server = key
        self._notify(f"[NET] Connecting to {key} …")
        # Test /announce
        url = f"http://{host}:{port}/announce"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                info = json.loads(r.read())
            self._notify(f"[NET] Connected to '{info.get('name',key)}'  "
                         f"— {info.get('tracks',0)} tracks")
        except Exception as e:
            self._notify(f"[NET] Connect failed: {e}")
            self._connected_server = None
            return

        # Start playing /stream
        stream_url = f"http://{host}:{port}/stream"
        try:
            self.player.root.after(0, lambda: self._play_stream(stream_url))
        except Exception as e:
            log_exception("netstream_connect_play", e)

        # Start meta polling
        if self._meta_thread and self._meta_thread.is_alive():
            pass  # existing thread will notice _connected_server changed
        else:
            self._meta_thread = threading.Thread(
                target=self._meta_poll_loop, args=(host, port),
                daemon=True, name="netstream-meta"
            )
            self._meta_thread.start()

    def disconnect(self):
        self._connected_server = None
        try:
            self.player.engine.stop()
        except Exception:
            pass
        self._notify("[NET] Disconnected.")

    def send_control(self, host: str, port: int, action: str, value=None):
        def _do():
            try:
                data = json.dumps({"action": action, "value": value}).encode()
                req = urllib.request.Request(
                    f"http://{host}:{port}/control",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                self._notify(f"[NET] Control failed: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def _play_stream(self, url: str):
        try:
            eng = self.player.engine
            eng.stop()
            eng.load(url)
            eng.play()
            self._notify(f"[NET] Streaming {url}")
        except Exception as e:
            self._notify(f"[NET] Stream error: {e}")
            log_exception("netstream_play", e)

    def _meta_poll_loop(self, host: str, port: int):
        key = f"{host}:{port}"
        while self._connected_server == key:
            try:
                url = f"http://{host}:{port}/meta"
                with urllib.request.urlopen(url, timeout=4) as r:
                    meta = json.loads(r.read())
                self._current_meta = meta
                if self._on_meta_update:
                    self._on_meta_update(meta)
            except Exception:
                pass
            time.sleep(_META_INTERVAL)

    def get_servers(self) -> List[Dict]:
        return list(self._servers.values())

    def _notify(self, msg: str):
        """Thread-safe status callback — always routes through Tk main thread."""
        if not self._on_status:
            return
        cb = self._on_status
        try:
            self.player.root.after(0, lambda m=msg: cb(m))
        except Exception:
            try:
                cb(msg)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  NET STREAM VIEW  — tkinter panel
# ─────────────────────────────────────────────────────────────────────────────
class NetStreamView:
    """
    Builds and manages the NETSTREAM tab inside VoidPlayer.
    Call `build(parent_content_frame, player)` once from _build_deferred_views.
    Returns self.frame.
    """

    def __init__(self, player):
        self.player  = player
        self.server  = NetStreamServer(player)
        self.client  = NetStreamClient(player)
        self.frame: Optional[tk.Frame] = None
        self._server_rows: List[tk.Frame] = []
        self._log_lines: List[str] = []

        # Wire callbacks
        self.server._on_status         = self._append_log
        self.client._on_status         = self._append_log
        self.client._on_servers_changed = self._refresh_server_list
        self.client._on_meta_update    = self._on_meta_update

    def build(self, parent: tk.Frame) -> tk.Frame:
        self.frame = tk.Frame(parent, bg=C["bg"])

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self.frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(12, 0))
        tk.Label(hdr, text="NET·STREAM", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self._ip_lbl = tk.Label(hdr, text="", font=("Courier New", 7),
                                 fg=C["white3"], bg=C["bg"])
        self._ip_lbl.pack(side="right")
        tk.Frame(self.frame, bg=C["border2"], height=2).pack(fill="x", padx=20, pady=(4, 0))
        tk.Frame(self.frame, bg=C["border"],  height=1).pack(fill="x", padx=20, pady=(1, 8))

        # ── Two columns: HOST + LISTEN ────────────────────────────────────────
        cols = tk.Frame(self.frame, bg=C["bg"])
        cols.pack(fill="both", expand=True, padx=20)

        # LEFT — HOST
        host_col = tk.Frame(cols, bg=C["bg"])
        host_col.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_host_panel(host_col)

        # Divider
        tk.Frame(cols, bg=C["border"], width=1).pack(side="left", fill="y", pady=8)

        # RIGHT — LISTEN
        listen_col = tk.Frame(cols, bg=C["bg"])
        listen_col.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self._build_listen_panel(listen_col)

        # ── Log ───────────────────────────────────────────────────────────────
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 4))
        log_hdr = tk.Frame(self.frame, bg=C["bg"])
        log_hdr.pack(fill="x", padx=20)
        tk.Label(log_hdr, text="NET LOG", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left")
        clr = tk.Label(log_hdr, text="[ CLEAR ]", font=FMS, fg=C["white3"],
                       bg=C["bg"], cursor="hand2")
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda e: self._clear_log())
        clr.bind("<Enter>", lambda e: clr.config(fg=C["white"]))
        clr.bind("<Leave>", lambda e: clr.config(fg=C["white3"]))

        log_outer = tk.Frame(self.frame, bg=C["bg"])
        log_outer.pack(fill="both", expand=True, padx=20, pady=(4, 12))
        log_sb = tk.Scrollbar(log_outer, bg=C["panel"], troughcolor=C["bg"],
                               width=6, relief="flat", bd=0)
        log_sb.pack(side="right", fill="y")
        self._log_text = tk.Text(
            log_outer, bg=C["panel"], fg=C["white2"], font=FMS, relief="flat",
            bd=0, highlightthickness=0, wrap="word", state="disabled",
            yscrollcommand=log_sb.set, padx=8, pady=6, height=6
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        log_sb.config(command=self._log_text.yview)
        self._log_text.tag_config("net",   foreground=C["white2"])
        self._log_text.tag_config("ok",    foreground=C["glow"])
        self._log_text.tag_config("err",   foreground=C["red"])

        # Update local IP
        self.frame.after(200, self._update_ip_label)

        return self.frame

    # ── HOST panel ────────────────────────────────────────────────────────────
    def _build_host_panel(self, parent: tk.Frame):
        tk.Label(parent, text="HOST  //  BROADCAST", font=("Courier New", 8, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", pady=(0, 8))

        # Server name
        nf = tk.Frame(parent, bg=C["bg"])
        nf.pack(fill="x", pady=(0, 6))
        tk.Label(nf, text="NAME", font=FMS, fg=C["white3"],
                 bg=C["bg"], width=8, anchor="w").pack(side="left")
        self._name_var = tk.StringVar(value=socket.gethostname())
        name_e = tk.Entry(nf, textvariable=self._name_var, font=FMS,
                           bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                           relief="flat", bd=0, width=20,
                           highlightthickness=1, highlightbackground=C["border"])
        name_e.pack(side="left", ipady=3, padx=(4, 0))

        # Port
        pf = tk.Frame(parent, bg=C["bg"])
        pf.pack(fill="x", pady=(0, 6))
        tk.Label(pf, text="PORT", font=FMS, fg=C["white3"],
                 bg=C["bg"], width=8, anchor="w").pack(side="left")
        self._port_var = tk.StringVar(value=str(_DEFAULT_HTTP_PORT))
        port_e = tk.Entry(pf, textvariable=self._port_var, font=FMS,
                           bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                           relief="flat", bd=0, width=8,
                           highlightthickness=1, highlightbackground=C["border"])
        port_e.pack(side="left", ipady=3, padx=(4, 0))

        # Allow remote control
        self._ctrl_var = tk.BooleanVar(value=False)
        ctrl_frame = tk.Frame(parent, bg=C["bg"])
        ctrl_frame.pack(fill="x", pady=(0, 10))
        tk.Label(ctrl_frame, text="ALLOW REMOTE CONTROL", font=FMS,
                 fg=C["white3"], bg=C["bg"]).pack(side="left")
        self._ctrl_ind = tk.Label(ctrl_frame, text="○", font=FMS,
                                   fg=C["white3"], bg=C["bg"], cursor="hand2")
        self._ctrl_ind.pack(side="left", padx=(4, 0))

        def _toggle_ctrl():
            self._ctrl_var.set(not self._ctrl_var.get())
            self._ctrl_ind.config(
                text="●" if self._ctrl_var.get() else "○",
                fg=C["glow"] if self._ctrl_var.get() else C["white3"]
            )

        for w in (ctrl_frame, self._ctrl_ind):
            w.bind("<Button-1>", lambda e: _toggle_ctrl())

        # Start/Stop
        btn_row = tk.Frame(parent, bg=C["bg"])
        btn_row.pack(fill="x", pady=(0, 10))
        self._srv_start_btn = self._mk_btn(btn_row, "▶ START SERVER", self._start_server)
        self._srv_start_btn.pack(side="left", padx=(0, 8))
        self._srv_stop_btn  = self._mk_btn(btn_row, "■ STOP",         self._stop_server, dim=True)
        self._srv_stop_btn.pack(side="left")

        # Status row
        self._srv_status = tk.Label(parent, text="— offline —", font=FMS,
                                     fg=C["white3"], bg=C["bg"])
        self._srv_status.pack(anchor="w")

        # Listener count
        self._listener_lbl = tk.Label(parent, text="", font=("Courier New", 7),
                                       fg=C["white3"], bg=C["bg"])
        self._listener_lbl.pack(anchor="w")
        parent.after(2000, self._poll_listener_count)

        # Share URL label
        self._share_lbl = tk.Label(parent, text="", font=("Courier New", 7),
                                    fg=C["white3"], bg=C["bg"], cursor="hand2")
        self._share_lbl.pack(anchor="w")
        self._share_lbl.bind("<Button-1>", lambda e: self._copy_url())

    # ── LISTEN panel ──────────────────────────────────────────────────────────
    def _build_listen_panel(self, parent: tk.Frame):
        tk.Label(parent, text="LISTEN  //  DISCOVER", font=("Courier New", 8, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", pady=(0, 8))

        disc_row = tk.Frame(parent, bg=C["bg"])
        disc_row.pack(fill="x", pady=(0, 8))
        self._disc_btn = self._mk_btn(disc_row, "◉ SCAN", self._start_discovery)
        self._disc_btn.pack(side="left", padx=(0, 8))
        self._disc_stop_btn = self._mk_btn(disc_row, "■ STOP", self._stop_discovery, dim=True)
        self._disc_stop_btn.pack(side="left")

        # Manual host entry
        mf = tk.Frame(parent, bg=C["bg"])
        mf.pack(fill="x", pady=(0, 8))
        tk.Label(mf, text="MANUAL IP", font=FMS, fg=C["white3"],
                 bg=C["bg"], width=10, anchor="w").pack(side="left")
        self._manual_host_var = tk.StringVar()
        manual_e = tk.Entry(mf, textvariable=self._manual_host_var, font=FMS,
                             bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                             relief="flat", bd=0, width=18,
                             highlightthickness=1, highlightbackground=C["border"])
        manual_e.pack(side="left", ipady=3, padx=(4, 0))
        manual_e.bind("<Return>", lambda e: self._connect_manual())
        conn_btn = self._mk_btn(mf, "GO", self._connect_manual)
        conn_btn.pack(side="left", padx=(6, 0))

        # Discovered server list
        tk.Label(parent, text="DISCOVERED SERVERS", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", pady=(4, 4))
        self._server_list_frame = tk.Frame(parent, bg=C["bg"])
        self._server_list_frame.pack(fill="both", expand=True)

        # Now playing (while connected)
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", pady=(8, 4))
        tk.Label(parent, text="REMOTE NOW PLAYING", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w")
        self._remote_title  = tk.Label(parent, text="—", font=FM,
                                        fg=C["white"], bg=C["bg"])
        self._remote_title.pack(anchor="w")
        self._remote_artist = tk.Label(parent, text="", font=FMS,
                                        fg=C["white3"], bg=C["bg"])
        self._remote_artist.pack(anchor="w")
        self._remote_pos    = tk.Label(parent, text="", font=("Courier New", 7),
                                        fg=C["white3"], bg=C["bg"])
        self._remote_pos.pack(anchor="w")

        disc_btn2 = self._mk_btn(parent, "✕ DISCONNECT", self._disconnect, dim=True)
        disc_btn2.pack(anchor="w", pady=(8, 0))

    # ── server control ────────────────────────────────────────────────────────
    def _start_server(self):
        try:
            port = int(self._port_var.get())
        except ValueError:
            port = _DEFAULT_HTTP_PORT
        self.server.port          = port
        self.server.name          = self._name_var.get() or socket.gethostname()
        self.server.allow_control = self._ctrl_var.get()
        ok = self.server.start()
        if ok:
            self._srv_status.config(text=f"LIVE  :{port}", fg=C["glow"])
            ip = self.server._local_ip()
            url = f"http://{ip}:{port}/stream"
            self._share_lbl.config(text=f"▸ {url}  (click to copy)")
            self._share_url = url
        else:
            self._srv_status.config(text="FAILED — port in use?", fg=C["red"])

    def _stop_server(self):
        # Run on background thread — server.stop() waits for the HTTP
        # serve loop to finish its current timeout which could be up to 1s.
        self._srv_status.config(text="— stopping… —", fg=C["white3"])
        def _do():
            self.server.stop()
        threading.Thread(target=_do, daemon=True).start()
        # Update UI after a short delay to let shutdown complete
        if self.frame and self.frame.winfo_exists():
            self.frame.after(1200, self._on_server_stopped)

    def _on_server_stopped(self):
        if not self.frame or not self.frame.winfo_exists():
            return
        self._srv_status.config(text="— offline —", fg=C["white3"])
        self._share_lbl.config(text="")
        self._listener_lbl.config(text="")

    def _copy_url(self):
        url = getattr(self, "_share_url", "")
        if url and self.frame:
            try:
                self.frame.clipboard_clear()
                self.frame.clipboard_append(url)
                self._share_lbl.config(text="✓ copied to clipboard")
                self.frame.after(2000, lambda: self._share_lbl.config(
                    text=f"▸ {url}  (click to copy)"
                ))
            except Exception:
                pass

    def _poll_listener_count(self):
        if not self.frame or not self.frame.winfo_exists():
            return
        n = self.server._listener_count
        if n > 0:
            self._listener_lbl.config(text=f"◉ {n} listener{'s' if n != 1 else ''}")
        else:
            self._listener_lbl.config(text="")
        self.frame.after(3000, self._poll_listener_count)

    # ── discovery control ─────────────────────────────────────────────────────
    def _start_discovery(self):
        self.client.start_discovery()
        self._append_log("[NET] Scanning for OTERNOS servers on LAN …")
        self._disc_btn.config(fg=C["glow"])

    def _stop_discovery(self):
        self.client.stop_discovery()
        self._disc_btn.config(fg=C["white"])
        self._refresh_server_list()

    def _connect_manual(self):
        raw = self._manual_host_var.get().strip()
        if not raw:
            return
        if ":" in raw:
            host, _, port_s = raw.rpartition(":")
            try:
                port = int(port_s)
            except ValueError:
                port = _DEFAULT_HTTP_PORT
        else:
            host = raw
            port = _DEFAULT_HTTP_PORT
        threading.Thread(
            target=lambda: self.client.connect(host, port),
            daemon=True
        ).start()

    def _disconnect(self):
        self.client.disconnect()
        self._remote_title.config(text="—")
        self._remote_artist.config(text="")
        self._remote_pos.config(text="")

    # ── server list refresh ───────────────────────────────────────────────────
    def _refresh_server_list(self):
        if not self.frame or not self.frame.winfo_exists():
            return
        try:
            self.player.root.after(0, self._rebuild_server_list)
        except Exception:
            pass

    def _rebuild_server_list(self):
        if not self.frame or not self.frame.winfo_exists():
            return
        for w in self._server_list_frame.winfo_children():
            w.destroy()
        servers = self.client.get_servers()
        if not servers:
            tk.Label(self._server_list_frame, text="No servers found",
                     font=FMS, fg=C["white3"], bg=C["bg"]).pack(anchor="w")
            return
        for srv in servers:
            host = srv.get("host","?")
            port = srv.get("port", _DEFAULT_HTTP_PORT)
            name = srv.get("name", host)
            tracks = srv.get("tracks", 0)
            key  = f"{host}:{port}"
            is_conn = self.client._connected_server == key

            row = tk.Frame(self._server_list_frame, bg=C["select"] if is_conn else C["bg"],
                           pady=3, padx=6)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=name, font=FMS, fg=C["glow"] if is_conn else C["white"],
                     bg=row["bg"]).pack(side="left")
            tk.Label(row, text=f"{tracks} tracks", font=("Courier New", 7),
                     fg=C["white3"], bg=row["bg"]).pack(side="left", padx=8)
            tk.Label(row, text=f"{host}:{port}", font=("Courier New", 7),
                     fg=C["white3"], bg=row["bg"]).pack(side="left")
            conn_lbl = tk.Label(row, text="[ CONNECT ]" if not is_conn else "[ CONNECTED ]",
                                 font=FMS, fg=C["white3"] if not is_conn else C["glow"],
                                 bg=row["bg"], cursor="hand2")
            conn_lbl.pack(side="right")
            if not is_conn:
                conn_lbl.bind("<Button-1>", lambda e, h=host, p=port: threading.Thread(
                    target=lambda: self.client.connect(h, p), daemon=True
                ).start())
                conn_lbl.bind("<Enter>", lambda e, l=conn_lbl: l.config(fg=C["white"]))
                conn_lbl.bind("<Leave>", lambda e, l=conn_lbl: l.config(fg=C["white3"]))

    # ── meta update ───────────────────────────────────────────────────────────
    def _on_meta_update(self, meta: Dict):
        try:
            self.player.root.after(0, lambda: self._apply_meta(meta))
        except Exception:
            pass

    def _apply_meta(self, meta: Dict):
        if not self.frame or not self.frame.winfo_exists():
            return
        self._remote_title.config(text=meta.get("title","—") or "—")
        self._remote_artist.config(text=meta.get("artist","") or "")
        pos = meta.get("position_s", 0)
        dur = meta.get("duration_s", 0)
        state = "▶" if meta.get("playing") else "⏸"
        if dur:
            pm, ps = divmod(int(pos), 60)
            dm, ds = divmod(int(dur), 60)
            self._remote_pos.config(
                text=f"{state}  {pm}:{ps:02d} / {dm}:{ds:02d}"
            )
        else:
            self._remote_pos.config(text=state)

    # ── log ───────────────────────────────────────────────────────────────────
    def _append_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self._log_lines.append(entry)
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-200:]
        if not self._log_text:
            return
        try:
            tag = "ok" if "live" in msg.lower() or "connected" in msg.lower() else \
                  "err" if "fail" in msg.lower() or "error" in msg.lower() else "net"
            self.player.root.after(0, lambda e=entry, t=tag: self._write_log(e, t))
        except Exception:
            pass

    def _write_log(self, entry: str, tag: str):
        if not self._log_text or not self._log_text.winfo_exists():
            return
        self._log_text.config(state="normal")
        self._log_text.insert("end", entry + "\n", (tag,))
        self._log_text.config(state="disabled")
        self._log_text.see("end")

    def _clear_log(self):
        if self._log_text:
            self._log_text.config(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.config(state="disabled")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _mk_btn(self, parent, text, cmd, dim=False):
        lbl = tk.Label(parent, text=text, font=FMS,
                       fg=C["white3"] if dim else C["white"],
                       bg=C["panel"], cursor="hand2", padx=10, pady=4)
        lbl.bind("<Button-1>", lambda e: cmd())
        lbl.bind("<Enter>", lambda e: lbl.config(fg=C["glow"]))
        lbl.bind("<Leave>", lambda e: lbl.config(fg=C["white3"] if dim else C["white"]))
        return lbl

    def _update_ip_label(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if self._ip_lbl and self._ip_lbl.winfo_exists():
                self._ip_lbl.config(text=f"LAN: {ip}")
        except Exception:
            pass

    def on_view_shown(self):
        """Called by _switch_view."""
        self._update_ip_label()
        self._rebuild_server_list()


# ─────────────────────────────────────────────────────────────────────────────
#  INTEGRATION NOTES  (paste these into player.py)
# ─────────────────────────────────────────────────────────────────────────────
"""
STEP 1 — imports at top of player.py:

    from oternos.netstream import NetStreamView          # frozen
    from .netstream import NetStreamView                 # non-frozen

STEP 2 — in VoidPlayer.__init__, after Discord init (~line 261):

    self._netstream_view = NetStreamView(self)

STEP 3 — in _build_topbar _tabs list (~line 2323), add:

    ("NETSTREAM", "netstream"),

STEP 4 — in _build_deferred_views _steps list (~line 3243), add:

    self._build_netstream_view,

STEP 5 — add new method to VoidPlayer:

    def _build_netstream_view(self):
        self.netstream_frame = self._netstream_view.build(self.content)

STEP 6 — in _switch_view _do_switch, pack_forget list, add:

    "netstream_frame",

STEP 7 — in _switch_view _do_switch, elif chain, add:

    elif view == "netstream":
        self.netstream_frame.pack(fill="both", expand=True)
        self._netstream_view.on_view_shown()

STEP 8 — in _update_tabs _labels dict, add:

    "netstream": "NETSTREAM",

STEP 9 — in _on_close, stop server + client:

    if hasattr(self, '_netstream_view'):
        self._netstream_view.server.stop()
        self._netstream_view.client.stop_discovery()
"""
