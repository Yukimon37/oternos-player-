"""
player_bridge.py — OTERNOS HTML PLAYER BRIDGE
Runs a lightweight HTTP server on the Tkinter thread side to serve the 
HTML player UI and act as a bi-directional REST API.
"""

import json
import threading
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

BRIDGE_PORT = 47389

class PlayerBridge:
    def __init__(self, player):
        self.player = player
        self.server = None
        self.thread = None
        self._running = False
        
        # We need a reference to the outer class instance inside the handler
        _bridge = self
        
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass # suppress stderr logging for clean console
                
            def _set_cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                
            def do_OPTIONS(self):
                self.send_response(200)
                self._set_cors()
                self.end_headers()
                
            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    try:
                        # Find player_ui.html safely
                        candidates = []
                        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                            candidates.append(Path(sys._MEIPASS) / "oternos" / "player_ui.html")
                            candidates.append(Path(sys.executable).parent / "player_ui.html")
                        else:
                            candidates.append(Path(__file__).parent / "player_ui.html")
                            
                        html_path = None
                        for p in candidates:
                            if p.exists():
                                html_path = p
                                break
                                
                        if not html_path:
                            self.send_response(404)
                            self.end_headers()
                            self.wfile.write(b"player_ui.html not found")
                            return
                            
                        content = html_path.read_text(encoding="utf-8")
                        self.send_response(200)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(content.encode("utf-8"))
                        
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(str(e).encode('utf-8'))
                        
                elif self.path == "/state":
                    self._handle_get_state()
                else:
                    self.send_response(404)
                    self.end_headers()

            def _handle_get_state(self):
                try:
                    p = _bridge.player
                    
                    # Compute current track info
                    track_title = "NO TRACK LOADED"
                    track_artist = "SYS.IDLE"
                    album_art = ""
                    
                    # 1. Local Library
                    if p._active_source == "library" and p.current_idx >= 0 and p.current_idx < len(p.queue):
                        t = p.queue[p.current_idx]
                        track_title = t.get("title", "")
                        track_artist = t.get("artist", "")
                    # 2. Spotify
                    elif p._active_source == "spotify" and p._sp_playing and len(p._sp_tracks) > 0:
                        try:
                            # Try to get currently active track from the Spotify list safely
                            for t in p._sp_tracks:
                                # We can't access active index easily from outside, so we'll just check title
                                pass 
                            # Safe fallback for now:
                            track_title = "SPOTIFY STREAM"
                            track_artist = "ONLINE"
                        except: pass
                    # 3. Soundcloud / Youtube / Deezer / Archive / Bandcamp
                    elif p._active_source == "soundcloud" and getattr(p, "_sc_current_track", None):
                        track_title = p._sc_current_track.get("title", "")
                        track_artist = p._sc_current_track.get("artist", "")
                    elif p._active_source == "youtube" and getattr(p, "_yt_current_track", None):
                        track_title = p._yt_current_track.get("title", "")
                        track_artist = p._yt_current_track.get("artist", "")
                        
                    # Handle raw path fallback
                    if (not track_title or track_title == "Unknown") and p._current_play_path:
                        track_title = Path(p._current_play_path).stem
                        track_artist = "LOCAL AUDIO"

                    state = {
                        "playing": p.engine.is_playing,
                        "volume": p.engine.volume,
                        "position": p.engine.get_time(),
                        "duration": p.engine.get_duration(),
                        "track": track_title,
                        "artist": track_artist,
                        "library_count": len(p.library),
                        "source": p._active_source,
                        "queue_pos": p.current_idx,
                        "queue_len": len(p.queue),
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self._set_cors()
                    self.end_headers()
                    self.wfile.write(json.dumps(state).encode("utf-8"))
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

            def do_POST(self):
                if self.path == "/command":
                    try:
                        length = int(self.headers.get("content-length", 0))
                        body = self.rfile.read(length).decode("utf-8")
                        data = json.loads(body)
                        cmd = data.get("cmd")
                        
                        p = _bridge.player
                        
                        # Route commands via Tkinter mainloop to be thread-safe
                        if cmd == "play_pause":
                            p.root.after(0, p._toggle_play)
                        elif cmd == "next":
                            p.root.after(0, p._next)
                        elif cmd == "prev":
                            p.root.after(0, p._prev)
                        elif cmd == "seek":
                            pos = float(data.get("pos", 0))
                            p.root.after(0, lambda: p._seek_abs(pos))
                        elif cmd == "seek_rel":
                            delta = float(data.get("delta", 0))
                            p.root.after(0, lambda: p._seek_relative(delta))
                        elif cmd == "volume":
                            vol = float(data.get("vol", 1.0))
                            p.root.after(0, lambda: p.engine.set_volume(vol))
                            
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self._set_cors()
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
                        
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

        self.HandlerClass = Handler
        
    def start(self):
        if self._running: return
        self._running = True
        try:
            # Try to bind to port, if fails, we might already have one running
            self.server = HTTPServer(("127.0.0.1", BRIDGE_PORT), self.HandlerClass)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"Player Bridge active on port {BRIDGE_PORT}")
        except Exception as repr:
            print(f"Failed to start bridge: {repr}")

    def stop(self):
        self._running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except: pass
