"""
server.py — OTERNOS STREAMING SERVER
Runs as a background thread inside the Oternos process.
Exposes your local library over HTTP so any device on your network
can stream, browse, and control playback.

Default: http://localhost:7471  (or your LAN IP on the same port)

Endpoints:
  GET  /                      → web player UI
  GET  /api/library           → full track list as JSON
  GET  /api/track/<id>        → single track metadata
  GET  /api/art/<id>          → album art (JPEG)
  GET  /stream/<id>           → audio stream (supports Range requests)
  GET  /api/status            → current playback state
  POST /api/control           → play / pause / next / prev / seek / volume
  GET  /api/search?q=...      → search library
"""

import os
import json
import math
import mimetypes
import threading
import hashlib
import logging
from pathlib import Path
from datetime import datetime

# ── Suppress Flask/Werkzeug console noise ─────────────────────────────────────
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

try:
    from flask import (Flask, jsonify, request, Response,
                       send_file, abort, render_template_string)
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

SETTINGS_PATH = Path.home() / ".voidplayer.json"
PORT          = 7471

# ─────────────────────────────────────────────────────────────────────────────
#  WEB PLAYER UI  (single-file, no external deps, cybercore aesthetic)
# ─────────────────────────────────────────────────────────────────────────────
WEB_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OTERNOS // REMOTE</title>
<style>
  :root {
    --bg:     #0a0a0a;
    --bg2:    #111111;
    --bg3:    #1a1a1a;
    --fg:     #d0d0d0;
    --dim:    #444444;
    --acc:    #ffffff;
    --green:  #00ff88;
    --red:    #ff3333;
    --yellow: #ffcc00;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--fg);
    font-family: 'Courier New', monospace; font-size: 13px;
    height: 100vh; display: flex; flex-direction: column;
  }
  /* ── header ── */
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 18px; border-bottom: 1px solid #1a1a1a;
    background: var(--bg);
  }
  .logo { font-size: 16px; font-weight: bold; letter-spacing: 2px; color: var(--acc); }
  .logo span { color: var(--dim); font-size: 11px; margin-left: 8px; }
  #status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--dim); display: inline-block; margin-right: 6px;
  }
  #status-dot.online { background: var(--green); }

  /* ── layout ── */
  .body { display: flex; flex: 1; overflow: hidden; }
  .sidebar {
    width: 260px; min-width: 260px; background: var(--bg2);
    border-right: 1px solid #1a1a1a;
    display: flex; flex-direction: column;
  }
  .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  /* ── search ── */
  .search-wrap { padding: 10px; border-bottom: 1px solid #161616; }
  #search {
    width: 100%; background: var(--bg3); border: 1px solid #222;
    color: var(--fg); font-family: inherit; font-size: 12px;
    padding: 6px 10px; outline: none;
  }
  #search:focus { border-color: #333; }

  /* ── track list ── */
  #tracklist {
    flex: 1; overflow-y: auto; list-style: none;
  }
  #tracklist::-webkit-scrollbar { width: 4px; }
  #tracklist::-webkit-scrollbar-track { background: var(--bg2); }
  #tracklist::-webkit-scrollbar-thumb { background: #2a2a2a; }
  .track-item {
    padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #0f0f0f;
    display: flex; align-items: center; gap: 10px;
    transition: background 0.1s;
  }
  .track-item:hover  { background: var(--bg3); }
  .track-item.active { background: #1e1e1e; color: var(--acc); }
  .track-num { color: var(--dim); font-size: 10px; min-width: 22px; }
  .track-info { flex: 1; overflow: hidden; }
  .track-title {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    font-size: 12px;
  }
  .track-artist { color: var(--dim); font-size: 10px; margin-top: 2px; }
  .track-dur { color: var(--dim); font-size: 10px; }

  /* ── now playing ── */
  #nowplaying {
    border-bottom: 1px solid #1a1a1a;
    padding: 16px 20px; background: var(--bg);
    display: flex; align-items: center; gap: 16px;
  }
  #art {
    width: 64px; height: 64px; background: var(--bg3);
    border: 1px solid #1e1e1e; flex-shrink: 0;
    object-fit: cover;
  }
  .np-meta { flex: 1; overflow: hidden; }
  #np-title {
    font-size: 14px; font-weight: bold; color: var(--acc);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  #np-artist { color: var(--dim); font-size: 11px; margin-top: 4px; }
  #np-album  { color: var(--dim); font-size: 10px; margin-top: 2px; }

  /* ── progress ── */
  .progress-wrap { padding: 10px 20px 4px; }
  #progress-bar {
    width: 100%; height: 3px; background: var(--bg3);
    cursor: pointer; position: relative; margin-bottom: 6px;
  }
  #progress-fill {
    height: 100%; background: var(--acc); width: 0%;
    transition: width 0.5s linear; pointer-events: none;
  }
  .time-row {
    display: flex; justify-content: space-between;
    color: var(--dim); font-size: 10px;
  }

  /* ── controls ── */
  .controls {
    display: flex; align-items: center; justify-content: center;
    gap: 20px; padding: 12px 20px;
    border-bottom: 1px solid #1a1a1a;
  }
  .btn {
    background: none; border: 1px solid #222; color: var(--fg);
    font-family: inherit; font-size: 11px; padding: 6px 14px;
    cursor: pointer; letter-spacing: 1px;
    transition: background 0.1s, color 0.1s;
  }
  .btn:hover  { background: var(--bg3); color: var(--acc); }
  .btn.active { border-color: var(--acc); color: var(--acc); }
  .btn-play {
    font-size: 13px; padding: 8px 20px;
    border-color: #333;
  }

  /* ── volume ── */
  .vol-wrap {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 20px; border-bottom: 1px solid #1a1a1a;
    font-size: 10px; color: var(--dim);
  }
  #vol-slider {
    flex: 1; accent-color: var(--acc); cursor: pointer;
  }
  #vol-val { min-width: 28px; text-align: right; }

  /* ── console ── */
  #console {
    flex: 1; overflow-y: auto; padding: 10px 20px;
    font-size: 10px; color: var(--dim); background: var(--bg);
  }
  #console::-webkit-scrollbar { width: 3px; }
  #console::-webkit-scrollbar-thumb { background: #1a1a1a; }
  .log-line { margin-bottom: 3px; }
  .log-line.ok  { color: var(--green); }
  .log-line.err { color: var(--red); }
  .log-line.warn { color: var(--yellow); }

  /* ── footer ── */
  footer {
    padding: 6px 18px; border-top: 1px solid #111;
    font-size: 9px; color: #2a2a2a;
    display: flex; justify-content: space-between;
  }
</style>
</head>
<body>

<header>
  <div class="logo">OTERNOS <span>// REMOTE</span></div>
  <div style="font-size:10px; color:var(--dim)">
    <span id="status-dot"></span><span id="conn-lbl">CONNECTING</span>
  </div>
</header>

<div class="body">

  <!-- sidebar: track list -->
  <div class="sidebar">
    <div class="search-wrap">
      <input id="search" type="text" placeholder="SEARCH LIBRARY..." autocomplete="off">
    </div>
    <ul id="tracklist"></ul>
  </div>

  <!-- main panel -->
  <div class="main">

    <!-- now playing -->
    <div id="nowplaying">
      <img id="art" src="" alt="">
      <div class="np-meta">
        <div id="np-title">NO TRACK LOADED</div>
        <div id="np-artist">—</div>
        <div id="np-album"></div>
      </div>
      <div style="font-size:10px; color:var(--dim); text-align:right">
        <div id="np-fmt">—</div>
        <div id="np-br" style="margin-top:4px">—</div>
      </div>
    </div>

    <!-- progress -->
    <div class="progress-wrap">
      <div id="progress-bar" onclick="seek(event)">
        <div id="progress-fill"></div>
      </div>
      <div class="time-row">
        <span id="t-cur">0:00</span>
        <span id="t-dur">0:00</span>
      </div>
    </div>

    <!-- controls -->
    <div class="controls">
      <button class="btn" onclick="ctrl('prev')">◀◀ PREV</button>
      <button class="btn btn-play" id="btn-play" onclick="ctrl('toggle')">▶ PLAY</button>
      <button class="btn" onclick="ctrl('next')">NEXT ▶▶</button>
    </div>

    <!-- volume -->
    <div class="vol-wrap">
      VOL
      <input id="vol-slider" type="range" min="0" max="100" value="80"
             oninput="setVol(this.value)">
      <span id="vol-val">80</span>
    </div>

    <!-- console log -->
    <div id="console"></div>

  </div>
</div>

<footer>
  <span>OTERNOS REMOTE PLAYER</span>
  <span id="lib-count">— tracks</span>
</footer>

<script>
  let library = [];
  let currentId = null;
  let pollTimer = null;
  let audio = new Audio();
  audio.preload = 'none';

  // ── logging ───────────────────────────────────────────────────────────────
  function clog(msg, cls='') {
    const c = document.getElementById('console');
    const d = document.createElement('div');
    d.className = 'log-line ' + cls;
    const ts = new Date().toTimeString().slice(0,8);
    d.textContent = `[${ts}] ${msg}`;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
  }

  // ── connection ────────────────────────────────────────────────────────────
  function setOnline(on) {
    const dot = document.getElementById('status-dot');
    const lbl = document.getElementById('conn-lbl');
    dot.className = on ? 'online' : '';
    lbl.textContent = on ? 'ONLINE' : 'OFFLINE';
  }

  // ── load library ──────────────────────────────────────────────────────────
  async function loadLibrary() {
    try {
      const r = await fetch('/api/library');
      library = await r.json();
      document.getElementById('lib-count').textContent = library.length + ' TRACKS';
      renderList(library);
      setOnline(true);
      clog('Library loaded — ' + library.length + ' tracks', 'ok');
    } catch(e) {
      setOnline(false);
      clog('Failed to load library: ' + e, 'err');
    }
  }

  function renderList(tracks) {
    const ul = document.getElementById('tracklist');
    ul.innerHTML = '';
    tracks.forEach((t, i) => {
      const li = document.createElement('li');
      li.className = 'track-item' + (t.id === currentId ? ' active' : '');
      li.dataset.id = t.id;
      li.innerHTML = `
        <span class="track-num">${i+1}</span>
        <div class="track-info">
          <div class="track-title">${esc(t.title)}</div>
          <div class="track-artist">${esc(t.artist || '—')}</div>
        </div>
        <span class="track-dur">${fmtTime(t.duration||0)}</span>`;
      li.onclick = () => playTrack(t.id);
      ul.appendChild(li);
    });
  }

  // ── search ────────────────────────────────────────────────────────────────
  document.getElementById('search').addEventListener('input', function() {
    const q = this.value.toLowerCase();
    const filtered = q
      ? library.filter(t =>
          (t.title||'').toLowerCase().includes(q) ||
          (t.artist||'').toLowerCase().includes(q) ||
          (t.album||'').toLowerCase().includes(q))
      : library;
    renderList(filtered);
  });

  // ── playback ──────────────────────────────────────────────────────────────
  function playTrack(id) {
    currentId = id;
    const t = library.find(x => x.id === id);
    if (!t) return;

    // update art + meta immediately
    document.getElementById('art').src = '/api/art/' + id;
    document.getElementById('np-title').textContent  = t.title || 'Unknown';
    document.getElementById('np-artist').textContent = t.artist || '—';
    document.getElementById('np-album').textContent  = t.album  || '';
    document.getElementById('np-fmt').textContent    = (t.ext || '').toUpperCase();
    document.getElementById('btn-play').textContent  = '⏸ PAUSE';

    // stream via browser audio
    audio.src = '/stream/' + id;
    audio.play().catch(() => {});

    // highlight row
    document.querySelectorAll('.track-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id == id);
    });

    clog('Playing: ' + (t.artist ? t.artist + ' — ' : '') + t.title, 'ok');

    // also tell the desktop app (best-effort)
    fetch('/api/control', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action:'play', id})
    }).catch(()=>{});
  }

  function ctrl(action) {
    if (action === 'toggle') {
      if (audio.paused) {
        audio.play();
        document.getElementById('btn-play').textContent = '⏸ PAUSE';
      } else {
        audio.pause();
        document.getElementById('btn-play').textContent = '▶ PLAY';
      }
      return;
    }
    if (action === 'next' || action === 'prev') {
      const idx = library.findIndex(t => t.id === currentId);
      const next = action === 'next'
        ? library[(idx + 1) % library.length]
        : library[(idx - 1 + library.length) % library.length];
      if (next) playTrack(next.id);
    }
    fetch('/api/control', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action})
    }).catch(()=>{});
  }

  function seek(e) {
    const bar = document.getElementById('progress-bar');
    const pct = e.offsetX / bar.offsetWidth;
    audio.currentTime = audio.duration * pct;
  }

  function setVol(v) {
    audio.volume = v / 100;
    document.getElementById('vol-val').textContent = v;
  }

  // ── progress tick ─────────────────────────────────────────────────────────
  audio.addEventListener('timeupdate', () => {
    if (!audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('t-cur').textContent = fmtTime(audio.currentTime);
    document.getElementById('t-dur').textContent = fmtTime(audio.duration);
  });
  audio.addEventListener('ended', () => ctrl('next'));
  audio.addEventListener('error', () => clog('Stream error', 'err'));

  // ── status poll (sync with desktop app) ───────────────────────────────────
  async function pollStatus() {
    try {
      const r   = await fetch('/api/status');
      const s   = await r.json();
      setOnline(true);
      if (s.track_id && s.track_id !== currentId && !audio.src.includes('/stream/')) {
        // desktop app is playing something — reflect it
        currentId = s.track_id;
        const t = library.find(x => x.id === s.track_id);
        if (t) {
          document.getElementById('np-title').textContent  = t.title  || 'Unknown';
          document.getElementById('np-artist').textContent = t.artist || '—';
          document.getElementById('np-album').textContent  = t.album  || '';
          document.getElementById('art').src = '/api/art/' + s.track_id;
          document.querySelectorAll('.track-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id == s.track_id);
          });
        }
      }
    } catch(e) { setOnline(false); }
  }

  // ── helpers ───────────────────────────────────────────────────────────────
  function fmtTime(s) {
    s = Math.floor(s || 0);
    return Math.floor(s/60) + ':' + String(s%60).padStart(2,'0');
  }
  function esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── init ──────────────────────────────────────────────────────────────────
  loadLibrary();
  setInterval(pollStatus, 3000);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _track_id(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()[:12]


def _load_library() -> list[dict]:
    """Read library from ~/.voidplayer.json and build track list."""
    try:
        raw = json.loads(SETTINGS_PATH.read_text())
        tracks = raw.get("library", [])
    except Exception:
        tracks = []

    out = []
    for entry in tracks:
        # library entries may be plain path strings or dicts
        if isinstance(entry, str):
            path = entry
            meta = {}
        elif isinstance(entry, dict):
            path = entry.get("path", "")
            meta = entry
        else:
            continue

        if not path or not os.path.isfile(path):
            continue

        tid = _track_id(path)
        ext = Path(path).suffix.lstrip(".").lower()

        # pull whatever metadata is stored
        out.append({
            "id":       tid,
            "path":     path,
            "title":    meta.get("title")  or Path(path).stem,
            "artist":   meta.get("artist") or "",
            "album":    meta.get("album")  or "",
            "duration": meta.get("duration") or 0,
            "ext":      ext,
        })
    return out


def _fmt_mime(ext: str) -> str:
    m = {
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
        "wav": "audio/wav",
        "aac": "audio/aac",
        "m4a": "audio/mp4",
        "opus": "audio/opus",
    }
    return m.get(ext, "audio/mpeg")


# ─────────────────────────────────────────────────────────────────────────────
#  FLASK APP
# ─────────────────────────────────────────────────────────────────────────────

def _build_flask_app(player_ref: list) -> "Flask":
    """
    player_ref is a one-element list holding the VoidPlayer instance (or None).
    It's a list so the server can access the live object even after it's set.
    """
    app = Flask(__name__)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    # ── web UI ────────────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template_string(WEB_UI)

    # ── library ───────────────────────────────────────────────────────────────
    @app.route("/api/library")
    def api_library():
        tracks = _load_library()
        # strip path from response (security)
        safe = [{k: v for k, v in t.items() if k != "path"} for t in tracks]
        return jsonify(safe)

    @app.route("/api/track/<tid>")
    def api_track(tid):
        for t in _load_library():
            if t["id"] == tid:
                return jsonify({k: v for k, v in t.items() if k != "path"})
        abort(404)

    # ── album art ─────────────────────────────────────────────────────────────
    @app.route("/api/art/<tid>")
    def api_art(tid):
        for t in _load_library():
            if t["id"] == tid:
                path = t["path"]
                # try mutagen / tinytag for embedded art
                img_bytes = _extract_art(path)
                if img_bytes:
                    return Response(img_bytes, mimetype="image/jpeg")
                break
        # fallback: 1×1 black pixel
        import base64
        px = base64.b64decode(
            "FFD8FFE000104A464946000101000001000100"
            "00FFDB004300080606070605080707070909"
            "0808090C140D0C0B0B0C1912130F141D1A1F"
            "1E1D1A1C1C20242E2720222C231C1C283729"
            "2C30313434341F27393D38323C2E333432FF"
            "C0000B080001000101011100FFC40014000"
            "10000000000000000000000000000000000"
            "FFC40014100100000000000000000000000"
            "00000000FFDA00030101003F00FAF00FFFD9"
        )
        return Response(px, mimetype="image/jpeg")

    # ── stream ────────────────────────────────────────────────────────────────
    @app.route("/stream/<tid>")
    def stream(tid):
        path = None
        ext  = "mp3"
        for t in _load_library():
            if t["id"] == tid:
                path = t["path"]
                ext  = t["ext"]
                break
        if not path or not os.path.isfile(path):
            abort(404)

        mime      = _fmt_mime(ext)
        file_size = os.path.getsize(path)
        range_hdr = request.headers.get("Range")

        if range_hdr:
            # parse "bytes=start-end"
            byte_range = range_hdr.replace("bytes=", "").split("-")
            start = int(byte_range[0]) if byte_range[0] else 0
            end   = int(byte_range[1]) if byte_range[1] else file_size - 1
            end   = min(end, file_size - 1)
            length = end - start + 1

            def _gen():
                with open(path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            headers = {
                "Content-Range":  f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges":  "bytes",
                "Content-Length": str(length),
                "Content-Type":   mime,
            }
            return Response(_gen(), 206, headers=headers)
        else:
            def _gen_full():
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        yield chunk

            headers = {
                "Accept-Ranges":  "bytes",
                "Content-Length": str(file_size),
                "Content-Type":   mime,
            }
            return Response(_gen_full(), 200, headers=headers)

    # ── status ────────────────────────────────────────────────────────────────
    @app.route("/api/status")
    def api_status():
        player = player_ref[0]
        if not player:
            return jsonify({"playing": False, "track_id": None})
        try:
            path     = getattr(player, "current_track", None)
            playing  = getattr(player, "playing", False)
            position = getattr(player, "position", 0) or 0
            volume   = getattr(player, "volume", 80) or 80
            tid      = _track_id(path) if path else None
            return jsonify({
                "playing":  playing,
                "track_id": tid,
                "position": round(float(position), 2),
                "volume":   int(volume),
            })
        except Exception:
            return jsonify({"playing": False, "track_id": None})

    # ── control ───────────────────────────────────────────────────────────────
    @app.route("/api/control", methods=["POST"])
    def api_control():
        player = player_ref[0]
        data   = request.get_json(force=True, silent=True) or {}
        action = data.get("action", "")

        if not player:
            return jsonify({"ok": False, "error": "player not ready"})

        try:
            if action == "toggle":
                if getattr(player, "playing", False):
                    player.pause()
                else:
                    player.resume()
            elif action == "play":
                tid = data.get("id")
                if tid:
                    for t in _load_library():
                        if t["id"] == tid:
                            # schedule on main tkinter thread
                            player.after(0, lambda p=t["path"]: player._play_file(p))
                            break
            elif action == "pause":
                player.pause()
            elif action == "next":
                player.after(0, player._next_track)
            elif action == "prev":
                player.after(0, player._prev_track)
            elif action == "seek":
                pos = float(data.get("position", 0))
                player.after(0, lambda: player._seek(pos))
            elif action == "volume":
                vol = int(data.get("value", 80))
                player.after(0, lambda: player._set_volume(vol))
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

        return jsonify({"ok": True})

    # ── search ────────────────────────────────────────────────────────────────
    @app.route("/api/search")
    def api_search():
        q = request.args.get("q", "").lower()
        if not q:
            tracks = _load_library()
        else:
            tracks = [t for t in _load_library()
                      if q in (t["title"]  or "").lower()
                      or q in (t["artist"] or "").lower()
                      or q in (t["album"]  or "").lower()]
        safe = [{k: v for k, v in t.items() if k != "path"} for t in tracks]
        return jsonify(safe)

    return app


# ─────────────────────────────────────────────────────────────────────────────
#  ART EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_art(path: str) -> bytes | None:
    try:
        import mutagen
        from mutagen.mp3  import MP3
        from mutagen.id3  import ID3
        from mutagen.flac import FLAC
        from mutagen.mp4  import MP4

        ext = Path(path).suffix.lower()
        if ext == ".mp3":
            tags = ID3(path)
            for key in tags:
                if key.startswith("APIC"):
                    return tags[key].data
        elif ext == ".flac":
            f = FLAC(path)
            if f.pictures:
                return f.pictures[0].data
        elif ext in (".m4a", ".aac", ".mp4"):
            tags = MP4(path)
            if "covr" in tags:
                return bytes(tags["covr"][0])
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

_player_ref  = [None]   # set after VoidPlayer is created
_server_thread: threading.Thread | None = None


def set_player(player) -> None:
    """Call this after VoidPlayer is instantiated to wire up control endpoints."""
    _player_ref[0] = player


def start(player=None) -> bool:
    """
    Start the streaming server in a background daemon thread.
    Returns True if started successfully, False if Flask is unavailable.
    """
    global _server_thread

    if not FLASK_AVAILABLE:
        return False

    if player:
        _player_ref[0] = player

    flask_app = _build_flask_app(_player_ref)

    def _run():
        try:
            flask_app.run(
                host="0.0.0.0",
                port=PORT,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
        except OSError:
            # port in use — try next
            try:
                flask_app.run(
                    host="0.0.0.0",
                    port=PORT + 1,
                    debug=False,
                    use_reloader=False,
                    threaded=True,
                )
            except Exception:
                pass
        except Exception:
            pass

    _server_thread = threading.Thread(target=_run, daemon=True, name="oternos-server")
    _server_thread.start()
    return True


def get_url() -> str:
    """Return the local URL for the web player."""
    return f"http://localhost:{PORT}"


def get_lan_url() -> str:
    """Return the LAN IP URL so other devices can connect."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"http://{ip}:{PORT}"
    except Exception:
        return get_url()
