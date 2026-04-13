"""
bandcamp_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all bandcamp-related methods.
"""

import sys
import tkinter as tk
import threading
import time
import os
import json
import re
import math
import random
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    from oternos.constants import C, FM, FMS, FML, FMX, DATA_FILE, YT_CACHE, HW_ACCEL
    from oternos.diagnostics import log_exception
else:
    from ..constants import C, FM, FMS, FML, FMX, DATA_FILE, YT_CACHE, HW_ACCEL
    from ..diagnostics import log_exception

if getattr(sys, "frozen", False):
    from oternos.stream_cards import StreamCardList
else:
    from ..stream_cards import StreamCardList


class BandcampMixin:
    """Mixin: bandcamp methods for VoidPlayer."""
    def _build_bandcamp_view(self):
        self.bc_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.bc_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="BANDCAMP", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.bc_status_lbl = tk.Label(top, text="[ INDIE / FREE STREAMS ]", font=FMS, fg=C["white3"], bg=C["bg"])
        self.bc_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.bc_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        sf = tk.Frame(self.bc_frame, bg=C["bg"])
        sf.pack(fill="x", pady=(6, 0))
        tk.Label(sf, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.bc_search_var = tk.StringVar()
        bc_entry = tk.Entry(sf, textvariable=self.bc_search_var, font=FM,
                            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                            relief="flat", bd=0, width=38)
        bc_entry.pack(side="left", ipady=4)
        bc_entry.bind("<Return>", lambda e: self._bc_do_search())
        bc_go = tk.Label(sf, text="[GO]", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=8)
        bc_go.pack(side="left")
        bc_go.bind("<Button-1>", lambda e: self._bc_do_search())
        bc_go.bind("<Enter>", lambda e: bc_go.config(fg=C["white"]))
        bc_go.bind("<Leave>", lambda e: bc_go.config(fg=C["white3"]))

        tk.Frame(self.bc_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))
        self.bc_content_lbl = tk.Label(self.bc_frame, text="Search for tracks above",
                                        font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.bc_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        lf = tk.Frame(self.bc_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        self._bc_card_list = StreamCardList(
            lf, self.root,
            on_play   = lambda t: threading.Thread(target=lambda: self._bc_stream(t), daemon=True).start(),
            on_queue  = None,
            on_detail = None,
            source    = "bandcamp",
        )
        self.bc_list = self._bc_card_list.cv

        self._bc_ctx = tk.Menu(self.bc_frame, tearoff=0, bg=C["panel"], fg=C["white"],
                                activebackground=C["select2"], activeforeground=C["glow"],
                                font=FMS, bd=0, relief="flat")
        self._bc_ctx.add_command(label="▶  Play", command=self._bc_ctx_play)
        self._bc_ctx.add_command(label="⎘  Open in Browser", command=self._bc_ctx_open)

        np = tk.Frame(self.bc_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.bc_np_lbl = tk.Label(np, text="— BANDCAMP —", font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.bc_np_lbl.pack(side="left", padx=16)

    def _bc_refresh_view(self):
        pass

    def _bc_do_search(self):
        q = self.bc_search_var.get().strip()
        if not q:
            return
        self.bc_content_lbl.config(text="Searching Bandcamp…")
        self.bc_list.delete(0, "end")
        self._bc_tracks = []
        threading.Thread(target=lambda: self._bc_run_search(q), daemon=True).start()

    def _bc_run_search(self, q):
        tracks = self.bc_api.search(q, 30)
        self._bc_tracks = tracks
        def _show():
            self.bc_content_lbl.config(text=f"{len(tracks)} tracks found" if tracks else "No results.")
            self._bc_card_list.set_tracks(tracks)
        self.root.after(0, _show)

    def _bc_play_selected(self, event=None):
        sel = self.bc_list.curselection()
        if not sel or not self._bc_tracks:
            return
        track = self._bc_tracks[sel[0]]
        threading.Thread(target=lambda: self._bc_stream(track), daemon=True).start()

    def _bc_rclick(self, event):
        idx = self.bc_list.nearest(event.y)
        if idx >= 0:
            self.bc_list.selection_clear(0, "end")
            self.bc_list.selection_set(idx)
        self._bc_ctx.tk_popup(event.x_root, event.y_root)

    def _bc_ctx_play(self):
        sel = self.bc_list.curselection()
        if sel and self._bc_tracks:
            threading.Thread(target=lambda: self._bc_stream(self._bc_tracks[sel[0]]), daemon=True).start()

    def _bc_ctx_open(self):
        sel = self.bc_list.curselection()
        if sel and self._bc_tracks:
            import webbrowser
            webbrowser.open(self._bc_tracks[sel[0]].get("url", ""))

    def _bc_stream(self, track):
        url_page = track.get("url", "")
        title    = track.get("title", "Unknown")
        artist   = track.get("artist", "Unknown")
        if not url_page:
            self.root.after(0, lambda: self.bc_np_lbl.config(text="  No URL for this track."))
            return
        self.root.after(0, lambda: self.bc_np_lbl.config(text="  Fetching stream…"))
        stream_url, meta = self.bc_api.get_stream_url(url_page)
        if meta:
            title  = meta.get("title") or title
            artist = meta.get("artist") or artist
        if not stream_url:
            self.root.after(0, lambda: self.bc_np_lbl.config(text="  No stream available (track may require purchase)."))
            return
        self.root.after(0, lambda: self.bc_np_lbl.config(text="  Buffering…"))
        try:
            import urllib.request as _ur
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            _ur.urlretrieve(stream_url, tmp.name)

            def _play():
                self._stop_all_sources()
                self._bc_current_track = track
                self._active_source = "bandcamp"
                self._sp_mode = False
                self._set_source_badge("bandcamp")
                if self.engine.load(tmp.name):
                    self._current_play_path = tmp.name
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text="Bandcamp")
                    self.lbl_cur.config(text="0:00")
                    self._draw_prog(0)
                    self.bc_np_lbl.config(text=f"▶  {title[:40]}  —  {artist[:24]}")
                    art_url = track.get("art", "")
                    if art_url:
                        self._set_album_art(art_url)
                    self._history_add({"title": title, "artist": artist, "album": "Bandcamp"}, source="bandcamp")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp.name: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
            self.root.after(0, _play)
        except Exception:
            self.root.after(0, lambda: self.bc_np_lbl.config(text=f"  Error: {ex}"))

