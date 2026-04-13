"""
deezer_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all deezer-related methods.
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


class DeezerMixin:
    """Mixin: deezer methods for VoidPlayer."""
    def _build_deezer_view(self):
        self.dz_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.dz_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="DEEZER", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.dz_status_lbl = tk.Label(top, text="[ 30s PREVIEWS ]", font=FMS, fg=C["white2"], bg=C["bg"])
        self.dz_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.dz_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Nav
        nav = tk.Frame(self.dz_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(6, 0))
        self._dz_nav_btns = {}
        for label, key in [("SEARCH", "search"), ("CHARTS", "chart")]:
            b = tk.Label(nav, text=label, font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=10)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._dz_nav(k))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))
            self._dz_nav_btns[key] = b
        self._dz_nav_btns["search"].config(fg=C["white"])

        # Search bar
        self.dz_search_frame = tk.Frame(self.dz_frame, bg=C["bg"])
        self.dz_search_frame.pack(fill="x", pady=(4, 0))
        tk.Label(self.dz_search_frame, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.dz_search_var = tk.StringVar()
        dz_entry = tk.Entry(self.dz_search_frame, textvariable=self.dz_search_var,
                            font=FM, bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                            relief="flat", bd=0, width=40)
        dz_entry.pack(side="left", ipady=4)
        dz_entry.bind("<Return>", lambda e: self._dz_do_search())
        dz_go = tk.Label(self.dz_search_frame, text="[GO]", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=8)
        dz_go.pack(side="left")
        dz_go.bind("<Button-1>", lambda e: self._dz_do_search())
        dz_go.bind("<Enter>", lambda e: dz_go.config(fg=C["white"]))
        dz_go.bind("<Leave>", lambda e: dz_go.config(fg=C["white3"]))

        tk.Frame(self.dz_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))
        self.dz_content_lbl = tk.Label(self.dz_frame, text="Search for tracks above",
                                        font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.dz_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        lf = tk.Frame(self.dz_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        self._dz_card_list = StreamCardList(
            lf, self.root,
            on_play   = lambda t: threading.Thread(target=lambda: self._dz_stream(t), daemon=True).start(),
            on_queue  = None,
            on_detail = None,
            source    = "deezer",
        )
        self.dz_list = self._dz_card_list.cv

        self._dz_ctx = tk.Menu(self.dz_frame, tearoff=0, bg=C["panel"], fg=C["white"],
                                activebackground=C["select2"], activeforeground=C["glow"],
                                font=FMS, bd=0, relief="flat")
        self._dz_ctx.add_command(label="▶  Play preview", command=self._dz_ctx_play)

        np = tk.Frame(self.dz_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.dz_np_lbl = tk.Label(np, text="— DEEZER —", font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.dz_np_lbl.pack(side="left", padx=16)

    def _dz_nav(self, key):
        self._dz_view = key
        for k, b in self._dz_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        if key == "search":
            self.dz_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.dz_search_frame.pack_forget()
        self._dz_refresh_view()

    def _dz_refresh_view(self):
        view = getattr(self, "_dz_view", "search")
        if view == "chart" and not self._dz_tracks:
            self.dz_content_lbl.config(text="Loading chart…")
            threading.Thread(target=self._dz_load_chart, daemon=True).start()
        elif view == "search":
            self.dz_content_lbl.config(text="Search for tracks above" if not self._dz_tracks else f"{len(self._dz_tracks)} results")
        self._dz_populate()

    def _dz_load_chart(self):
        tracks = self.dz_api.chart(50)
        self._dz_tracks = tracks
        self.root.after(0, lambda: (
            self.dz_content_lbl.config(text=f"{len(tracks)} tracks"),
            self._dz_populate(),
        ))

    def _dz_do_search(self):
        q = self.dz_search_var.get().strip()
        if not q:
            return
        self.dz_content_lbl.config(text="Searching…")
        self.dz_list.delete(0, "end")
        self._dz_tracks = []
        threading.Thread(target=lambda: self._dz_run_search(q), daemon=True).start()

    def _dz_run_search(self, q):
        tracks = self.dz_api.search(q, 50)
        self._dz_tracks = tracks
        self.root.after(0, lambda: (
            self.dz_content_lbl.config(text=f"{len(tracks)} results" if tracks else "No results."),
            self._dz_populate(),
        ))

    def _dz_populate(self):
        self._dz_card_list.set_tracks(self._dz_tracks)
        return
        for t in self._dz_tracks:  # legacy dead code below
            artist = (t.get("artist") or {}).get("name", "") or t.get("artist_name", "")
            title  = t.get("title", t.get("title_short", ""))
            dur    = t.get("duration", 0)
            dur_s  = f"{dur//60}:{dur%60:02d}" if dur else ""
            preview = t.get("preview", "")
            flag   = " ▸" if preview else " ✕"
            self.dz_list.insert("end", f"  {title}  —  {artist}  [{dur_s}]{flag}")

    def _dz_play_selected(self, event=None):
        sel = self.dz_list.curselection()
        if not sel or not self._dz_tracks:
            return
        track = self._dz_tracks[sel[0]]
        threading.Thread(target=lambda: self._dz_stream(track), daemon=True).start()

    def _dz_rclick(self, event):
        idx = self.dz_list.nearest(event.y)
        if idx >= 0:
            self.dz_list.selection_clear(0, "end")
            self.dz_list.selection_set(idx)
        self._dz_ctx.tk_popup(event.x_root, event.y_root)

    def _dz_ctx_play(self):
        sel = self.dz_list.curselection()
        if sel and self._dz_tracks:
            threading.Thread(target=lambda: self._dz_stream(self._dz_tracks[sel[0]]), daemon=True).start()

    def _dz_stream(self, track):
        preview_url = track.get("preview", "")
        if not preview_url:
            self.root.after(0, lambda: self.dz_np_lbl.config(text="  No preview available for this track."))
            return
        artist  = (track.get("artist") or {}).get("name", "") or track.get("artist_name", "Unknown")
        title   = track.get("title", track.get("title_short", "Unknown"))
        album   = (track.get("album") or {}).get("title", "Deezer")
        dur_s   = track.get("duration", 30)
        art_url = (track.get("album") or {}).get("cover_medium", "")

        self.root.after(0, lambda: self.dz_np_lbl.config(text="  Buffering preview…"))
        try:
            import urllib.request as _ur
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            _ur.urlretrieve(preview_url, tmp.name)

            def _play():
                self._stop_all_sources()
                self._dz_current_track = track
                self._active_source = "deezer"
                self._sp_mode = False
                self._set_source_badge("deezer")
                if self.engine.load(tmp.name):
                    self._current_play_path = tmp.name
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text=album)
                    self.engine.duration = float(dur_s)
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=f"{dur_s//60}:{dur_s%60:02d}")
                    self._draw_prog(0)
                    self.dz_np_lbl.config(text=f"▶  {title[:40]}  —  {artist[:24]}  [30s preview]")
                    if art_url:
                        self._set_album_art(art_url)
                    self._history_add({"title": title, "artist": artist, "album": album}, source="deezer")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp.name: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
            self.root.after(0, _play)
        except Exception:
            self.root.after(0, lambda: self.dz_np_lbl.config(text=f"  Error: {ex}"))

    # ══════════════════════════════════════════════════════
    #  INTERNET ARCHIVE VIEW
    # ══════════════════════════════════════════════════════
