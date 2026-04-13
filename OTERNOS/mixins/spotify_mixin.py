"""
spotify_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all spotify-related methods.
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


class SpotifyMixin:
    """Mixin: spotify methods for VoidPlayer."""
    def _build_spotify_view(self):
        self.sp_frame = tk.Frame(self.content, bg=C["bg"])

        # Top bar: header + login status
        top = tk.Frame(self.sp_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="SPOTIFY", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        self.sp_status_lbl = tk.Label(
            top, text="[ NOT CONNECTED ]", font=FMS, fg=C["white2"], bg=C["bg"]
        )
        self.sp_status_lbl.pack(side="left", padx=12)
        self.sp_login_btn = tk.Label(
            top, text="CONNECT", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2"
        )
        self.sp_login_btn.pack(side="right", padx=4)
        self.sp_login_btn.bind("<Button-1>", lambda e: self._sp_login())
        self.sp_login_btn.bind(
            "<Enter>", lambda e: self.sp_login_btn.config(fg=C["white"])
        )
        self.sp_login_btn.bind(
            "<Leave>", lambda e: self.sp_login_btn.config(fg=C["white3"])
        )

        tk.Frame(self.sp_frame, bg=C["border"], height=1).pack(
            fill="x", padx=0, pady=(8, 0)
        )

        # Sub-nav row
        nav = tk.Frame(self.sp_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(8, 0))
        self._sp_nav_btns = {}
        for label, key in [("HOME", "home"), ("LIKED", "liked"), ("SEARCH", "search")]:
            b = tk.Label(
                nav,
                text=label,
                font=FMS,
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
                padx=10,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._sp_nav(k))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))
            self._sp_nav_btns[key] = b
        # Device picker button
        dev_btn = tk.Label(
            nav,
            text="[ DEVICES ]",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
            padx=10,
        )
        dev_btn.pack(side="right")
        dev_btn.bind("<Button-1>", lambda e: self._sp_show_devices())
        dev_btn.bind("<Enter>", lambda e: dev_btn.config(fg=C["white"]))
        dev_btn.bind("<Leave>", lambda e: dev_btn.config(fg=C["white3"]))

        # Search bar (hidden until search nav selected)
        self.sp_search_frame = tk.Frame(self.sp_frame, bg=C["bg"])
        tk.Label(
            self.sp_search_frame,
            text="⌕",
            font=("Courier New", 12),
            fg=C["white3"],
            bg=C["bg"],
        ).pack(side="left", padx=(20, 4))
        self.sp_search_var = tk.StringVar()
        self.sp_search_entry = tk.Entry(
            self.sp_search_frame,
            textvariable=self.sp_search_var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            width=40,
        )
        self.sp_search_entry.pack(side="left", ipady=4)
        self.sp_search_entry.bind(
            "<Return>", lambda e: (self._sp_do_search(), "break")[1]
        )
        go = tk.Label(
            self.sp_search_frame,
            text="[GO]",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
            padx=8,
        )
        go.pack(side="left")
        go.bind("<Button-1>", lambda e: self._sp_do_search())

        tk.Frame(self.sp_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(6, 0)
        )

        # Content label
        self.sp_content_lbl = tk.Label(
            self.sp_frame,
            text="",
            font=("Courier New", 7, "bold"),
            fg=C["white3"],
            bg=C["bg"],
            anchor="w",
        )
        self.sp_content_lbl.pack(fill="x", padx=20, pady=(8, 2))

        # Track list
        lf = tk.Frame(self.sp_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0
        )
        sb.pack(side="right", fill="y")
        self.sp_list_cv = tk.Canvas(
            lf,
            bg=C["bg"],
            highlightthickness=1,
            highlightbackground=C["border"],
            yscrollcommand=sb.set,
        )
        self.sp_list_cv.pack(fill="both", expand=True)
        sb.config(command=self.sp_list_cv.yview)
        self.sp_list_cv.bind(
            "<MouseWheel>",
            lambda e: self.sp_list_cv.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_play_selected)
        self.sp_list_cv.bind("<Button-3>", self._sp_rclick)
        self.sp_list_cv.bind("<Button-1>", self._sp_list_click)
        self._sp_row_height = 64
        self._sp_thumb_cache = {}  # url -> PhotoImage
        self._sp_selected_idx = -1
        self._sp_list_width = 0
        self.sp_list_cv.bind("<Configure>", self._sp_list_resize)

        # Now-playing bar at bottom
        np = tk.Frame(self.sp_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.sp_np_lbl = tk.Label(
            np,
            text="— SPOTIFY NOT PLAYING —",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
        )
        self.sp_np_lbl.pack(side="left", padx=16)
        # controls
        ctrl = tk.Frame(np, bg=C["panel"])
        ctrl.pack(side="right", padx=10)
        for sym, cmd in [
            ("⏮", self._sp_prev),
            ("⏯", self._sp_playpause),
            ("⏭", self._sp_next),
        ]:
            b = tk.Label(
                ctrl,
                text=sym,
                font=("Courier New", 11),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=6,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))

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
            self.sp_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.sp_search_frame.pack_forget()
        self._sp_refresh_view()

    def _sp_refresh_view(self):
        if not self.sp_auth.is_authenticated():
            self.sp_status_lbl.config(text="[ NOT CONNECTED ]")
            self.sp_login_btn.config(text="CONNECT")
            self.sp_content_lbl.config(
                text="Connect your Spotify account to get started."
            )
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
            self.sp_auth.reload_from_disk()
            if self.sp_api._is_rate_limited():
                remaining = int(self.sp_auth.rate_limited_until - time.time())
                self.root.after(
                    0,
                    lambda: self._sp_status_msg(
                        f"[ Rate limited — retry in {remaining}s ]"
                    ),
                )
                return
            data = self.sp_api.playlists(50)
            if not data:
                self.root.after(
                    0, lambda: self._sp_status_msg("[ Error loading playlists ]")
                )
                return
            items = data.get("items", [])
            self._sp_playlists_cache = items
            self.root.after(0, lambda: self._sp_show_playlists(items))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_show_playlists(self, items):
        self._sp_clear_list()
        self._sp_tracks = []
        self._sp_selected_idx = -1
        self._sp_pl_thumb_cache = {}  # playlist cover cache (separate from track thumbs)
        self._sp_pl_items = items  # keep reference for redraw
        cv = self.sp_list_cv
        RH = self._sp_row_height
        W = max(self._sp_list_width, cv.winfo_width(), 400)
        cv.configure(scrollregion=(0, 0, W, RH * len(items)))
        for i, pl in enumerate(items):
            self._sp_draw_pl_row(i, pl, W)
            # kick off cover art fetch
            images = pl.get("images") or []
            url = images[0].get("url") if images else None
            if url:
                threading.Thread(
                    target=self._sp_fetch_pl_thumb, args=(i, url), daemon=True
                ).start()
            # count comes straight from the playlist object — no extra API calls
        # double-click opens playlist (only while playlists are shown)
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_open_playlist)

    def _sp_draw_pl_row(self, i, pl, W):
        cv = self.sp_list_cv
        RH = self._sp_row_height
        y0 = i * RH
        y1 = y0 + RH
        tag = f"row{i}"
        cv.delete(tag)
        bg = (
            C["select"]
            if i == self._sp_selected_idx
            else (C["panel2"] if i % 2 == 0 else C["bg"])
        )
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)

        # cover art square (same layout as track rows)
        TH = RH - 8
        cv.create_rectangle(
            4, y0 + 4, 4 + TH, y1 - 4, fill=C["panel"], outline=C["border"], tags=tag
        )
        if i in self._sp_pl_thumb_cache:
            photo = self._sp_pl_thumb_cache[i]
            cx = 4 + TH // 2
            cy = y0 + RH // 2
            cv.create_image(cx, cy, image=photo, anchor="center", tags=tag)
        else:
            cv.create_text(
                4 + TH // 2,
                y0 + RH // 2,
                text="▤",
                font=("Courier New", 11),
                fill=C["white3"],
                anchor="center",
                tags=tag,
            )

        # text — offset past image
        tx = 4 + TH + 10
        name = pl.get("name", "?")
        owner = (pl.get("owner") or {}).get("id", "")
        count = (pl.get("tracks") or {}).get("total", None)
        # Spotify-owned algorithmic playlists are API-blocked
        spotify_owned = owner == "spotify"
        name_col = C["white3"] if spotify_owned else C["white"]
        count_str = (
            "[ spotify — no api access ]"
            if spotify_owned
            else (f"{count} tracks" if count else "—")
        )
        cv.create_text(
            tx,
            y0 + RH // 2 - 7,
            text=name[:55],
            font=("Courier New", 9, "bold"),
            fill=name_col,
            anchor="w",
            tags=tag,
        )
        cv.create_text(
            tx,
            y0 + RH // 2 + 7,
            text=count_str,
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )
        cv.create_line(0, y1 - 1, W, y1 - 1, fill=C["border"], tags=tag)

    def _sp_fetch_pl_thumb(self, idx, url):
        """Fetch a playlist cover image in a background thread."""
        try:
            import urllib.request as _ur
            import tempfile

            data = _ur.urlopen(url, timeout=8).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
            self.root.after(0, lambda p=tmp.name, i=idx: self._sp_load_pl_thumb(i, p))
        except Exception:
            pass

    def _sp_load_pl_thumb(self, idx, path):
        """Load playlist cover from temp file, cache it, redraw the row."""
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
            self._sp_pl_thumb_cache[idx] = img
            self._sp_redraw_pl_row(idx)
        except Exception:
            pass
        finally:
            try:
                import os

                os.unlink(path)
            except Exception:
                pass

    def _sp_redraw_pl_row(self, idx):
        """Redraw a single playlist row (called after image/count arrives)."""
        if not hasattr(self, "_sp_pl_items") or idx >= len(self._sp_pl_items):
            return
        W = max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        self._sp_draw_pl_row(idx, self._sp_pl_items[idx], W)

    def _sp_open_playlist(self, event=None):
        idx = self._sp_selected_idx
        if idx < 0 or idx >= len(self._sp_playlists_cache):
            return
        pl = self._sp_playlists_cache[idx]
        pl_id = pl["id"]
        pl_name = pl.get("name", "?")
        pl_uri = pl.get("uri") or f"spotify:playlist:{pl_id}"

        self.sp_content_lbl.config(text=f"▸ {pl_name.upper()}")
        self._sp_clear_list()
        print(f"[SPOTIFY] playing playlist via context_uri: '{pl_name}' id={pl_id}")

        # First try to load track list so user can see and pick songs
        # If that 403s, fall back to playing the whole playlist as a context
        def _fetch():
            tracks = []
            offset = 0
            while True:
                self.sp_api._last_error = ""
                data = self.sp_api.playlist_tracks(pl_id, limit=50, offset=offset)
                if not data:
                    err = getattr(self.sp_api, "_last_error", "")
                    if "403" in err:
                        # Track list blocked — play via context_uri instead
                        print(
                            "[SPOTIFY] track list 403 — falling back to context_uri play"
                        )
                        self.root.after(
                            0, lambda: self._sp_play_context(pl_uri, pl_name)
                        )
                    break
                items = data.get("items", [])
                for it in items:
                    t = it.get("track")
                    if t and t.get("uri"):
                        tracks.append(t)
                offset += len(items)
                if not items or not data.get("next"):
                    break
            if tracks:
                self._sp_tracks = tracks
                self.root.after(0, lambda: self._sp_show_tracks(tracks))
            elif not getattr(self.sp_api, "_last_error", ""):
                self.root.after(
                    0,
                    lambda: self._sp_status_msg("No playable tracks in this playlist."),
                )

        self._sp_status_msg("Loading...")
        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_play_context(self, context_uri, name):
        """Play a Spotify context (playlist/album) directly — bypasses track list API."""
        self._sp_status_msg(f"▶  Playing '{name}'")
        self._stop_all_sources()
        self._active_source = "spotify"
        self._sp_mode = True
        self.root.after(0, lambda: self.sp_np_lbl.config(text=f"▶  {name}"))

        def _do():
            import time as _t

            devices = []
            for _ in range(4):
                data = self.sp_api.devices()
                devices = (data or {}).get("devices", [])
                if devices:
                    break
                _t.sleep(0.7)

            active = [d for d in devices if d.get("is_active")]
            dev_id = (
                active[0]["id"] if active else (devices[0]["id"] if devices else None)
            )
            if not dev_id:
                self.root.after(0, self._sp_no_device_error)
                return

            if not active:
                self.sp_api.transfer(dev_id, play=False)
                _t.sleep(0.5)

            self.sp_api.play_on(dev_id, context_uri=context_uri)

            # Reset position and force a fresh poll after 1.5s
            now = _t.time()
            self.root.after(
                0,
                lambda: (
                    setattr(self, "_sp_pos_ms", 0),
                    setattr(self, "_sp_dur_ms", 0),
                    setattr(self, "_sp_poll_at", now),
                ),
            )
            _t.sleep(1.5)
            if self._sp_np_job:
                try:
                    self.root.after_cancel(self._sp_np_job)
                except:
                    pass
                self._sp_np_job = None
            self.root.after(0, self._sp_poll_np)

        threading.Thread(target=_do, daemon=True).start()

    def _sp_load_liked(self):
        self.sp_content_lbl.config(text="LIKED SONGS")
        self._sp_clear_list()
        self._sp_status_msg("Loading...")

        def _fetch():
            tracks = []
            offset = 0
            while len(tracks) < 200:
                data = self.sp_api.liked_songs(limit=50, offset=offset)
                if not data:
                    break
                items = data.get("items", [])
                for it in items:
                    t = it.get("track")
                    if t and t.get("uri"):
                        tracks.append(t)
                offset += len(items)
                if not items:
                    break
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_do_search(self):
        q = self.sp_search_var.get().strip()
        if not q:
            return
        if not self.sp_auth.is_authenticated():
            self._sp_status_msg("[ Not connected — click CONNECT first ]")
            return
        self.sp_content_lbl.config(text=f'SEARCH: "{q}"')
        self._sp_clear_list()
        self._sp_status_msg("Searching...")

        def _fetch():
            # Diagnose token state before searching
            auth = self.sp_auth
            has_token = bool(auth.access_token)
            token_valid = auth.token_valid()
            has_refresh = bool(auth.refresh_token)
            expires_in = int(auth.expires_at - time.time()) if auth.expires_at else 0

            if not has_token and not has_refresh:
                self.root.after(
                    0,
                    lambda: self._sp_status_msg(
                        "[ Not logged in — please DISCONNECT and reconnect ]"
                    ),
                )
                return
            if not token_valid and not has_refresh:
                self.root.after(
                    0,
                    lambda: self._sp_status_msg(
                        "[ Token expired and no refresh token — please reconnect ]"
                    ),
                )
                return

            data = self.sp_api.search(q, limit=20)
            if not data:
                err = getattr(self.sp_api, "_last_error", None)
                if err:
                    msg = f"[ Search failed: {err} ]"
                else:
                    # Extra diagnostics
                    msg = (
                        f"[ Search returned nothing — "
                        f"token={'ok' if token_valid else 'expired'}, "
                        f"refresh={'yes' if has_refresh else 'no'}, "
                        f"expires_in={expires_in}s, "
                        f"client_id={'set' if SPOTIFY_CLIENT_ID else 'MISSING'} ]"
                    )
                self.root.after(0, lambda m=msg: self._sp_status_msg(m))
                return
            tracks = [
                it
                for it in data.get("tracks", {}).get("items", [])
                if it and it.get("uri")
            ]
            if not tracks:
                self.root.after(0, lambda: self._sp_status_msg("[ No tracks found ]"))
                return
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_clear_list(self):
        if hasattr(self, "sp_list_cv"):
            self.sp_list_cv.delete("all")
            self.sp_list_cv.configure(scrollregion=(0, 0, 100, 40))
        self._sp_thumb_cache = {}
        self._sp_pl_thumb_cache = {}
        self._sp_pl_items = []
        self._sp_selected_idx = -1

    def _sp_status_msg(self, msg):
        cv = self.sp_list_cv
        cv.delete("all")
        cv.create_text(20, 20, text=msg, anchor="nw", font=FM, fill=C["white3"])
        cv.configure(scrollregion=(0, 0, 100, 40))

    def _sp_show_tracks(self, tracks):
        self._sp_tracks = tracks
        self._sp_selected_idx = -1
        self._sp_thumb_cache = {}
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
                threading.Thread(
                    target=self._sp_fetch_thumb, args=(i, url), daemon=True
                ).start()

    def _sp_fetch_thumb(self, idx, url):
        try:
            import urllib.request as _ur
            import tempfile

            data = _ur.urlopen(url, timeout=6).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
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
                import os

                os.unlink(path)
            except Exception:
                pass

    def _sp_render_list(self):
        cv = self.sp_list_cv
        cv.delete("all")
        if not hasattr(self, "_sp_tracks") or not self._sp_tracks:
            cv.create_text(
                20, 20, text="No tracks loaded.", anchor="nw", font=FM, fill=C["white3"]
            )
            cv.configure(scrollregion=(0, 0, 100, 40))
            return
        RH = self._sp_row_height
        W = max(self._sp_list_width, cv.winfo_width(), 400)
        total_h = RH * len(self._sp_tracks)
        cv.configure(scrollregion=(0, 0, W, total_h))
        for i, t in enumerate(self._sp_tracks):
            self._sp_draw_row(i, t, W)
        cv.update_idletasks()
        cv.update_idletasks()

    def _sp_draw_row(self, i, t, W):
        cv = self.sp_list_cv
        RH = self._sp_row_height
        y0 = i * RH
        y1 = y0 + RH
        tag = f"row{i}"
        cv.delete(tag)

        bg = (
            C["select"]
            if i == self._sp_selected_idx
            else (C["panel2"] if i % 2 == 0 else C["bg"])
        )
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)

        TH = RH - 8
        cv.create_rectangle(
            4, y0 + 4, 4 + TH, y1 - 4, fill=C["panel"], outline=C["border"], tags=tag
        )
        if i in self._sp_thumb_cache:
            photo = self._sp_thumb_cache[i]
            cx = 4 + TH // 2
            cy = y0 + RH // 2
            cv.create_image(cx, cy, image=photo, anchor="center", tags=tag)
        else:
            cv.create_text(
                4 + TH // 2,
                y0 + RH // 2,
                text="o",
                font=("Courier New", 12),
                fill=C["white3"],
                anchor="center",
                tags=tag,
            )

        tx = 4 + TH + 8
        cv.create_text(
            tx,
            y0 + RH // 2,
            text=f"{i + 1:>3}.",
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )

        title = t.get("name", "?")
        artists = t.get("artists", [])
        artist = ", ".join(a["name"] for a in artists)
        album = t.get("album", {}).get("name", "")
        dur_ms = t.get("duration_ms", 0)
        dur_s = dur_ms // 1000
        dur_str = f"{dur_s // 60}:{dur_s % 60:02d}"
        tx2 = tx + 36
        # Title row
        cv.create_text(
            tx2,
            y0 + 14,
            text=title[:70],
            font=("Courier New", 9, "bold"),
            fill=C["white"],
            anchor="w",
            tags=tag,
        )
        # Artist row
        cv.create_text(
            tx2,
            y0 + 32,
            text=artist[:70],
            font=("Courier New", 8),
            fill=C["white2"],
            anchor="w",
            tags=tag,
        )
        # Album row
        cv.create_text(
            tx2,
            y0 + 48,
            text=album[:70],
            font=("Courier New", 7),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )

        cv.create_text(
            W - 12,
            y0 + RH // 2,
            text=dur_str,
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="e",
            tags=tag,
        )

        cv.create_line(0, y1 - 1, W, y1 - 1, fill=C["border"], tags=tag)

    def _sp_redraw_row(self, idx):
        if not hasattr(self, "_sp_tracks") or idx >= len(self._sp_tracks):
            return
        W = max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        self._sp_draw_row(idx, self._sp_tracks[idx], W)

    def _sp_list_resize(self, event):
        self._sp_list_width = event.width
        self._sp_render_list()

    def _sp_list_click(self, event):
        RH = self._sp_row_height
        idx = int(self.sp_list_cv.canvasy(event.y) // RH)
        max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        # ── playlist home view: single click opens the playlist ──
        if hasattr(self, "_sp_pl_items") and self._sp_pl_items and not self._sp_tracks:
            if idx < 0 or idx >= len(self._sp_pl_items):
                return
            self._sp_selected_idx = idx
            self._sp_open_playlist()
            return
        # ── track view ──
        if not hasattr(self, "_sp_tracks") or idx >= len(self._sp_tracks):
            return
        old = self._sp_selected_idx
        self._sp_selected_idx = idx
        if old >= 0:
            self._sp_redraw_row(old)
        self._sp_redraw_row(idx)

    def _sp_play_selected(self, event=None):
        idx = self._sp_selected_idx
        if idx < 0 or not self._sp_tracks:
            return
        if idx >= len(self._sp_tracks):
            return
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
            for attempt in range(6):  # try up to ~5 seconds
                data = self.sp_api.devices()
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
        messagebox.showwarning(
            "OTERNOS // SPOTIFY",
            "No active Spotify device found."
            + chr(10)
            + chr(10)
            + "Open Spotify on your phone, PC, or any device first,"
            + chr(10)
            + "then try playing again.",
        )

    def _sp_rclick(self, event):
        RH = self._sp_row_height
        sel = int(self.sp_list_cv.canvasy(event.y) // RH)
        old = self._sp_selected_idx
        self._sp_selected_idx = sel
        if old >= 0:
            self._sp_redraw_row(old)
        self._sp_redraw_row(sel)
        if sel >= len(self._sp_tracks):
            return
        track = self._sp_tracks[sel]
        m = tk.Menu(
            self.root,
            tearoff=0,
            bg=C["panel"],
            fg=C["white"],
            font=FM,
            bd=0,
            relief="flat",
            activebackground=C["select"],
            activeforeground=C["white"],
        )
        m.add_command(label="▶  Play Now", command=lambda: self._sp_play_selected())
        m.add_command(
            label="＋  Add to Local Library",
            command=lambda: self._sp_add_to_local(track),
        )
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _sp_add_to_local(self, track):
        title = track.get("name", "?")
        artist = ", ".join(a["name"] for a in track.get("artists", []))
        note = "Spotify tracks cannot be downloaded. Play them via the Spotify tab while Spotify is open."
        msg = title + " by " + artist + chr(10) + chr(10) + note
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
        """Poll Spotify now-playing every 10 seconds."""
        if not self.sp_auth.is_authenticated():
            self._sp_np_job = None
            return

        def _fetch():
            if not self.sp_auth.token_valid():
                return
            if self.sp_api._is_rate_limited():
                remaining = int(self.sp_auth.rate_limited_until - time.time())
                self.root.after(
                    0,
                    lambda: self.sp_np_lbl.config(
                        text=f"⏸  Rate limited — {remaining}s"
                    ),
                )
                return
            np = self.sp_api.now_playing()
            if np and np.get("item"):
                t = np["item"]
                title = t.get("name", "?")
                artist = ", ".join(a["name"] for a in t.get("artists", []))
                is_play = np.get("is_playing", False)
                pos_ms = np.get("progress_ms", 0) or 0
                dur_ms = t.get("duration_ms", 0) or 0
                dev = (np.get("device") or {}).get("name", "")
                dev_s = ("  //  " + dev[:20]) if dev else ""
                sym = "▶" if is_play else "⏸"
                sp_lbl = sym + "  " + title[:38] + "  —  " + artist[:24] + dev_s
                # grab smallest image that's still at least 64px
                images = t.get("album", {}).get("images", [])
                art_url = None
                for img in sorted(images, key=lambda x: x.get("width", 0)):
                    if img.get("width", 0) >= 64:
                        art_url = img.get("url")
                        break
                if not art_url and images:
                    art_url = images[-1].get("url")

                # Push into main player bar — only if Spotify is actually playing
                def _update():
                    self._sp_pos_ms = pos_ms
                    self._sp_dur_ms = dur_ms
                    self._sp_playing = is_play
                    self.sp_np_lbl.config(text=sp_lbl)
                    # Only take over the main bar if:
                    #   - Spotify is already the active source, OR
                    #   - No local playback is happening at all
                    local_active = (
                        self.engine.is_playing
                        or self.engine.is_paused
                        or self._active_source in ("library", "youtube", "soundcloud")
                    )
                    if is_play and self._active_source == "spotify":
                        pass  # already spotify — always update
                    elif is_play and not local_active and self._active_source == "none":
                        pass  # nothing local running — spotify can take over
                    else:
                        return  # local/YT/SC is active — don't hijack
                    self._sp_mode = True
                    self._active_source = "spotify"
                    self._set_source_badge("spotify")
                    t_disp = (title[:36] + "…") if len(title) > 37 else title
                    self.now_title.config(text=t_disp)
                    self.now_artist.config(text=artist)
                    self.lbl_tot.config(text=self._fmt(dur_ms / 1000))
                    self.btn_play.config(text="⏸")
                    self.wavevis.set_active(True)
                    self.status_lbl.config(text="[ SPOTIFY ]")
                    if art_url:
                        self._set_album_art(art_url)
                    # History + lyrics
                    last = self._history[-1] if self._history else {}
                    if is_play and last.get("title") != title:
                        self._history_add(
                            {"title": title, "artist": artist, "album": ""},
                            source="spotify",
                        )
                        # Fetch lyrics for new track — works same as library/_do_load_track
                        self._set_current_track_for_lyrics(artist, title)
                        self._start_lyric_ticker()
                        if getattr(self, "view", "") == "lyrics":
                            self._refresh_lyrics_view()

                self.root.after(0, _update)
            else:
                devs = (self.sp_api.devices() or {}).get("devices", [])
                if devs:
                    names = ", ".join(d.get("name", "?") for d in devs[:3])
                    lbl = "⏸  No track playing  //  devices: " + names
                else:
                    lbl = "— NO SPOTIFY DEVICE FOUND — open Spotify on a device —"
                self.root.after(0, lambda: self.sp_np_lbl.config(text=lbl))
                self.root.after(0, self._draw_art_placeholder)

        threading.Thread(target=_fetch, daemon=True).start()
        self._sp_np_job = self.root.after(10000, self._sp_poll_np)

    def _sp_show_devices(self):
        def _do():
            data = self.sp_api.devices()
            devices = (data or {}).get("devices", [])
            if not devices:
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "OTERNOS // SPOTIFY DEVICES",
                        "No Spotify devices found."
                        + chr(10)
                        + chr(10)
                        + "Make sure Spotify is open and playing on at least one device.",
                    ),
                )
                return
            lines = ["AVAILABLE DEVICES", ""]
            for d in devices:
                active = " [ACTIVE]" if d.get("is_active") else ""
                lines.append(
                    d.get("name", "?") + "  //  " + d.get("type", "?") + active
                )
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "OTERNOS // SPOTIFY DEVICES", chr(10).join(lines)
                ),
            )

        threading.Thread(target=_do, daemon=True).start()

    def _sp_login(self):
        if self.sp_auth.is_authenticated():
            # Disconnect
            self.sp_auth.access_token = None
            self.sp_auth.refresh_token = None
            self.sp_auth.expires_at = 0
            try:
                Path(SpotifyAuth.TOKEN_FILE).unlink()
            except:
                pass
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
            self.root.after(
                0,
                lambda: self.sp_status_lbl.config(text="[ AUTH FAILED ]", fg=C["red"]),
            )


    # ── SOUNDCLOUD VIEW ───────────────────
    def _sp_vol_debounce(self, pct):
        if not self._sp_mode:
            return
        if hasattr(self, "_sp_vol_job") and self._sp_vol_job:
            self.root.after_cancel(self._sp_vol_job)
        self._sp_vol_job = self.root.after(
            250,
            lambda p=pct: threading.Thread(
                target=lambda: self.sp_api.volume(p), daemon=True
            ).start(),
        )

