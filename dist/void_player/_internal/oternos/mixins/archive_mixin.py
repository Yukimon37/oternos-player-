"""
archive_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all archive-related methods.
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


class ArchiveMixin:
    """Mixin: archive methods for VoidPlayer."""
    def _build_archive_view(self):
        self.ia_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.ia_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="INTERNET ARCHIVE", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.ia_status_lbl = tk.Label(top, text="[ FREE / OPEN ]", font=FMS, fg=C["white2"], bg=C["bg"])
        self.ia_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.ia_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Search bar
        sf = tk.Frame(self.ia_frame, bg=C["bg"])
        sf.pack(fill="x", pady=(6, 0))
        tk.Label(sf, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.ia_search_var = tk.StringVar()
        ia_entry = tk.Entry(sf, textvariable=self.ia_search_var, font=FM,
                            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                            relief="flat", bd=0, width=38)
        ia_entry.pack(side="left", ipady=4)
        ia_entry.bind("<Return>", lambda e: self._ia_do_search())
        ia_go = tk.Label(sf, text="[GO]", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=8)
        ia_go.pack(side="left")
        ia_go.bind("<Button-1>", lambda e: self._ia_do_search())
        ia_go.bind("<Enter>", lambda e: ia_go.config(fg=C["white"]))
        ia_go.bind("<Leave>", lambda e: ia_go.config(fg=C["white3"]))

        tk.Frame(self.ia_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        # Two-pane: items (top) and files (bottom)
        self.ia_content_lbl = tk.Label(self.ia_frame, text="Search for audio items above",
                                        font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.ia_content_lbl.pack(fill="x", padx=20, pady=(4, 2))

        pane = tk.Frame(self.ia_frame, bg=C["bg"])
        pane.pack(fill="both", expand=True, padx=20, pady=(0, 2))

        # Items list (left/top half)
        items_frame = tk.Frame(pane, bg=C["bg"])
        items_frame.pack(fill="both", expand=True)
        sb1 = tk.Scrollbar(items_frame, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb1.pack(side="right", fill="y")
        self.ia_items_list = tk.Listbox(items_frame, bg=C["bg"], fg=C["white2"],
                                         selectbackground=C["select"], selectforeground=C["white"],
                                         font=FM, relief="flat", bd=0, activestyle="none",
                                         yscrollcommand=sb1.set,
                                         highlightthickness=1, highlightcolor=C["border"],
                                         highlightbackground=C["border"])
        self.ia_items_list.pack(fill="both", expand=True)
        sb1.config(command=self.ia_items_list.yview)
        self.ia_items_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.ia_items_list, e.delta))
        self.ia_items_list.bind("<Button-1>", self._ia_item_click)

        # Files sub-list separator + label
        tk.Frame(self.ia_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(2, 0))
        self.ia_files_lbl = tk.Label(self.ia_frame, text="▸ Select an item to browse its files",
                                      font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.ia_files_lbl.pack(fill="x", padx=20, pady=(2, 0))

        files_frame = tk.Frame(self.ia_frame, bg=C["bg"], height=140)
        files_frame.pack(fill="x", padx=20, pady=(0, 4))
        files_frame.pack_propagate(False)
        sb2 = tk.Scrollbar(files_frame, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb2.pack(side="right", fill="y")
        self.ia_files_list = tk.Listbox(files_frame, bg=C["panel"], fg=C["white2"],
                                         selectbackground=C["select"], selectforeground=C["white"],
                                         font=FMS, relief="flat", bd=0, activestyle="none",
                                         yscrollcommand=sb2.set,
                                         highlightthickness=1, highlightcolor=C["border"],
                                         highlightbackground=C["border"])
        self.ia_files_list.pack(fill="both", expand=True)
        sb2.config(command=self.ia_files_list.yview)
        self.ia_files_list.bind("<Double-Button-1>", self._ia_play_selected)
        self.ia_files_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.ia_files_list, e.delta))

        np = tk.Frame(self.ia_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.ia_np_lbl = tk.Label(np, text="— INTERNET ARCHIVE —", font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.ia_np_lbl.pack(side="left", padx=16)

    def _ia_refresh_view(self):
        pass  # state already in ia_items_list / ia_files_list

    def _ia_do_search(self):
        q = self.ia_search_var.get().strip()
        if not q:
            return
        self.ia_content_lbl.config(text="Searching…")
        self.ia_items_list.delete(0, "end")
        self.ia_files_list.delete(0, "end")
        self._ia_items = []
        self._ia_files = []
        self.ia_files_lbl.config(text="▸ Select an item to browse its files")
        threading.Thread(target=lambda: self._ia_run_search(q), daemon=True).start()

    def _ia_run_search(self, q):
        items = self.ia_api.search(q, 40)
        self._ia_items = items
        def _show():
            self.ia_content_lbl.config(text=f"{len(items)} items found" if items else "No results.")
            self.ia_items_list.delete(0, "end")
            for it in items:
                creator = it.get("creator", "")
                if isinstance(creator, list):
                    creator = creator[0] if creator else ""
                title = it.get("title", it.get("identifier", ""))
                year  = it.get("year", "")
                line  = f"  {title}"
                if creator:
                    line += f"  —  {creator}"
                if year:
                    line += f"  [{year}]"
                self.ia_items_list.insert("end", line)
        self.root.after(0, _show)

    def _ia_item_click(self, event):
        idx = self.ia_items_list.nearest(event.y)
        if idx < 0 or idx >= len(self._ia_items):
            return
        item = self._ia_items[idx]
        ident = item.get("identifier", "")
        self.ia_files_lbl.config(text=f"▸ Loading files for: {ident} …")
        self.ia_files_list.delete(0, "end")
        self._ia_files = []
        threading.Thread(target=lambda: self._ia_load_files(ident), daemon=True).start()

    def _ia_load_files(self, identifier):
        files = self.ia_api.get_audio_files(identifier)
        self._ia_files = [(identifier, f) for f in files]
        def _show():
            self.ia_files_list.delete(0, "end")
            if not files:
                self.ia_files_lbl.config(text="▸ No audio files found in this item.")
                return
            self.ia_files_lbl.config(text=f"▸ {len(files)} audio files  —  double-click to play")
            for f in files:
                name = f.get("name", "")
                size_b = int(f.get("size", 0) or 0)
                size_s = f"{size_b//1024//1024}MB" if size_b > 1024*1024 else f"{size_b//1024}KB"
                length = f.get("length", "")
                line = f"  {name}"
                if length:
                    try:
                        s = int(float(length))
                        line += f"  [{s//60}:{s%60:02d}]"
                    except Exception:
                        pass
                line += f"  ({size_s})"
                self.ia_files_list.insert("end", line)
        self.root.after(0, _show)

    def _ia_play_selected(self, event=None):
        sel = self.ia_files_list.curselection()
        if not sel or not self._ia_files:
            return
        idx = sel[0]
        if idx >= len(self._ia_files):
            return
        identifier, fdata = self._ia_files[idx]
        filename = fdata.get("name", "")
        stream_url = self.ia_api.stream_url(identifier, filename)
        title  = filename.rsplit(".", 1)[0].replace("_", " ")
        # Try to get creator from items list
        artist = ""
        for it in self._ia_items:
            if it.get("identifier") == identifier:
                c = it.get("creator", "")
                artist = (c[0] if isinstance(c, list) else c) or ""
                break
        threading.Thread(target=lambda: self._ia_stream(stream_url, title, artist, identifier, filename), daemon=True).start()

    def _ia_stream(self, stream_url, title, artist, identifier, filename):
        self.root.after(0, lambda: self.ia_np_lbl.config(text="  Buffering…"))
        try:
            import urllib.request as _ur
            ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp.close()
            _ur.urlretrieve(stream_url, tmp.name)

            def _play():
                self._stop_all_sources()
                self._ia_current = {"identifier": identifier, "file": filename, "title": title, "artist": artist}
                self._active_source = "archive"
                self._sp_mode = False
                self._set_source_badge("archive")
                if self.engine.load(tmp.name):
                    self._current_play_path = tmp.name
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist or "Internet Archive")
                    self.now_album.config(text=identifier)
                    self.lbl_cur.config(text="0:00")
                    self._draw_prog(0)
                    self.ia_np_lbl.config(text=f"▶  {title[:44]}  —  {artist[:24]}")
                    self._history_add({"title": title, "artist": artist or "Internet Archive", "album": identifier}, source="archive")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp.name: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
            self.root.after(0, _play)
        except Exception:
            self.root.after(0, lambda: self.ia_np_lbl.config(text=f"  Error: {ex}"))

    # ══════════════════════════════════════════════════════
    #  BANDCAMP VIEW
    # ══════════════════════════════════════════════════════
