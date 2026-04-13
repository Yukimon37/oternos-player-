"""
soundcloud_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all soundcloud-related methods.
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
import tempfile
from pathlib import Path
from tkinter import messagebox

if getattr(sys, "frozen", False):
    from oternos.constants import C, FM, FMS, FML, FMX, DATA_FILE, YT_CACHE, HW_ACCEL
    from oternos.diagnostics import log_exception
    from oternos.streaming import SoundCloudAPI
else:
    from ..constants import C, FM, FMS, FML, FMX, DATA_FILE, YT_CACHE, HW_ACCEL
    from ..diagnostics import log_exception
    from ..streaming import SoundCloudAPI

if getattr(sys, "frozen", False):
    from oternos.stream_cards import StreamCardList
else:
    from ..stream_cards import StreamCardList

# ── Inline script for the pywebview subprocess ────────────────────────────────
_SC_WEBVIEW_SCRIPT = """
import sys
try:
    import webview
    w = webview.create_window(
        "OTERNOS // SOUNDCLOUD",
        "http://127.0.0.1:47472/",
        width=960, height=700,
        resizable=True,
        min_size=(640, 480),
    )
    webview.start()
except ImportError:
    import webbrowser, time
    webbrowser.open("http://127.0.0.1:47472/")
    time.sleep(86400)
except Exception as e:
    import time
    print(f"webview error: {e}", file=sys.stderr)
    time.sleep(3)
"""


class SoundcloudMixin:
    """Mixin: soundcloud methods for VoidPlayer."""
    def _build_soundcloud_view(self):
        self.sc_frame = tk.Frame(self.content, bg=C["bg"])
        self._sc_hover_idx = -1

        # ── Header ────────────────────────────────────────────────────────
        top = tk.Frame(self.sc_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="SOUNDCLOUD", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")

        # Status pill: ● dot + text badge
        self._sc_status_dot = tk.Label(top, text="●", font=FMS, fg=C["white3"], bg=C["bg"])
        self._sc_status_dot.pack(side="left", padx=(12, 2))
        self.sc_status_lbl = tk.Label(top, text="PUBLIC", font=FMS, fg=C["white2"], bg=C["bg"])
        self.sc_status_lbl.pack(side="left")

        self.sc_queue_lbl = tk.Label(top, text="", font=FMS, fg=C["white3"], bg=C["bg"])
        self.sc_queue_lbl.pack(side="left", padx=(12, 0))

        # HTML view controls (right side of header)
        self._sc_close_web_btn = tk.Label(top, text="[ CLOSE ]", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=4)
        self._sc_close_web_btn.pack(side="right", padx=(0, 4))
        self._sc_close_web_btn.bind("<Button-1>", lambda e: self._sc_close_html_view())
        self._sc_close_web_btn.bind("<Enter>",    lambda e: self._sc_close_web_btn.config(fg=C["white"]))
        self._sc_close_web_btn.bind("<Leave>",    lambda e: self._sc_close_web_btn.config(fg=C["white3"]))

        self._sc_open_web_btn = tk.Label(top, text="[ WEB UI ]", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=4)
        self._sc_open_web_btn.pack(side="right", padx=(0, 2))
        self._sc_open_web_btn.bind("<Button-1>", lambda e: threading.Thread(target=self._sc_open_html_view, daemon=True).start())
        self._sc_open_web_btn.bind("<Enter>",    lambda e: self._sc_open_web_btn.config(fg=C["white"]))
        self._sc_open_web_btn.bind("<Leave>",    lambda e: self._sc_open_web_btn.config(fg=C["white2"]))

        self._sc_webview_dot = tk.Label(top, text="○", font=FMS, fg=C["white3"], bg=C["bg"])
        self._sc_webview_dot.pack(side="right", padx=(8, 0))

        # ── Collapsible auth row (hidden by default) ──────────────────────
        self._sc_auth_visible = False
        self.sc_auth_row = tk.Frame(self.sc_frame, bg=C["panel"])
        inner_auth = tk.Frame(self.sc_auth_row, bg=C["panel"])
        inner_auth.pack(fill="x", padx=20, pady=6)
        tk.Label(inner_auth, text="OAuth Token:", font=FMS, fg=C["white3"], bg=C["panel"]).pack(side="left", padx=(0, 6))
        self.sc_token_var = tk.StringVar(value=self.sc_api.oauth_token or "")
        _tok_wrap = tk.Frame(inner_auth, bg=C["border"], padx=1, pady=1)
        _tok_wrap.pack(side="left", padx=(0, 6))
        sc_tok_entry = tk.Entry(_tok_wrap, textvariable=self.sc_token_var,
                                font=FMS, bg=C["panel"], fg=C["white"],
                                insertbackground=C["white"], relief="flat", bd=0, width=36, show="*")
        sc_tok_entry.pack(ipady=3)
        sc_tok_entry.bind("<FocusIn>",  lambda e: _tok_wrap.config(bg=C["white3"]))
        sc_tok_entry.bind("<FocusOut>", lambda e: _tok_wrap.config(bg=C["border"]))
        sc_tok_entry.bind("<Return>", lambda e: self._sc_save_token())
        self.sc_save_btn = tk.Label(inner_auth, text="SAVE", font=FMS, fg=C["white3"], bg=C["panel"], cursor="hand2")
        self.sc_save_btn.pack(side="left")
        self.sc_save_btn.bind("<Button-1>", lambda e: self._sc_save_token())
        self.sc_save_btn.bind("<Enter>", lambda e: self.sc_save_btn.config(fg=C["white"]))
        self.sc_save_btn.bind("<Leave>", lambda e: self.sc_save_btn.config(fg=C["white3"]))
        tk.Label(inner_auth, text="  from sc-inspector or browser devtools",
                 font=("Courier New", 7), fg=C["white3"], bg=C["panel"]).pack(side="left")

        tk.Frame(self.sc_frame, bg=C["border"], height=1).pack(fill="x", pady=(6, 0))

        # ── Sub-nav with animated underline ──────────────────────────────
        nav = tk.Frame(self.sc_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(6, 0))
        self._sc_nav_btns = {}
        self._sc_nav_underlines = {}
        for label, key in [("SEARCH", "search"), ("LIKES", "likes"), ("FAVORITES", "favorites")]:
            tf = tk.Frame(nav, bg=C["bg"])
            tf.pack(side="left", padx=(0, 2))
            b = tk.Label(tf, text=label, font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=10)
            b.pack()
            uline = tk.Canvas(tf, height=2, bg=C["bg"], highlightthickness=0)
            uline.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=key: self._sc_nav(k))
            b.bind("<Enter>",  lambda e, w=b, k=key: w.config(fg=C["white"]) if self._sc_view != k else None)
            b.bind("<Leave>",  lambda e, w=b, k=key: w.config(fg=C["white"]) if self._sc_view == k else w.config(fg=C["white3"]))
            self._sc_nav_btns[key] = b
            self._sc_nav_underlines[key] = uline

        # CLR QUEUE button — right side
        self._sc_clr_btn = tk.Label(nav, text="CLR QUEUE", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=6)
        self._sc_clr_btn.pack(side="right")
        self._sc_clr_btn.bind("<Button-1>", lambda e: self._sc_clear_queue())
        self._sc_clr_btn.bind("<Enter>", lambda e: self._sc_clr_btn.config(fg=C["white"]))
        self._sc_clr_btn.bind("<Leave>", lambda e: self._sc_clr_btn.config(fg=C["white3"]))

        # TOKEN toggle — right side
        self._sc_tok_btn = tk.Label(nav, text="TOKEN", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=6)
        self._sc_tok_btn.pack(side="right")
        self._sc_tok_btn.bind("<Button-1>", lambda e: self._sc_toggle_auth())
        self._sc_tok_btn.bind("<Enter>", lambda e: self._sc_tok_btn.config(fg=C["white"]))
        self._sc_tok_btn.bind("<Leave>", lambda e: self._sc_tok_btn.config(fg=C["white3"]))

        # Draw initial underline on active tab
        self.sc_frame.after(50, lambda: self._sc_draw_nav_underline("search"))

        # ── Search bar with focus ring ────────────────────────────────────
        self.sc_search_frame = tk.Frame(self.sc_frame, bg=C["bg"])
        self.sc_search_frame.pack(fill="x", pady=(4, 0))
        tk.Label(self.sc_search_frame, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        _search_ring = tk.Frame(self.sc_search_frame, bg=C["border"], padx=1, pady=1)
        _search_ring.pack(side="left", padx=(0, 6))
        self.sc_search_var = tk.StringVar()
        sc_entry = tk.Entry(_search_ring, textvariable=self.sc_search_var,
                            font=FM, bg=C["panel"], fg=C["white"],
                            insertbackground=C["white"], relief="flat", bd=0, width=40)
        sc_entry.pack(ipady=4)
        sc_entry.bind("<FocusIn>",  lambda e: _search_ring.config(bg=C["white3"]))
        sc_entry.bind("<FocusOut>", lambda e: _search_ring.config(bg=C["border"]))
        sc_entry.bind("<Return>", lambda e: (self._sc_do_search(), "break")[1])
        sc_go = tk.Label(self.sc_search_frame, text="GO", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=8)
        sc_go.pack(side="left")
        sc_go.bind("<Button-1>", lambda e: self._sc_do_search())
        sc_go.bind("<Enter>", lambda e: sc_go.config(fg=C["white"]))
        sc_go.bind("<Leave>", lambda e: sc_go.config(fg=C["white3"]))

        tk.Frame(self.sc_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        self.sc_content_lbl = tk.Label(self.sc_frame, text="Search for tracks above",
                                        font=("Courier New", 8, "bold"), fg=C["white3"], bg=C["bg"], anchor="w")
        self.sc_content_lbl.pack(fill="x", padx=20, pady=(8, 2))

        # ── Track list ────────────────────────────────────────────────────
        lf = tk.Frame(self.sc_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        self._sc_card_list = StreamCardList(
            lf, self.root,
            on_play   = lambda t: threading.Thread(target=lambda: self._sc_stream(t), daemon=True).start(),
            on_queue  = lambda t: self._sc_queue_track(t),
            on_detail = lambda t, x, y: self._sc_rclick_from_card(t, x, y),
            source    = "soundcloud",
        )
        self.sc_list = self._sc_card_list.cv
        self._sc_detail_idx = -1
        self._sc_detail_win = None
        self._sc_hover_idx  = -1
        self._sc_hover_job  = None
        self._sc_thumb_tip  = None

        # ── Right-click context menu ──────────────────────────────────────
        self._sc_ctx = tk.Menu(self.sc_frame, tearoff=0, bg=C["panel"], fg=C["white"],
                                activebackground=C["select2"], activeforeground=C["glow"],
                                font=FMS, bd=0, relief="flat")
        self._sc_ctx.add_command(label="▶  Play",                  command=self._sc_ctx_play)
        self._sc_ctx.add_command(label="⊕  Add to Queue",          command=self._sc_ctx_queue)
        self._sc_ctx.add_separator()
        self._sc_ctx.add_command(label="♥  Add to Favorites",      command=self._sc_ctx_favorite)
        self._sc_ctx.add_command(label="✕  Remove from Favorites", command=self._sc_ctx_unfavorite)
        self._sc_ctx.add_separator()
        self._sc_ctx.add_command(label="⬇  Save to Library",       command=self._sc_ctx_save)
        self._sc_ctx.add_command(label="⎘  Open on SoundCloud",    command=self._sc_ctx_open)

        # ── Now-playing bar ───────────────────────────────────────────────
        np = tk.Frame(self.sc_frame, bg=C["panel"], height=36)
        np.pack(fill="x")
        np.pack_propagate(False)
        # Left accent stripe
        tk.Frame(np, bg=C["border2"], width=3).pack(side="left", fill="y")
        self.sc_np_lbl = tk.Label(np, text="— SOUNDCLOUD —", font=("Courier New", 8),
                                   fg=C["white3"], bg=C["panel"])
        self.sc_np_lbl.pack(side="left", padx=12)
        self.sc_np_artist_btn = tk.Label(np, text="", font=("Courier New", 8),
                                          fg=C["white3"], bg=C["panel"], cursor="hand2")
        self.sc_np_artist_btn.pack(side="right", padx=16)
        self.sc_np_artist_btn.bind("<Button-1>", lambda e: self._sc_np_artist_click())
        self.sc_np_artist_btn.bind("<Enter>", lambda e: self.sc_np_artist_btn.config(fg=C["white"]))
        self.sc_np_artist_btn.bind("<Leave>", lambda e: self.sc_np_artist_btn.config(fg=C["white3"]))

        # Restore NP bar if a track is already playing when view is first built
        self.sc_frame.after(50,  self._sc_restore_np_bar)
        self.sc_frame.after(200, self._sc_init_bridge)   # start bridge in background

    def _sc_toggle_auth(self):
        self._sc_auth_visible = not self._sc_auth_visible
        if self._sc_auth_visible:
            self.sc_auth_row.pack(fill="x", pady=(2, 0), after=self.sc_frame.winfo_children()[0])
            self._sc_tok_btn.config(fg=C["white"])
        else:
            self.sc_auth_row.pack_forget()
            self._sc_tok_btn.config(fg=C["white3"] if not self.sc_api.oauth_token else C["white"])

    def _sc_draw_nav_underline(self, key):
        """Draw a 2px white underline bar under the active nav tab."""
        for k, uline in self._sc_nav_underlines.items():
            uline.delete("all")
            if k == key:
                w = uline.winfo_width() or 60
                uline.create_rectangle(0, 0, w, 2, fill=C["white"], outline="")

    def _sc_list_hover(self, event):
        pass  # StreamCardList handles hover

    def _sc_list_unhover(self, event=None):
        pass  # StreamCardList handles hover

    def _sc_restore_row_color(self, idx):
        pass  # StreamCardList handles row colors

    def _sc_hover_animate(self, idx):
        pass  # StreamCardList handles hover animation

    def _sc_hover_scan(self, idx, cols):
        pass  # StreamCardList handles hover animation

    # ── Inline detail panel ───────────────────────────────────────────────

    def _sc_list_click(self, event):
        pass  # StreamCardList handles clicks via on_play/on_queue/on_detail callbacks
        list_w = self.sc_list.winfo_width()
        if event.x >= list_w - 28:
            self._sc_detail_toggle(idx)
        else:
            self._sc_detail_close()
            track = self._sc_tracks[idx]
            threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_detail_toggle(self, idx):
        """Open detail for idx, or close it if already open for same row."""
        if self._sc_detail_idx == idx and self._sc_detail_win is not None:
            self._sc_detail_close()
        else:
            self._sc_detail_open(idx)

    def _sc_detail_close(self):
        """Destroy the floating detail panel."""
        if self._sc_detail_win is not None:
            try:
                self._sc_detail_win.destroy()
            except Exception:
                pass
            self._sc_detail_win = None
        self._sc_detail_idx = -1

    def _sc_detail_open(self, idx):
        """Build and position the floating detail panel below the selected row."""
        self._sc_detail_close()
        if idx < 0 or idx >= len(self._sc_tracks):
            return
        track = self._sc_tracks[idx]
        self._sc_detail_idx = idx

        # ── Compute position: just below the card list ──
        try:
            lx = self.sc_list.winfo_rootx()
            ly = self.sc_list.winfo_rooty()
            lw = self.sc_list.winfo_width()
            lh = self.sc_list.winfo_height()
        except Exception:
            return

        panel_w = lw - 2
        panel_x = lx + 1
        panel_y = ly + row_y + row_h  # immediately below the row

        # Clamp: if it would overflow the bottom of the listbox, show above instead
        panel_h_est = 96
        if panel_y + panel_h_est > ly + lh:
            panel_y = ly + row_y - panel_h_est

        # ── Build as a Toplevel so it floats over the listbox ──────────────
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", False)
        win.configure(bg=C["border"])
        self._sc_detail_win = win

        # 1px border via bg + inner frame
        inner = tk.Frame(win, bg=C["panel2"] if "panel2" in C else C["panel"], padx=14, pady=8)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        bg = inner["bg"]

        # ── Row 1: title + duration ────────────────────────────────────────
        r1 = tk.Frame(inner, bg=bg)
        r1.pack(fill="x", pady=(0, 4))
        title = (track.get("title") or "")
        tk.Label(r1, text=title, font=("Courier New", 9, "bold"),
                 fg=C["white"], bg=bg, anchor="w").pack(side="left", fill="x", expand=True)
        dur_ms = track.get("duration", 0)
        dur_s = dur_ms // 1000
        dur_str = f"{dur_s // 60}:{dur_s % 60:02d}"
        tk.Label(r1, text=dur_str, font=FMS, fg=C["white3"], bg=bg).pack(side="right")

        # ── Row 2: artist ──────────────────────────────────────────────────
        r2 = tk.Frame(inner, bg=bg)
        r2.pack(fill="x", pady=(0, 4))
        artist = (track.get("user", {}).get("username") or "")
        artist_lbl = tk.Label(r2, text=artist, font=FMS, fg=C["white3"], bg=bg,
                               cursor="hand2", anchor="w")
        artist_lbl.pack(side="left")
        artist_lbl.bind("<Button-1>", lambda e: (self._sc_detail_close(),
                                                  self.sc_search_var.set(artist),
                                                  self._sc_nav("search"),
                                                  self._sc_do_search()))
        artist_lbl.bind("<Enter>", lambda e: artist_lbl.config(fg=C["white"]))
        artist_lbl.bind("<Leave>", lambda e: artist_lbl.config(fg=C["white3"]))

        # Genre pill
        genre = (track.get("genre") or "").strip()
        if genre:
            tk.Label(r2, text=f"  {genre}", font=("Courier New", 7),
                     fg=C["white3"], bg=bg).pack(side="left")

        # ── Row 3: stats ───────────────────────────────────────────────────
        r3 = tk.Frame(inner, bg=bg)
        r3.pack(fill="x", pady=(0, 5))

        def _fmt(n):
            if n is None:
                return "—"
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n//1000}k"
            return str(n)

        plays    = track.get("playback_count")
        likes    = track.get("likes_count") or track.get("favoritings_count")
        comments = track.get("comment_count")
        reposts  = track.get("reposts_count")

        stats = [
            ("▸", _fmt(plays),    "plays"),
            ("♥", _fmt(likes),    "likes"),
            ("◉", _fmt(comments), "comments"),
            ("⇄", _fmt(reposts),  "reposts"),
        ]
        for icon, val, tip in stats:
            cell = tk.Frame(r3, bg=bg)
            cell.pack(side="left", padx=(0, 16))
            tk.Label(cell, text=f"{icon} {val}", font=FMS,
                     fg=C["white2"], bg=bg).pack(side="left")

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", pady=(0, 5))

        # ── Row 4: description snippet ────────────────────────────────────
        desc = (track.get("description") or "").strip().replace("\n", "  ")
        if desc:
            snippet = desc[:120] + ("…" if len(desc) > 120 else "")
            tk.Label(inner, text=snippet, font=("Courier New", 7),
                     fg=C["white3"], bg=bg, anchor="w", wraplength=panel_w - 40,
                     justify="left").pack(fill="x", pady=(0, 4))

        # ── Row 5: action buttons ─────────────────────────────────────────
        r5 = tk.Frame(inner, bg=bg)
        r5.pack(fill="x")

        def _btn(parent, text, cmd):
            b = tk.Label(parent, text=text, font=FMS, fg=C["white3"], bg=bg,
                          cursor="hand2", padx=6)
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(fg=C["white"]))
            b.bind("<Leave>", lambda e: b.config(fg=C["white3"]))
            return b

        def _play():
            self._sc_detail_close()
            threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

        def _queue():
            self._sc_ctx_queue()
            self._sc_detail_close()

        def _fav():
            fav_ids = {t.get("id") for t in self._sc_favorites}
            if track.get("id") in fav_ids:
                self._sc_ctx_unfavorite()
            else:
                self._sc_ctx_favorite()
            self._sc_detail_close()

        def _open():
            url = track.get("permalink_url") or ""
            if url:
                import webbrowser
                webbrowser.open(url)

        _btn(r5, "▶ PLAY",    _play)
        _btn(r5, "⊕ QUEUE",   _queue)
        fav_ids = {t.get("id") for t in self._sc_favorites}
        fav_text = "✕ UNFAV" if track.get("id") in fav_ids else "♥ FAV"
        _btn(r5, fav_text, _fav)
        _btn(r5, "⎘ OPEN",    _open)

        # ── Position and show ─────────────────────────────────────────────
        win.update_idletasks()
        actual_h = win.winfo_reqheight()

        # Re-clamp with real height
        if panel_y + actual_h > ly + lh:
            panel_y = ly + row_y - actual_h
        panel_y = max(ly, panel_y)

        win.geometry(f"{panel_w}x{actual_h}+{panel_x}+{panel_y}")

        # Close if user clicks anywhere outside the panel.
        # We use FocusOut on the panel window — no root-level binding needed,
        # which avoids clobbering other root Button-1 handlers.
        win.bind("<FocusOut>", lambda e: self.root.after(120, self._sc_detail_maybe_close))
        self.sc_list.bind("<Configure>", lambda e: self._sc_detail_close(), add="+")
        self.sc_list.bind("<MouseWheel>",
            lambda e: self._sc_detail_close(), add="+")
        # Give the panel focus so FocusOut fires when user clicks elsewhere
        win.after(50, lambda: win.focus_force() if win.winfo_exists() else None)

    def _sc_detail_maybe_close(self):
        """Close detail panel if focus has left it."""
        if self._sc_detail_win is None:
            return
        try:
            focused = self.root.focus_get()
            # If focus is inside the detail window, don't close
            win = self._sc_detail_win
            w = focused
            while w is not None:
                if w == win:
                    return
                try:
                    w = w.master
                except Exception:
                    break
        except Exception:
            pass
        self._sc_detail_close()

    def _sc_detail_outside_click(self, event):
        """Close detail panel if click lands outside it."""
        if self._sc_detail_win is None:
            return
        try:
            win = self._sc_detail_win
            wx = win.winfo_rootx()
            wy = win.winfo_rooty()
            ww = win.winfo_width()
            wh = win.winfo_height()
            if not (wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh):
                self._sc_detail_close()
        except Exception:
            self._sc_detail_close()

    def _sc_save_token(self):
        tok = self.sc_token_var.get().strip()
        self.sc_api.oauth_token = tok or None
        self.sc_api._save_token()
        if tok:
            self._sc_status_dot.config(fg=C["white"])
            self.sc_status_lbl.config(text="AUTH", fg=C["white"])
        else:
            self._sc_status_dot.config(fg=C["white3"])
            self.sc_status_lbl.config(text="PUBLIC", fg=C["white3"])
        self._sc_tok_btn.config(fg=C["white"] if tok else C["white3"])
        # Flash SAVED ✓ then revert, and auto-collapse after a moment
        self.sc_save_btn.config(text="SAVED ✓", fg=C["white"])
        def _revert_btn():
            try:
                self.sc_save_btn.config(text="SAVE", fg=C["white3"])
            except Exception:
                pass
        def _collapse():
            if self._sc_auth_visible:
                self._sc_toggle_auth()
        self.root.after(1200, _revert_btn)
        self.root.after(1600, _collapse)

    def _sc_nav(self, key):
        # Save current view's track list and label before switching
        prev = getattr(self, "_sc_view", "search")
        if prev == "search":
            self._sc_search_tracks = list(self._sc_tracks)
            self._sc_search_label = self.sc_content_lbl.cget("text") if hasattr(self, "sc_content_lbl") else ""
        elif prev == "likes":
            self._sc_likes_tracks = list(self._sc_tracks)
            self._sc_likes_label = self.sc_content_lbl.cget("text") if hasattr(self, "sc_content_lbl") else ""

        self._sc_view = key
        self._sc_detail_close()
        for k, b in self._sc_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        self._sc_draw_nav_underline(key)
        if key == "search":
            self.sc_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.sc_search_frame.pack_forget()
        self._sc_restore_np_bar()
        self._sc_refresh_view()

    def _sc_restore_np_bar(self):
        """Restore NP bar labels from _sc_current_track after tab switches."""
        t = getattr(self, "_sc_current_track", None)
        if t:
            title  = (t.get("title") or "")[:48]
            artist = (t.get("user", {}).get("username") or "")
            self.sc_np_lbl.config(text=f"  ▶  {title}", fg=C["white"])
            self.sc_np_artist_btn.config(text=artist, fg=C["white2"])
            self.sc_frame.after(120, lambda: self.sc_np_lbl.config(fg=C["white2"]))
        else:
            self.sc_np_lbl.config(text="— SOUNDCLOUD —", fg=C["white3"])
            self.sc_np_artist_btn.config(text="")

    def _sc_refresh_view(self):
        tok = self.sc_api.oauth_token
        cid = bool(self.sc_api.client_id)
        if tok:
            dot_col, status = C["white"], "AUTH"
        elif cid:
            dot_col, status = C["white3"], "PUBLIC"
        else:
            dot_col, status = C["white3"], "CONNECTING..."
        self._sc_status_dot.config(fg=dot_col)
        self.sc_status_lbl.config(text=status, fg=dot_col)
        if self._sc_view == "search":
            # Restore cached search results — don't re-search
            cached = getattr(self, "_sc_search_tracks", [])
            label  = getattr(self, "_sc_search_label", "Search for tracks above")
            self._sc_tracks = list(cached)
            if cached:
                self._sc_show_tracks(cached, label)
            else:
                self._sc_tracks = []
                self._sc_card_list.set_tracks([])
                self.sc_content_lbl.config(text="Search for tracks above")
        elif self._sc_view == "likes":
            cached = getattr(self, "_sc_likes_tracks", [])
            label  = getattr(self, "_sc_likes_label", "YOUR LIKES")
            if cached:
                # Restore without re-fetching
                self._sc_tracks = list(cached)
                self._sc_show_tracks(cached, label)
            else:
                self._sc_load_likes()
        elif self._sc_view == "favorites":
            self._sc_nav_favorites()

    def _sc_do_search(self):
        q = self.sc_search_var.get().strip()
        if not q:
            return
        self._sc_last_query = q
        self._sc_search_offset = 0
        self._sc_can_load_more = False
        self.sc_content_lbl.config(text=f'Searching "{q}"…')
        self._sc_card_list.set_tracks([])
        self._sc_tracks = []

        def _fetch():
            if not self.sc_api.client_id:
                self.root.after(0, lambda: self.sc_content_lbl.config(text="Fetching SoundCloud credentials…"))
                self.sc_api.refresh_client_id()
                if not self.sc_api.client_id:
                    self.root.after(0, lambda: self.sc_content_lbl.config(text="Could not connect to SoundCloud."))
                    return
            tracks = self.sc_api.search(q, limit=40)
            self._sc_tracks = tracks
            self._sc_search_tracks = list(tracks)
            self._sc_search_label = f'RESULTS FOR "{q.upper()}"'
            self._sc_search_offset = len(tracks)
            more = len(tracks) >= 40
            def _show():
                self._sc_show_tracks(tracks, f'RESULTS FOR "{q.upper()}"')
                if more:
                    self._sc_append_load_more()
            self.root.after(0, _show)

        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_append_load_more(self):
        """Signal that more results can be loaded."""
        self._sc_can_load_more = True
        self.sc_content_lbl.config(
            text=self.sc_content_lbl.cget("text").split("  ·")[0]
            + f"  ·  [ LOAD MORE ]"
        )

    def _sc_load_more(self):
        if not self._sc_last_query or not self._sc_can_load_more:
            return
        self._sc_can_load_more = False
        self.sc_content_lbl.config(text="Loading more…")
        q = self._sc_last_query
        offset = self._sc_search_offset

        def _fetch():
            tracks = self.sc_api.search(q + f" offset={offset}", limit=40)
            if not tracks:
                tracks = self.sc_api._get(
                    "/search/tracks",
                    {"q": q, "limit": 40, "offset": offset}
                )
                tracks = (tracks or {}).get("collection", [])
            new_tracks = [t for t in tracks if t.get("id") not in
                          {x.get("id") for x in self._sc_tracks}]
            self._sc_tracks.extend(new_tracks)
            self._sc_search_tracks = list(self._sc_tracks)
            self._sc_search_offset += len(new_tracks)
            more = len(new_tracks) >= 40

            def _show():
                label = f'RESULTS FOR "{q.upper()}"'
                self._sc_search_label = label
                self._sc_show_tracks(self._sc_tracks, label)
                if more:
                    self._sc_append_load_more()
                else:
                    self.sc_content_lbl.config(text=label + "  ·  end of results")

            self.root.after(0, _show)

        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_load_likes(self):
        if not self.sc_api.oauth_token:
            self._sc_tracks = []
            self._sc_card_list.set_tracks([])
            self.sc_content_lbl.config(text="YOUR LIKES  —  OAuth token required")
            self.sc_np_lbl.config(
                text="  ⚠  Paste your token: click [ TOKEN ] top-right → "
                     "DevTools → Application → Cookies → oauth_token"
            )
            return
        self.sc_content_lbl.config(text="YOUR LIKES")
        self.sc_np_lbl.config(text="  Loading likes…")
        self._sc_tracks = []

        def _fetch():
            tracks = self.sc_api.likes(limit=100)
            self._sc_tracks = tracks
            self._sc_likes_tracks = list(tracks)
            self._sc_likes_label = "YOUR LIKES"
            self.root.after(0, lambda: self._sc_show_tracks(tracks, "YOUR LIKES"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_queue_track(self, track):
        self._sc_stream_queue.append(track)
        self._sc_update_queue_lbl()
        self.sc_np_lbl.config(text=f"  ⊕ Queued: {track.get('title','')[:40]}")

    def _sc_rclick_from_card(self, track, x, y):
        try:
            self._sc_rclick_track = track
            fav_ids = {t.get("id") for t in self._sc_favorites}
            already_fav = track.get("id") in fav_ids
            self._sc_ctx.entryconfig("♥  Add to Favorites",      state="disabled" if already_fav else "normal")
            self._sc_ctx.entryconfig("✕  Remove from Favorites", state="normal" if already_fav else "disabled")
            self._sc_ctx.tk_popup(x, y)
        except Exception:
            pass

    def _sc_show_tracks(self, tracks, label=""):
        self._sc_hover_idx = -1
        self._sc_detail_close()
        playing_id = (getattr(self, "_sc_current_track", None) or {}).get("id")
        self._sc_card_list.set_tracks(tracks, playing_id=playing_id)
        if label:
            self.sc_content_lbl.config(text=label, fg=C["white2"])
            self.sc_frame.after(80, lambda: self.sc_content_lbl.config(fg=C["white3"]))


    def _sc_update_queue_lbl(self):
        n = len(self._sc_stream_queue)
        if n:
            self.sc_queue_lbl.config(text=f"{n} queued", fg=C["white2"])
        else:
            self.sc_queue_lbl.config(text="")

    def _sc_clear_queue(self):
        self._sc_stream_queue.clear()
        self._sc_update_queue_lbl()
        self.sc_np_lbl.config(text="  Queue cleared.")
        # Redraw list to remove ⊕ markers
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))

    def _sc_nav_favorites(self):
        self._sc_tracks = list(self._sc_favorites)
        self._sc_show_tracks(self._sc_tracks, f"FAVORITES  ({len(self._sc_favorites)})")

    def _sc_right_click(self, event):
        # For canvas-based list, right-click is routed via on_detail callback
        # This method kept as no-op for compat
        pass

    def _sc_ctx_play(self):
        track = getattr(self, "_sc_rclick_track", None)
        if not track:
            return
        threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_ctx_queue(self):
        track = getattr(self, "_sc_rclick_track", None)
        if not track:
            return
        if track.get("id") not in {t.get("id") for t in self._sc_stream_queue}:
            self._sc_stream_queue.append(track)
            self._sc_update_queue_lbl()
            self.sc_np_lbl.config(text=f"  ⊕ Queued: {(track.get('title') or '')[:40]}")
            self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        else:
            self.sc_np_lbl.config(text="  Already in queue.")

    def _sc_ctx_favorite(self):
        track = getattr(self, "_sc_rclick_track", None)
        if not track:
            return
        fav_ids = {t.get("id") for t in self._sc_favorites}
        if track.get("id") not in fav_ids:
            self._sc_favorites.append(track)
            self._save()
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        self.sc_np_lbl.config(text=f"  ♥  Added: {(track.get('title') or '')[:40]}")

    def _sc_ctx_unfavorite(self):
        track = getattr(self, "_sc_rclick_track", None)
        if not track:
            return
        self._sc_favorites = [t for t in self._sc_favorites if t.get("id") != track.get("id")]
        self._save()
        if self._sc_view == "favorites":
            self._sc_tracks = list(self._sc_favorites)
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        self.sc_np_lbl.config(text=f"  Removed: {(track.get('title') or '')[:40]}")

    def _sc_kb_delete(self):
        track = getattr(self, "_sc_rclick_track", None)
        if not track or not self._sc_tracks:
            return
        if self._sc_view == "favorites":
            self._sc_ctx_unfavorite()
        else:
            tid = track.get("id")
            if tid in {t.get("id") for t in self._sc_stream_queue}:
                self._sc_stream_queue = [t for t in self._sc_stream_queue if t.get("id") != tid]
                self._sc_update_queue_lbl()
                self.sc_np_lbl.config(text=f"  Removed from queue: {(track.get('title') or '')[:40]}")
                self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))

    def _sc_skip(self, direction):
        """Skip forward (+1) or backward (-1) through _sc_tracks. Called by _next/_prev."""
        tracks = self._sc_tracks
        if not tracks:
            return
        current = getattr(self, "_sc_current_track", None)
        current_id = current.get("id") if current else None
        current_idx = next(
            (i for i, t in enumerate(tracks) if t.get("id") == current_id), -1
        )
        if direction == -1:
            # Prev: if more than 3s in, restart current track instead
            if self.engine.get_position() > 3 and current_idx >= 0:
                self.engine.seek(0)
                return
            next_idx = max(0, current_idx - 1)
        else:
            if self.shuffle and len(tracks) > 1:
                import random
                candidates = [i for i in range(len(tracks)) if i != current_idx]
                next_idx = random.choice(candidates)
            else:
                next_idx = current_idx + 1
                if next_idx >= len(tracks):
                    if self.repeat_mode == "all":
                        next_idx = 0
                    else:
                        return
        track = tracks[next_idx]
        threading.Thread(target=lambda t=track: self._sc_stream(t), daemon=True).start()
        try:
            self._sc_card_list.set_playing(track.get("id"))
        except Exception:
            pass

    def _sc_autoplay_next(self):
        """
        Called by _watch_end when a SoundCloud track finishes.
        Priority: manual queue → shuffle → next in list → repeat-all wraps → stop.
        Guard flag prevents double-firing from concurrent watchers.
        """
        # Guard: only fire once per track completion
        fired_token = getattr(self, "_sc_autoplay_fired_token", -1)
        current_token = getattr(self, "_sc_stream_token", 0)
        if fired_token == current_token:
            return
        self._sc_autoplay_fired_token = current_token

        # 0. Repeat one — replay the same track
        if self.repeat_mode == "one":
            t = getattr(self, "_sc_current_track", None)
            if t:
                threading.Thread(target=lambda: self._sc_stream(t), daemon=True).start()
            return

        # 1. Manual queue always wins
        if self._sc_stream_queue:
            next_track = self._sc_stream_queue.pop(0)
            self._sc_update_queue_lbl()
            # Refresh list to remove ⊕ marker
            self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            return

        # 2. No list to advance through
        tracks = self._sc_tracks
        if not tracks:
            self._active_source = "none"
            self._set_source_badge("none")
            return

        current = getattr(self, "_sc_current_track", None)
        current_id = current.get("id") if current else None

        # Find current position in the visible list
        current_idx = next(
            (i for i, t in enumerate(tracks) if t.get("id") == current_id), -1
        )

        # 3. Shuffle — pick a random track that isn't the current one
        if self.shuffle and len(tracks) > 1:
            import random
            candidates = [i for i in range(len(tracks)) if i != current_idx]
            next_idx = random.choice(candidates)
            next_track = tracks[next_idx]
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            return

        # 4. Advance to next track in list
        next_idx = current_idx + 1

        if next_idx < len(tracks):
            next_track = tracks[next_idx]
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            try:
                self._sc_card_list.set_playing(next_track.get("id"))
            except Exception:
                pass
            return

        # 5. End of list — wrap if repeat all, else stop
        if self.repeat_mode == "all" and tracks:
            next_track = tracks[0]
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            try:
                self._sc_card_list.set_playing(next_track.get("id"))
            except Exception:
                pass
        else:
            self._active_source = "none"
            self._set_source_badge("none")
            self._sc_restore_np_bar()

    def _sc_ctx_save(self):
        """Download current track's temp file into the library Music folder."""
        track = getattr(self, "_sc_rclick_track", None)
        if not track:
            return
        title  = (track.get("title") or "track").replace("/", "-").replace("\\", "-")
        artist = track.get("user", {}).get("username", "Unknown")
        self.sc_np_lbl.config(text="  ⬇ Fetching stream for save…")

        def _do():
            stream_url = self.sc_api.get_stream_url(track)
            if not stream_url:
                self.root.after(0, lambda: self.sc_np_lbl.config(text="  ⬇ Could not get stream URL."))
                return
            # Determine save folder — first watch_dir, or Music, or home
            dirs = self.settings.get("watch_dirs", [])
            save_dir = Path(dirs[0]) if dirs else Path.home() / "Music"
            save_dir.mkdir(parents=True, exist_ok=True)
            dest = save_dir / f"{artist} - {title}.mp3"
            counter = 1
            while dest.exists():
                dest = save_dir / f"{artist} - {title} ({counter}).mp3"
                counter += 1
            try:
                import urllib.request as _ur
                self.root.after(0, lambda: self.sc_np_lbl.config(text=f"  ⬇ Saving to {dest.name}…"))
                _ur.urlretrieve(stream_url, str(dest))
                # Write ID3 tags if mutagen available
                try:
                    from mutagen.id3 import ID3, TIT2, TPE1, TALB
                    tags = ID3()
                    tags["TIT2"] = TIT2(encoding=3, text=title)
                    tags["TPE1"] = TPE1(encoding=3, text=artist)
                    tags["TALB"] = TALB(encoding=3, text="SoundCloud")
                    tags.save(str(dest))
                except Exception:
                    pass
                # Import into library
                self.root.after(0, lambda d=str(dest): (
                    self._import([d]),
                    self.sc_np_lbl.config(text=f"  ✓ Saved & imported: {dest.name}"),
                ))
            except Exception as ex:
                _msg = str(ex)
                self.root.after(0, lambda m=_msg: self.sc_np_lbl.config(text=f"  ⬇ Error: {m}"))

        threading.Thread(target=_do, daemon=True).start()

    def _sc_ctx_open(self):
        track = getattr(self, "_sc_rclick_track", None)
        if not track:
            return
        url = track.get("permalink_url") or track.get("uri") or ""
        if url:
            import webbrowser
            webbrowser.open(url)

    def _sc_np_artist_click(self):
        """Clicking the artist label in the NP bar searches for that artist."""
        track = getattr(self, "_sc_current_track", None)
        if not track:
            return
        artist = track.get("user", {}).get("username", "")
        if not artist:
            return
        self.sc_search_var.set(artist)
        self._sc_nav("search")
        self._sc_do_search()

    def _sc_play_selected(self, event=None):
        # StreamCardList handles play via on_play callback — kept for compat
        pass

    def _sc_stream(self, track):
        """Download stream fully then play — pygame holds a file lock so partial loads fail."""
        self.root.after(0, lambda: self.sc_np_lbl.config(text="  Resolving stream..."))

        stream_url = self.sc_api.get_stream_url(track)

        if not stream_url and not SoundCloudAPI._cached_cid:
            self.root.after(0, lambda: self.sc_np_lbl.config(text="  Refreshing client ID..."))
            if self.sc_api.refresh_client_id():
                stream_url = self.sc_api.get_stream_url(track)

        if not stream_url:
            self.root.after(0, lambda: (
                self.sc_np_lbl.config(text="  — SOUNDCLOUD —"),
                messagebox.showwarning(
                    "OTERNOS // SOUNDCLOUD",
                    "Could not get stream URL.\n\nThe track may not be streamable, or SoundCloud\nhas changed their API. Try again in a moment.",
                ),
            ))
            return

        title  = track.get("title", "Unknown")
        artist = track.get("user", {}).get("username", "Unknown")
        dur_s  = track.get("duration", 0) // 1000

        # Cancellation token — incremented by _stop_all_sources or a new stream call
        self._sc_stream_token = getattr(self, "_sc_stream_token", 0) + 1
        _my_token = self._sc_stream_token

        def _cancelled():
            return getattr(self, "_sc_stream_token", 0) != _my_token

        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            tmp_path = tmp.name

            import urllib.request as _ur

            CHUNK = 256 * 1024

            req = _ur.Request(
                stream_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )

            with _ur.urlopen(req, timeout=20) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                written = 0
                last_pct = -1
                with open(tmp_path, "wb") as fout:
                    while True:
                        if _cancelled():
                            return
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        fout.write(chunk)
                        written += len(chunk)

                        if total > 0:
                            pct = min(99, int(written * 100 / total))
                            if pct >= last_pct + 5:
                                last_pct = pct
                                self.root.after(0, lambda p=pct: self.sc_np_lbl.config(
                                    text=f"  Buffering... {p}%"))
                        else:
                            mb = written / 1048576
                            self.root.after(0, lambda m=mb: self.sc_np_lbl.config(
                                text=f"  Buffering... {m:.1f} MB"))

            if _cancelled():
                return

            self.root.after(0, lambda: self.sc_np_lbl.config(text="  Buffering... 100%"))

            # ── Full file on disk — now safe to load ──────────────────────
            def _play():
                if _cancelled():
                    return
                # _stop_all_sources() will increment _sc_stream_token by 1.
                # Pre-set our token to that future value so _cancelled() stays False.
                self._sc_stream_token = _my_token - 1
                self._stop_all_sources()
                # After _stop_all_sources, token == _my_token. Good.

                self._sc_current_track = track
                self._active_source = "soundcloud"
                self._sp_mode = False
                self._set_source_badge("soundcloud")
                if self.engine.load(tmp_path):
                    self._current_play_path = tmp_path
                    # Set duration BEFORE play() so the async reader doesn't race-overwrite it
                    self.engine.duration = float(dur_s)
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text="SoundCloud")
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=f"{dur_s // 60}:{dur_s % 60:02d}")
                    self._draw_prog(0)
                    self._sc_restore_np_bar()
                    self.sc_np_artist_btn.config(text=f"[ {artist[:20]} ▸ ]")
                    # Refresh list so ► marker moves to the new track
                    if self._sc_tracks:
                        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
                    art_url = track.get("artwork_url") or ""
                    if not art_url:
                        # Fall back to user avatar if track has no artwork
                        art_url = (track.get("user") or {}).get("avatar_url") or ""
                    if art_url:
                        self._set_album_art(art_url.replace("-large", "-t500x500"))
                    else:
                        # No artwork anywhere — clear to placeholder so previous art doesn't linger
                        self._art_url_last = None
                        self._draw_art_placeholder()
                    self._history_add({"title": title, "artist": artist, "album": "SoundCloud"}, source="soundcloud")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp_path: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
                    if getattr(self, "view", "") == "lyrics":
                        self._refresh_lyrics_view()
                    # ── End-of-track watcher ──────────────────────────────
                    _watch_token = _my_token
                    def _watch_end():
                        try:
                            import pygame as _pg
                            import time as _t
                            for _ in range(40):
                                if getattr(self, "_sc_stream_token", 0) != _watch_token:
                                    return
                                if _pg.mixer.music.get_busy():
                                    break
                                _t.sleep(0.1)
                            else:
                                return
                            while True:
                                if getattr(self, "_sc_stream_token", 0) != _watch_token:
                                    return
                                if not _pg.mixer.music.get_busy():
                                    # get_busy() is also False when paused — ignore that
                                    if self.engine.is_paused:
                                        _t.sleep(0.3)
                                        continue
                                    if (getattr(self, "_active_source", "") == "soundcloud"
                                            and getattr(self, "_sc_stream_token", 0) == _watch_token):
                                        self.root.after(0, self._sc_autoplay_next)
                                    return
                                _t.sleep(0.3)
                        except Exception:
                            pass
                    threading.Thread(target=_watch_end, daemon=True).start()
                else:
                    self.sc_np_lbl.config(text="  — load failed —")

            self.root.after(0, _play)

        except Exception as exc:
            err = str(exc)
            self.root.after(0, lambda: (
                self.sc_np_lbl.config(text="  Stream error."),
                messagebox.showwarning("OTERNOS // SOUNDCLOUD", f"Stream error:\n{err}"),
            ))


    # ── HTML Bridge + Webview ─────────────────────────────────────────────────

    def _sc_init_bridge(self):
        """Instantiate and start the SCBridgeServer (once only)."""
        if getattr(self, "_sc_bridge", None):
            return
        try:
            if getattr(sys, "frozen", False):
                from oternos.sc_bridge import SCBridgeServer
            else:
                from ..sc_bridge import SCBridgeServer
            b = SCBridgeServer()
            b.sc_api         = self.sc_api
            b.on_play        = self._sc_bridge_play
            b.on_queue       = self._sc_bridge_queue
            b.on_like_toggle = self._sc_bridge_like
            b.get_state      = self._sc_bridge_state
            ok = b.start()
            self._sc_bridge = b if ok else None
        except Exception as exc:
            self._sc_bridge = None
            print(f"[SC BRIDGE] init failed: {exc}")

    def _sc_bridge_play(self, raw_track: dict):
        """Bridge callback: play a track received from the HTML UI."""
        threading.Thread(target=lambda: self._sc_stream(raw_track), daemon=True).start()

    def _sc_bridge_queue(self, raw_track: dict):
        """Bridge callback: queue a track received from the HTML UI."""
        self.root.after(0, lambda: self._sc_queue_track(raw_track))

    def _sc_bridge_like(self, track_id: int, liked: bool):
        """Bridge callback: toggle favorite from the HTML UI."""
        favs    = getattr(self, "_sc_favorites", [])
        fav_ids = {t.get("id") for t in favs}
        if liked and track_id not in fav_ids:
            track = next((t for t in getattr(self, "_sc_tracks", [])
                          if t.get("id") == track_id), None)
            if track:
                self._sc_favorites.append(track)
                self._save()
        elif not liked and track_id in fav_ids:
            self._sc_favorites = [t for t in favs if t.get("id") != track_id]
            self._save()

    def _sc_bridge_state(self) -> dict:
        """Bridge callback: return current player state for the HTML UI."""
        current   = getattr(self, "_sc_current_track", None)
        tracks    = getattr(self, "_sc_tracks", [])
        favs      = getattr(self, "_sc_favorites", [])
        track_map = {t.get("id"): t for t in tracks}
        for t in favs:
            track_map[t.get("id")] = t
        return {
            "nowPlaying": current.get("id") if current else None,
            "liked_ids":  [t.get("id") for t in favs],
            "track_map":  track_map,
        }

    def _sc_open_html_view(self):
        """Launch the HTML SC UI in a pywebview (or browser) window."""
        proc = getattr(self, "_sc_webview_proc", None)
        if proc and proc.poll() is None:
            return  # already running

        # Ensure bridge is running first
        self._sc_init_bridge()
        if not getattr(self, "_sc_bridge", None):
            import webbrowser
            webbrowser.open("http://127.0.0.1:47472/")
            return

        import time, subprocess, shutil
        time.sleep(0.15)

        # When frozen, sys.executable is the .exe — find a real Python instead
        python_exe = None
        if getattr(sys, "frozen", False):
            # Try common Python launchers in order
            for candidate in ("py", "python", "python3", "python3.12", "python3.11", "python3.10"):
                found = shutil.which(candidate)
                if found:
                    python_exe = found
                    break
        else:
            python_exe = sys.executable

        if not python_exe:
            # No Python found — just open in browser
            import webbrowser
            webbrowser.open("http://127.0.0.1:47472/")
            self.root.after(0, lambda: self._sc_webview_dot.config(text="○", fg=C["white3"]))
            return

        CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            self._sc_webview_proc = subprocess.Popen(
                [python_exe, "-c", _SC_WEBVIEW_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            self.root.after(600, self._sc_poll_webview)
        except Exception as exc:
            print(f"[SC] Failed to launch webview: {exc}")
            import webbrowser
            webbrowser.open("http://127.0.0.1:47472/")
    def _sc_close_html_view(self):
        """Terminate the webview subprocess."""
        proc = getattr(self, "_sc_webview_proc", None)
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        self._sc_webview_proc = None
        try:
            if hasattr(self, "_sc_webview_dot"):
                self._sc_webview_dot.config(text="○", fg=C["white3"])
        except Exception:
            pass

    def _sc_poll_webview(self):
        """Keep the status dot in sync with the subprocess liveness."""
        proc  = getattr(self, "_sc_webview_proc", None)
        alive = proc and proc.poll() is None
        try:
            if hasattr(self, "_sc_webview_dot"):
                self._sc_webview_dot.config(
                    text="●" if alive else "○",
                    fg=C["white"] if alive else C["white3"],
                )
        except Exception:
            pass
        if alive:
            self.root.after(2000, self._sc_poll_webview)
