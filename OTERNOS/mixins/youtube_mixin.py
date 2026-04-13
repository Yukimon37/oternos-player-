"""
youtube_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all youtube-related methods.
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
    from oternos.stream_cards import normalise, _open_tk_detail, _open_webview_detail, _WEBVIEW_OK
else:
    from ..stream_cards import normalise, _open_tk_detail, _open_webview_detail, _WEBVIEW_OK


class YoutubeMixin:
    """Mixin: youtube methods for VoidPlayer."""
    def _yt_show_dropdown(self, widget):
        """Show SEARCH / SAVED dropdown under the YOUTUBE tab button."""
        try:
            if (
                hasattr(self, "_yt_dropdown")
                and self._yt_dropdown
                and self._yt_dropdown.winfo_exists()
            ):
                return
        except Exception:
            pass
        dd = tk.Frame(
            self.root,
            bg=C["panel"],
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        self._yt_dropdown = dd
        x = widget.winfo_rootx() - self.root.winfo_rootx()
        y = widget.winfo_rooty() - self.root.winfo_rooty() + widget.winfo_height()
        dd.place(x=x, y=y, width=90)

        def _btn(text, cmd):
            b = tk.Label(
                dd,
                text=text,
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                anchor="w",
                padx=8,
                pady=3,
            )
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e: (self._yt_close_dropdown(), cmd()))
            b.bind("<Enter>", lambda e: b.config(fg=C["white"], bg=C["select2"]))
            b.bind("<Leave>", lambda e: b.config(fg=C["white3"], bg=C["panel"]))

        _btn("/ SEARCH", lambda: self._yt_set_subview("search"))
        _btn("* SAVED", lambda: self._yt_set_subview("saved"))

        # Auto-close when mouse leaves dropdown
        def _leave(e):
            try:
                wx, wy = dd.winfo_rootx(), dd.winfo_rooty()
                ww, wh = dd.winfo_width(), dd.winfo_height()
                mx, my = e.x_root, e.y_root
                if not (wx <= mx <= wx + ww and wy <= my <= wy + wh):
                    self._yt_close_dropdown()
            except Exception:
                pass

        dd.bind("<Leave>", _leave)

        # Poll to close if mouse leaves both button and dropdown
        def _poll_close():
            try:
                if (
                    getattr(self, "_yt_dropdown", None)
                    and self._yt_dropdown.winfo_exists()
                ):
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
            dx = dd.winfo_x()
            dy = dd.winfo_y()
            dw = dd.winfo_width()
            dh = dd.winfo_height()
            # Also check if mouse is over the YOUTUBE tab button
            yt_btn = self.tab_btns.get("youtube")
            over_btn = False
            if yt_btn:
                bx = yt_btn.winfo_x()
                by = yt_btn.winfo_y()
                bw = yt_btn.winfo_width()
                bh = yt_btn.winfo_height()
                over_btn = bx <= mx <= bx + bw and by <= my <= by + bh
            over_dd = dx <= mx <= dx + dw and dy <= my <= dy + dh
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
            self.yt_content_lbl.config(
                text="No saved tracks yet — search and click ★ to save"
            )
            self._yt_tracks = []
            self._yt_clear_list()
            return
        self.yt_content_lbl.config(
            text=f"{len(saved)} saved tracks  —  double-click to play"
        )
        self._yt_tracks = saved
        self._yt_render_list()
        for i, t in enumerate(saved):
            vid_id = t.get("id", "")
            if vid_id:
                url = f"https://i.ytimg.com/vi/{vid_id}/default.jpg"
                threading.Thread(
                    target=self._yt_fetch_thumb, args=(i, url), daemon=True
                ).start()

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

    def _build_youtube_view(self):
        self.yt_frame = tk.Frame(self.content, bg=C["bg"])

        # Header
        top = tk.Frame(self.yt_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="YOUTUBE", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        self.yt_status_lbl = tk.Label(
            top, text="", font=FMS, fg=C["white3"], bg=C["bg"]
        )
        self.yt_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.yt_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Search bar (named so we can hide it in SAVED view)
        sf = tk.Frame(self.yt_frame, bg=C["bg"])
        self.yt_search_frame = sf
        sf.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(
            sf, text="⌕", font=("Courier New", 11), fg=C["white3"], bg=C["bg"]
        ).pack(side="left", padx=(0, 6))
        self.yt_search_var = tk.StringVar()
        self.yt_search_entry = tk.Entry(
            sf,
            textvariable=self.yt_search_var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            width=44,
        )
        self.yt_search_entry.pack(side="left", ipady=4)
        self.yt_search_entry.bind(
            "<Return>", lambda e: (self._yt_do_search(), "break")[1]
        )
        go = tk.Label(
            sf, text="GO", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=10
        )
        go.pack(side="left")
        go.bind("<Button-1>", lambda e: self._yt_do_search())
        go.bind("<Enter>", lambda e: go.config(fg=C["white"]))
        go.bind("<Leave>", lambda e: go.config(fg=C["white3"]))
        tk.Frame(self.yt_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(6, 0)
        )

        # Status / now-playing — pack bottom FIRST
        self.yt_np_lbl = tk.Label(
            self.yt_frame, text="", font=FMS, fg=C["white3"], bg=C["bg"], anchor="w"
        )
        self.yt_np_lbl.pack(side="bottom", fill="x", padx=20, pady=(0, 6))

        self.yt_content_lbl = tk.Label(
            self.yt_frame,
            text="Search for music above",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            anchor="w",
        )
        self.yt_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        # Loading bar + cancel button — hidden until a track is loading
        self._yt_load_bar_frame = tk.Frame(self.yt_frame, bg=C["bg"])
        self._yt_load_bar_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._yt_load_canvas = tk.Canvas(
            self._yt_load_bar_frame, height=3, bg=C["panel"], highlightthickness=0
        )
        self._yt_load_canvas.pack(side="left", fill="x", expand=True)
        self._yt_cancel_btn = tk.Label(
            self._yt_load_bar_frame,
            text="✕ cancel",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
            padx=8,
        )
        self._yt_cancel_btn.pack(side="right")
        self._yt_cancel_btn.bind("<Button-1>", lambda e: self._yt_cancel())
        self._yt_cancel_btn.bind(
            "<Enter>", lambda e: self._yt_cancel_btn.config(fg=C["red"])
        )
        self._yt_cancel_btn.bind(
            "<Leave>", lambda e: self._yt_cancel_btn.config(fg=C["white3"])
        )
        self._yt_load_bar_frame.pack_forget()  # hidden by default
        self._yt_load_anim_pos = 0.0
        self._yt_load_anim_job = None
        self._yt_cancelled = False
        self._yt_subview = "search"
        self._yt_dropdown = None

        # Canvas list — supports thumbnails
        lf = tk.Frame(self.yt_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb2 = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0
        )
        sb2.pack(side="right", fill="y")
        self.yt_list_cv = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=sb2.set
        )
        self.yt_list_cv.pack(side="left", fill="both", expand=True)
        sb2.config(command=self.yt_list_cv.yview)
        self.yt_list_cv.bind(
            "<MouseWheel>",
            lambda e: self.yt_list_cv.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )
        self.yt_list_cv.bind("<Double-Button-1>", self._yt_play_selected)
        self.yt_list_cv.bind("<Button-3>", self._yt_rclick)
        self.yt_list_cv.bind("<Button-1>", self._yt_list_click)
        self.yt_list_cv.bind("<Configure>", self._yt_list_resize)
        self._yt_row_height = 52
        self._yt_thumb_cache = {}
        self._yt_selected_idx = -1
        self._yt_list_width = 0
        # Keep yt_list as alias for legacy references (e.g. scroll routing)
        self.yt_list = self.yt_list_cv

    def _yt_refresh_view(self):
        if not self.yt_api.ytdlp_available():
            self.yt_status_lbl.config(
                text="yt-dlp not installed  —  run:  pip install yt-dlp", fg=C["red"]
            )
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
        self._yt_load_canvas.create_rectangle(
            0, 0, fill_w, 3, fill=C["white"], outline=""
        )

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
        self._yt_load_canvas.create_rectangle(
            0, 0, fill_w, 3, fill=C["white3"], outline=""
        )
        # Small bright leading edge
        edge = min(w, fill_w + 6)
        self._yt_load_canvas.create_rectangle(
            fill_w, 0, edge, 3, fill=C["white"], outline=""
        )
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
            max(0, x1), 0, min(w, x2), 3, fill=C["white"], outline=""
        )
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
                text="yt-dlp not installed  —  run:  pip install yt-dlp"
            )
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
                        text="No results — try updating yt-dlp:  pip install -U yt-dlp"
                    )
                    self._yt_clear_list()
                    return
                self.yt_content_lbl.config(
                    text=f"{len(tracks)} results  —  double-click to play"
                )
                self._yt_tracks = tracks
                self._yt_render_list()
                # Kick off thumbnail fetches
                for i, t in enumerate(tracks):
                    vid_id = t.get("id", "")
                    if vid_id:
                        url = f"https://i.ytimg.com/vi/{vid_id}/default.jpg"
                        threading.Thread(
                            target=self._yt_fetch_thumb, args=(i, url), daemon=True
                        ).start()

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
            import time as _t

            _t.sleep(0.15)
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
        self._yt_thumb_cache = {}
        self._yt_selected_idx = -1

    def _yt_render_list(self):
        cv = self.yt_list_cv
        cv.delete("all")
        if not self._yt_tracks:
            cv.create_text(
                20, 20, text="No results.", anchor="nw", font=FM, fill=C["white3"]
            )
            cv.configure(scrollregion=(0, 0, 100, 40))
            return
        RH = self._yt_row_height
        W = max(self._yt_list_width, cv.winfo_width(), 400)
        cv.configure(scrollregion=(0, 0, W, RH * len(self._yt_tracks)))
        for i, t in enumerate(self._yt_tracks):
            self._yt_draw_row(i, t, W)

    def _yt_draw_row(self, i, t, W=None):
        cv = self.yt_list_cv
        RH = self._yt_row_height
        if W is None:
            W = max(self._yt_list_width, cv.winfo_width(), 400)
        y0 = i * RH
        y1 = y0 + RH
        tag = f"ytrow{i}"
        cv.delete(tag)
        bg = (
            C["select"]
            if i == self._yt_selected_idx
            else (C["panel2"] if i % 2 == 0 else C["bg"])
        )
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)
        TH = RH - 8
        # Thumbnail placeholder
        cv.create_rectangle(
            4, y0 + 4, 4 + TH, y1 - 4, fill=C["panel"], outline="", tags=tag
        )
        if i in self._yt_thumb_cache:
            cv.create_image(
                4, y0 + 4, image=self._yt_thumb_cache[i], anchor="nw", tags=tag
            )
        else:
            cv.create_text(
                4 + TH // 2,
                y0 + RH // 2,
                text="▶",
                font=("Courier New", 10),
                fill=C["white3"],
                anchor="center",
                tags=tag,
            )
        # Save star button (right side)
        vid_id = t.get("id", "")
        is_saved = self._yt_is_saved(vid_id)
        star_x = W - 24
        star_col = "#f0c040" if is_saved else C["white3"]
        star_tag = f"ytstar{i}"
        cv.delete(star_tag)
        cv.create_text(
            star_x,
            y0 + RH // 2,
            text="★",
            font=("Courier New", 13),
            fill=star_col,
            anchor="center",
            tags=(tag, star_tag),
        )
        cv.tag_bind(
            star_tag, "<Button-1>", lambda e, tr=t, idx=i: self._yt_toggle_save(tr, idx)
        )
        cv.tag_bind(
            star_tag,
            "<Enter>",
            lambda e, st=star_tag: cv.itemconfig(st, fill="#f0c040"),
        )
        cv.tag_bind(
            star_tag,
            "<Leave>",
            lambda e, st=star_tag, sv=is_saved: cv.itemconfig(
                st, fill="#f0c040" if sv else C["white3"]
            ),
        )
        # Title and channel (leave room for star)
        title = (t.get("title") or "Unknown")[:58]
        channel = (t.get("channel") or "")[:35]
        dur = int(t.get("duration") or 0)
        dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else ""
        tx = 4 + TH + 8
        cv.create_text(
            tx,
            y0 + RH // 2 - 8,
            text=title,
            font=("Courier New", 9, "bold"),
            fill=C["white"],
            anchor="w",
            tags=tag,
        )
        sub = f"{channel}  {dur_str}".strip()
        cv.create_text(
            tx,
            y0 + RH // 2 + 8,
            text=sub,
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )
        cv.create_line(0, y1 - 1, W, y1 - 1, fill=C["border"], tags=tag)

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
            import urllib.request as _ur
            import tempfile

            data = _ur.urlopen(url, timeout=6).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
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
                import os

                os.unlink(path)
            except Exception:
                pass

    def _yt_open_detail(self, idx):
        if not self._yt_tracks or idx < 0 or idx >= len(self._yt_tracks):
            return
        t = self._yt_tracks[idx]
        n = normalise(t, "youtube")
        if _WEBVIEW_OK:
            import threading
            threading.Thread(target=_open_webview_detail, args=(n,"youtube"), daemon=True).start()
        else:
            _open_tk_detail(self.root, n, "youtube",
                on_play=lambda: threading.Thread(target=lambda: self._yt_play_track(t), daemon=True).start())

    def _yt_rclick(self, event):
        canvas_y = self.yt_list_cv.canvasy(event.y)
        idx = int(canvas_y // self._yt_row_height)
        if idx < 0 or idx >= len(self._yt_tracks):
            return
        track = self._yt_tracks[idx]
        menu = tk.Menu(
            self.root,
            bg=C["panel"],
            fg=C["white"],
            activebackground=C["select2"],
            activeforeground=C["white"],
            font=FM,
            tearoff=0,
            bd=0,
            relief="flat",
        )
        menu.add_command(label="▶ Play", command=lambda t=track: self._yt_play_track(t))
        menu.add_separator()
        menu.add_command(
            label="⬇  Save to Library",
            command=lambda t=track: self._yt_ctx_save(t),
        )
        menu.add_separator()
        menu.add_command(
            label="Open in browser",
            command=lambda: webbrowser.open(
                f"https://www.youtube.com/watch?v={track.get('id', '')}"
            ),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _yt_ctx_save(self, track):
        """Download (or reuse cached) YouTube track and save it into the library."""
        vid_id  = track.get("id", "")
        title   = (track.get("title")   or "track").replace("/", "-").replace("\\", "-")
        channel = (track.get("channel") or "Unknown").replace("/", "-").replace("\\", "-")
        if not vid_id:
            return

        cached_mp3 = YT_CACHE / f"{vid_id}.mp3"
        cached_m4a = YT_CACHE / f"{vid_id}.m4a"

        def _do():
            import time as _t
            import shutil as _sh

            # ── Step 1: ensure we have a local file ─────────────────────────
            if cached_mp3.exists():
                src = cached_mp3
            elif cached_m4a.exists():
                src = cached_m4a
            else:
                # Not cached yet — trigger the normal stream (which downloads
                # to cache), then wait for the cache file to appear.
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"  \u2b07 Downloading for library: {title[:40]}\u2026"
                    ),
                )
                self.root.after(0, lambda t=track: self._yt_play_track(t))
                deadline = _t.monotonic() + 120
                src = None
                while _t.monotonic() < deadline:
                    if cached_mp3.exists():
                        src = cached_mp3
                        break
                    if cached_m4a.exists():
                        src = cached_m4a
                        break
                    _t.sleep(0.5)
                if src is None:
                    self.root.after(
                        0,
                        lambda: self.yt_content_lbl.config(
                            text="  \u2b07 Save failed \u2014 could not download audio."
                        ),
                    )
                    return

            # ── Step 2: copy to Music / watch_dir ───────────────────────────
            dirs = self.settings.get("watch_dirs", [])
            save_dir = Path(dirs[0]) if dirs else Path.home() / "Music"
            save_dir.mkdir(parents=True, exist_ok=True)
            ext  = src.suffix
            dest = save_dir / f"{channel} - {title}{ext}"
            counter = 1
            while dest.exists():
                dest = save_dir / f"{channel} - {title} ({counter}){ext}"
                counter += 1
            _sh.copy2(str(src), str(dest))

            # ── Step 3: import into library ──────────────────────────────────
            dest_str  = str(dest)
            dest_name = dest.name
            self.root.after(
                0,
                lambda d=dest_str, n=dest_name: (
                    self._import([d]),
                    self.yt_content_lbl.config(text=f"  \u2713 Saved & imported: {n}"),
                ),
            )

        import threading as _th
        _th.Thread(target=_do, daemon=True).start()

    def _yt_stream(self, track):
        vid_id = track.get("id", "")
        title = track.get("title", "Unknown")
        channel = track.get("channel", "Unknown")
        dur_s = int(track.get("duration") or 0)
        if not vid_id:
            return

        self.root.after(0, self._yt_load_start)

        try:
            # Check cache for any previously downloaded format
            cached_mp3 = YT_CACHE / f"{vid_id}.mp3"
            cached_m4a = YT_CACHE / f"{vid_id}.m4a"

            if cached_mp3.exists():
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"Loading (cached): {title[:50]} ..."
                    ),
                )
                out_file = str(cached_mp3)

            elif cached_m4a.exists():
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"Loading (cached): {title[:50]} ..."
                    ),
                )
                out_file = str(cached_m4a)

            else:
                # Download m4a directly — no ffmpeg needed at all
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"Loading: {title[:60]} ..."
                    ),
                )

                import yt_dlp
                import tempfile as _tf
                import shutil

                tmp_dir = _tf.mkdtemp()

                def _progress_hook(d):
                    if d.get("status") == "downloading":
                        downloaded = d.get("downloaded_bytes") or 0
                        total = (
                            d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                        )
                        if total > 0:
                            pct = int(downloaded / total * 100)
                            self.root.after(
                                0,
                                lambda p=pct: (
                                    self.yt_content_lbl.config(
                                        text=f"Downloading: {title[:40]} ... {p}%"
                                    ),
                                    self._yt_set_load_progress(p / 100),
                                ),
                            )

                import sys as _sys
                import os as _os
                import shutil as _sh

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
                _ff_candidates += [
                    r"C:\\ffmpeg\\bin",
                    r"C:\\Program Files\\ffmpeg\\bin",
                    r"C:\\Program Files (x86)\\ffmpeg\\bin",
                    _os.path.join(
                        _os.environ.get("LOCALAPPDATA", ""), "Programs", "ffmpeg", "bin"
                    ),
                    _os.path.join(_os.environ.get("USERPROFILE", ""), "ffmpeg", "bin"),
                ]
                for _d in _ff_candidates:
                    if _d and _os.path.isfile(_os.path.join(_d, "ffmpeg.exe")):
                        _ffmpeg_dir = _d
                        break
                if not _ffmpeg_dir:
                    _path_ff = _sh.which("ffmpeg")
                    if _path_ff:
                        _ffmpeg_dir = _os.path.dirname(_path_ff)
                if not _ffmpeg_dir:
                    self.root.after(
                        0,
                        lambda: self.yt_content_lbl.config(
                            text="ffmpeg not found — run:  winget install ffmpeg"
                        ),
                    )
                    self.root.after(0, self._yt_load_stop)
                    return
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "format": "bestaudio/best",
                    "outtmpl": str(Path(tmp_dir) / f"{vid_id}.%(ext)s"),
                    "progress_hooks": [_progress_hook],
                    "ffmpeg_location": _ffmpeg_dir,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }

                import datetime

                logpath = Path.home() / "voidplayer_error.log"
                try:
                    with open(logpath, "a", encoding="utf-8") as _lf:
                        _lf.write(
                            f"[{datetime.datetime.now()}] ffmpeg_dir={_ffmpeg_dir!r} candidates={_ff_candidates}\n"
                        )
                except Exception:
                    pass

                # ── Age-restriction bypass strategy ────────────────────────
                # 1. tv_embedded / web_embedded player clients — bypass age gate
                #    without any login (YouTube's TV/embedded players don't enforce it)
                # 2. User-supplied cookies.txt if provided in Settings
                # 3. Standard no-cookies attempt (works for most normal videos)
                info = None
                _yt_cookies_path = self.settings.get("yt_cookies_path", "").strip()

                def _try_download(extra_opts):
                    opts = dict(ydl_opts)
                    opts.update(extra_opts)
                    opts["quiet"] = True
                    opts["no_warnings"] = True
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(
                            f"https://www.youtube.com/watch?v={vid_id}", download=True
                        )

                # Pass 1: tv_embedded client — bypasses age gate without login
                for _client in ("tv_embedded", "web_embedded"):
                    try:
                        info = _try_download(
                            {
                                "extractor_args": {
                                    "youtube": {"player_client": [_client]}
                                }
                            }
                        )
                        if info:
                            break
                    except Exception:
                        pass

                # Pass 2: cookies.txt if user provided one
                if (
                    info is None
                    and _yt_cookies_path
                    and Path(_yt_cookies_path).exists()
                ):
                    try:
                        info = _try_download({"cookiefile": _yt_cookies_path})
                    except Exception:
                        pass

                # Pass 3: standard download (no special options)
                if info is None:
                    try:
                        info = _try_download({})
                    except Exception as _e:
                        err_str = str(_e).lower()
                        if (
                            "sign in" in err_str
                            or "age" in err_str
                            or "inappropriate" in err_str
                        ):
                            raise Exception(
                                "Age-restricted video — bypass failed.\n\n"
                                "To fix: Settings → YouTube → cookies.txt → BROWSE\n"
                                "Export cookies.txt from the 'Get cookies.txt LOCALLY' browser extension\n"
                                "while logged into YouTube."
                            )
                        raise

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
                        _lf.write(
                            f"[{datetime.datetime.now()}] Final ext={actual_ext} size={tmp_file.stat().st_size}\n"
                        )
                except Exception:
                    pass

                dest = YT_CACHE / f"{vid_id}{actual_ext}"
                shutil.move(str(tmp_file), str(dest))
                out_file = str(dest)

            def _play(f=out_file, d=dur_s):
                self._yt_load_stop()
                self._stop_all_sources()
                self._yt_current_track = track  # remember for repeat
                self._active_source = "youtube"
                self._sp_mode = False
                self._set_source_badge("youtube")
                ok = self.engine.load(f)
                if ok:
                    self._current_play_path = f
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
                    self._history_add(
                        {"title": title, "artist": channel, "album": "YouTube"},
                        source="youtube",
                    )
                    # Sync visualizer — reset state and start FFT decoder like _do_load_track does
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(
                        target=lambda p=f: self._start_fft_file_decoder(p), daemon=True
                    ).start()
                    # Fetch lyrics + start ticker — same as _do_load_track
                    self._set_current_track_for_lyrics(channel, title)
                    self._start_lyric_ticker()
                    if getattr(self, "view", "") == "lyrics":
                        self._refresh_lyrics_view()
                else:
                    # MCI can't play this format — user needs K-Lite Codec Pack
                    self.yt_content_lbl.config(
                        text="Playback error — install K-Lite Codec Pack to play YouTube audio: codecguide.com/download_kl.htm"
                    )

            if not getattr(self, "_yt_cancelled", False):
                self.root.after(0, _play)

        except ImportError:
            self.root.after(0, self._yt_load_stop)
            self.root.after(
                0,
                lambda: self.yt_content_lbl.config(
                    text="yt-dlp not installed  —  run: pip install yt-dlp"
                ),
            )
        except Exception as ex:
            import traceback
            import datetime

            err = str(ex)
            tb = traceback.format_exc()
            try:
                logpath = Path.home() / "voidplayer_error.log"
                with open(logpath, "a", encoding="utf-8") as _lf:
                    _lf.write("\n[" + str(datetime.datetime.now()) + "]\n" + tb + "\n")
            except Exception:
                pass
            self.root.after(0, self._yt_load_stop)
            self.root.after(
                0, lambda: self.yt_content_lbl.config(text=f"Error: {err[:120]}")
            )

    # ── CLAUDE DEBUG VIEW ─────────────────
    # ── STREAM VIEW (YouTube + SoundCloud combined) ──
