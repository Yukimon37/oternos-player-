"""
boot.py
─────────────────────────────────────────────────────────────────────────────
OTERNOS PLAYER  —  TronBoot startup sequence + entry-point helpers.
  • _focused_on_entry()  — keyboard focus guard for global shortcuts
  • TronBoot             — fullscreen terminal boot animation
─────────────────────────────────────────────────────────────────────────────
"""

import tkinter as tk
import math
import time
from pathlib import Path

from .constants import C, FM, FML


# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
def _focused_on_entry(root):
    """Return True when a text-input widget has keyboard focus."""
    try:
        return isinstance(root.focus_get(), (tk.Entry, tk.Text))
    except Exception:
        return False

# ─────────────────────────────────────────
#  TRON BOOT SEQUENCE
# ─────────────────────────────────────────
class TronBoot:
    """
    Fullscreen boot sequence synced to boot.mp3 timestamps:
      0:01 — login prompt appears
      0:03 — credentials typed
      0:07 — ACCESS GRANTED flash
      0:08-0:15 — logo fades in, holds, fades out → player launches
    Place boot.mp3 in the same folder as the exe or script.
    """
    CHAR_DELAY = 22   # ms per character
    CURSOR     = "█"

    def __init__(self, root, on_done, track_count=0):
        self.root     = root
        self.on_done  = on_done
        self.n_tracks = track_count
        self._jobs    = []
        self._done    = False

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.sw, self.sh = sw, sh

        # Fullscreen black window
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{sw}x{sh}+0+0")
        self.win.configure(bg="#000000")

        self.cv = tk.Canvas(self.win, bg="#000000", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        # Subtle CRT scanlines
        for yy in range(0, sh, 4):
            self.cv.create_line(0, yy, sw, yy, fill="#060606", width=1)

        # Terminal area — centered
        self.term_x = sw // 2 - 300
        self.term_y = sh // 2 - 120
        self._line_items      = []
        self._cursor_blink_on = True
        self._cursor_item     = self.cv.create_text(
            self.term_x, self.term_y, text=self.CURSOR,
            font=("Courier New", 11), fill="#e8e8e8", anchor="nw")

        # Logo item (hidden until phase 3)
        self._logo_item = self.cv.create_text(
            sw // 2, sh // 2,
            text="O T E R N O S", font=("Courier New", 48, "bold"),
            fill="#000000", anchor="center")
        self._sub_item = self.cv.create_text(
            sw // 2, sh // 2 + 56,
            text="P  L  A  Y  E  R     v 1 . 1",
            font=("Courier New", 14), fill="#000000", anchor="center")

        self._blink()

        # Play audio
        self._play_boot_audio()

        # Schedule all phases synced to audio
        self._schedule()

    # ── audio ──────────────────────────────
    def _play_boot_audio(self):
        try:
            import sys as _sys, os as _os, pygame as _pg
            # Init mixer independently of the main player
            if not _pg.get_init():
                _pg.init()
            if not _pg.mixer.get_init():
                _pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            candidates = []
            if getattr(_sys, "frozen", False):
                candidates.append(_os.path.dirname(_sys.executable))
            try:
                candidates.append(_os.path.dirname(_os.path.abspath(__file__)))
            except Exception:
                pass
            candidates.append(str(Path.home() / "Downloads"))
            candidates.append(str(Path.home() / "Downloads" / "dist"))
            print("[BOOT] searching for boot.mp3 in:", candidates)
            for d in candidates:
                p = _os.path.join(d, "boot.mp3")
                print(f"[BOOT] checking: {p}  exists={_os.path.exists(p)}")
                if _os.path.exists(p):
                    _pg.mixer.music.load(p)
                    _pg.mixer.music.set_volume(1.0)
                    _pg.mixer.music.play()
                    print("[BOOT] playing:", p)
                    return
            print("[BOOT] boot.mp3 not found in any candidate path")
        except Exception as e:
            print(f"[BOOT] audio error: {e}")

    # ── cursor blink ───────────────────────
    def _blink(self):
        if self._done: return
        col = "#e8e8e8" if self._cursor_blink_on else "#000000"
        try: self.cv.itemconfig(self._cursor_item, fill=col)
        except: return
        self._cursor_blink_on = not self._cursor_blink_on
        self._jobs.append(self.root.after(500, self._blink))

    # ── main schedule ──────────────────────
    def _schedule(self):
        # ── Phase 1: 0:01 — login prompt appears ──
        self._at(1000, lambda: self._show_login_prompt())

        # ── Phase 2: 0:03 — type credentials ──
        self._at(3000, lambda: self._type_credentials())

        # ── Phase 3: 0:07 — ACCESS GRANTED flash ──
        self._at(7000, lambda: self._access_granted())

        # ── Phase 4: 0:08 — clear terminal, logo fades in ──
        self._at(8000, lambda: self._show_logo())

        # ── Phase 5: 0:13 — logo fades out ──
        self._at(13000, lambda: self._fade_logo_out())

        # ── Phase 6: 0:15 — launch player ──
        self._at(15000, lambda: self._finish())

    def _at(self, ms, fn):
        self._jobs.append(self.root.after(ms, fn))

    # ── Phase 1: login prompt ──────────────
    def _show_login_prompt(self):
        if self._done: return
        lines = [
            "ENCOM OS 12  //  SECURE TERMINAL",
            "━" * 44,
            "",
            "AUTHENTICATION REQUIRED",
            "",
        ]
        for i, line in enumerate(lines):
            self._at(i * 120, lambda l=line: self._add_line(l, "#888888" if "━" in l else "#c8c8c8"))
        # After lines appear, show login fields
        self._at(len(lines) * 120 + 100, self._show_login_fields)

    def _show_login_fields(self):
        if self._done: return
        self._add_line("  LOGIN    :  _", "#e8e8e8")
        self._add_line("  PASSWORD :  _", "#e8e8e8")

    # ── Phase 2: type credentials ──────────
    def _type_credentials(self):
        if self._done: return
        # Find and update login/password lines
        items = self._line_items
        login_item    = items[-2] if len(items) >= 2 else None
        password_item = items[-1] if len(items) >= 1 else None
        login_text    = "  LOGIN    :  IKARI"
        password_text = "  PASSWORD :  ••••••••••"
        if login_item:
            self._retype(login_item, "  LOGIN    :  ", login_text, 0)
        if password_item:
            self._at(800, lambda: self._retype(password_item,
                "  PASSWORD :  ", password_text, 0))

    def _retype(self, item, prefix, full_text, i):
        if self._done: return
        try: self.cv.itemconfig(item, text=full_text[:len(prefix)+i])
        except: return
        if len(prefix) + i < len(full_text):
            self._jobs.append(self.root.after(self.CHAR_DELAY,
                lambda: self._retype(item, prefix, full_text, i+1)))

    # ── Phase 3: ACCESS GRANTED ────────────
    def _access_granted(self):
        if self._done: return
        self._add_line("", "#000000")
        self._add_line("  ✓  IDENTITY VERIFIED", "#e8e8e8")
        self._add_line("", "#000000")
        ag = self._add_line("  ██  ACCESS GRANTED  ██", "#ffffff",
                            font=("Courier New", 13, "bold"))
        # Flash it
        self._flash_item(ag, 0)

    def _flash_item(self, item, step):
        if self._done or step > 5: return
        col = "#ffffff" if step % 2 == 0 else "#333333"
        try: self.cv.itemconfig(item, fill=col)
        except: return
        self._jobs.append(self.root.after(180, lambda: self._flash_item(item, step+1)))

    # ── Phase 4: show logo ─────────────────
    def _show_logo(self):
        if self._done: return
        # Hide terminal
        for item in self._line_items:
            try: self.cv.itemconfig(item, fill="#000000")
            except: pass
        try: self.cv.itemconfig(self._cursor_item, fill="#000000")
        except: pass
        # Fade logo in
        self._fade_logo_in(0)

    def _fade_logo_in(self, step):
        if self._done: return
        steps = 30
        v = int((step / steps) * 232)
        v2 = int((step / steps) * 100)
        col  = f"#{v:02x}{v:02x}{v:02x}"
        col2 = f"#{v2:02x}{v2:02x}{v2:02x}"
        try:
            self.cv.itemconfig(self._logo_item, fill=col)
            self.cv.itemconfig(self._sub_item,  fill=col2)
        except: return
        if step < steps:
            self._jobs.append(self.root.after(16, lambda: self._fade_logo_in(step+1)))

    # ── Phase 5: fade logo out ─────────────
    def _fade_logo_out(self, step=0):
        if self._done: return
        steps = 30
        v  = int((1 - step/steps) * 232)
        v2 = int((1 - step/steps) * 100)
        col  = f"#{v:02x}{v:02x}{v:02x}"
        col2 = f"#{v2:02x}{v2:02x}{v2:02x}"
        try:
            self.cv.itemconfig(self._logo_item, fill=col)
            self.cv.itemconfig(self._sub_item,  fill=col2)
        except: return
        if step < steps:
            self._jobs.append(self.root.after(16, lambda: self._fade_logo_out(step+1)))

    # ── helpers ────────────────────────────
    def _add_line(self, text, color="#c8c8c8", font=("Courier New", 11)):
        if self._done: return None
        y = self.term_y + len(self._line_items) * 18
        item = self.cv.create_text(self.term_x, y, text=text,
            font=font, fill=color, anchor="nw")
        self._line_items.append(item)
        self.cv.coords(self._cursor_item,
                       self.term_x, self.term_y + len(self._line_items) * 18)
        return item

    # ── finish ─────────────────────────────
    def _finish(self):
        if self._done: return
        self._done = True
        for j in self._jobs:
            try: self.root.after_cancel(j)
            except: pass
        try:
            import pygame as _pg
            _pg.mixer.music.stop()
        except: pass
        try: self.win.destroy()
        except: pass
        self.on_done()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()   # hide main window during boot

    def _launch():
        root.deiconify()
        app = VoidPlayer(root)

        def _guard(fn):
            def _handler(e):
                if not _focused_on_entry(root):
                    fn()
            return _handler

        root.bind("<MouseWheel>", app._route_scroll)
        root.bind("<space>", _guard(app._toggle_play))
        root.bind("<Right>", _guard(app._next))
        root.bind("<Left>",  _guard(app._prev))
        root.bind("<Up>",    _guard(lambda: (app.engine.set_volume(app.engine.volume+0.05), app._upd_vol())))
        root.bind("<Down>",  _guard(lambda: (app.engine.set_volume(app.engine.volume-0.05), app._upd_vol())))
        root.bind("<Control-Right>", _guard(lambda: app._seek_relative(+10)))
        root.bind("<Control-Left>",  _guard(lambda: app._seek_relative(-10)))
        root.bind("<Control-p>",     _guard(app._toggle_play))

    # Count library tracks for the boot display
    _n_tracks = 0
    try:
        import json as _json
        _d = _json.loads(Path.home().joinpath(".voidplayer.json").read_text())
        _n_tracks = len(_d.get("library", []))
    except Exception:
        pass

    TronBoot(root, on_done=_launch, track_count=_n_tracks)
    root.mainloop()
