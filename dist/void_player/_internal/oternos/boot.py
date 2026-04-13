"""
boot/tron.py — OTERNOS PLAYER
TronBoot startup sequence and _focused_on_entry helper.
Cyberpunk / Military / Minimal hybrid boot with:
  - Animated particle grid
  - Fake system diagnostics (CPU, RAM, NET)
  - Animated loading bars
  - Track library stats
  - Glitch flicker effects
  - Login sequence → ACCESS GRANTED → logo fade

Moved from boot.py → boot/tron.py (no logic changes).
"""

import sys
import tkinter as tk
import random
from pathlib import Path

from .html_boot import run_boot_only_mode, run_html_boot, run_html_init

if getattr(sys, "frozen", False):
    pass
else:
    pass


def _focused_on_entry(root):
    try:
        return isinstance(root.focus_get(), (tk.Entry, tk.Text))
    except Exception:
        return False


class TronBoot:
    CHAR_DELAY = 18
    CURSOR = "█"

    def __init__(self, root, on_done, track_count=0, fullscreen=True):
        self.root = root
        self.on_done = on_done
        self.n_tracks = track_count
        self.fullscreen = fullscreen
        self._jobs = []
        self._done = False

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#000000")
        if fullscreen:
            w, h = sw, sh
        else:
            w, h = min(sw, 900), min(sh, 560)
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.sw, self.sh = w, h

        self.cv = tk.Canvas(self.win, bg="#000000", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        for yy in range(0, h, 3):
            self.cv.create_line(0, yy, w, yy, fill="#050505", width=1)

        # ── Custom title bar (drawn on canvas) ──
        if not fullscreen:
            self.cv.create_rectangle(0, 0, w, 26, fill="#0a0a0a", outline="")
            self.cv.create_line(0, 26, w, 26, fill="#1a1a1a", width=1)
            self.cv.create_text(
                12,
                13,
                text="OTERNOS  //  SECURE BOOT",
                font=("Courier New", 8),
                fill="#444444",
                anchor="w",
            )
            # Close button
            close = self.cv.create_text(
                w - 14,
                13,
                text="✕",
                font=("Courier New", 9),
                fill="#333333",
                anchor="center",
            )
            self.cv.tag_bind(
                close, "<Enter>", lambda e: self.cv.itemconfig(close, fill="#cc2222")
            )
            self.cv.tag_bind(
                close, "<Leave>", lambda e: self.cv.itemconfig(close, fill="#333333")
            )
            self.cv.tag_bind(close, "<Button-1>", lambda e: self._finish())
            # Drag
            self._drag_x = self._drag_y = 0

            def _drag_start(e):
                if e.y < 26:
                    self._drag_x, self._drag_y = e.x, e.y

            def _drag_move(e):
                if e.y < 26 or (hasattr(self, "_drag_x") and self._drag_x):
                    nx = self.win.winfo_x() + e.x - self._drag_x
                    ny = self.win.winfo_y() + e.y - self._drag_y
                    self.win.geometry(f"+{nx}+{ny}")

            def _drag_end(e):
                self._drag_x = self._drag_y = 0

            self.cv.bind("<ButtonPress-1>", _drag_start)
            self.cv.bind("<B1-Motion>", _drag_move)
            self.cv.bind("<ButtonRelease-1>", _drag_end)

        self._draw_corners()
        self._particles = []
        self._init_particles()

        self._status_item = self.cv.create_text(
            w // 2,
            18,
            text="OTERNOS  //  SECURE BOOT  //  v1.1",
            font=("Courier New", 9),
            fill="#2a2a2a",
            anchor="center",
        )
        self.cv.create_line(0, 32, w, 32, fill="#111111", width=1)
        self.cv.create_line(0, h - 28, w, h - 28, fill="#111111", width=1)
        self._bot_item = self.cv.create_text(
            16, h - 14, text="", font=("Courier New", 8), fill="#2a2a2a", anchor="w"
        )

        self._sysinfo_vals = []
        self._sysinfo_x = w - 210
        self._sysinfo_y = 50
        self._init_sysinfo()
        self._init_stats()

        self.term_x = w // 2 - 220
        self.term_y = h // 2 - 130
        self._line_items = []
        self._cursor_blink_on = True
        self._cursor_item = self.cv.create_text(
            self.term_x,
            self.term_y,
            text=self.CURSOR,
            font=("Courier New", 11),
            fill="#e8e8e8",
            anchor="nw",
        )

        self._bar_bg = self._bar_fill = self._bar_pct = None

        self._logo_item = self.cv.create_text(
            w // 2,
            h // 2 - 20,
            text="O T E R N O S",
            font=("Courier New", 52, "bold"),
            fill="#000000",
            anchor="center",
        )
        self._sub_item = self.cv.create_text(
            w // 2,
            h // 2 + 46,
            text="P  L  A  Y  E  R     v 1 . 1",
            font=("Courier New", 13),
            fill="#000000",
            anchor="center",
        )
        self._tag_item = self.cv.create_text(
            w // 2,
            h // 2 + 72,
            text="",
            font=("Courier New", 9),
            fill="#000000",
            anchor="center",
        )

        self._blink()
        self._animate_particles()
        self._animate_sysinfo()
        self._animate_status_bar()
        self._play_boot_audio()
        self._schedule()

    def _draw_corners(self):
        w, h, cv = self.sw, self.sh, self.cv
        s, col = 32, "#1c1c1c"
        for x, y, dx, dy in [
            (0, 0, 1, 1),
            (w, 0, -1, 1),
            (0, h, 1, -1),
            (w, h, -1, -1),
        ]:
            cv.create_line(x, y, x + dx * s, y, fill=col, width=1)
            cv.create_line(x, y, x, y + dy * s, fill=col, width=1)

    def _init_particles(self):
        w, h = self.sw, self.sh
        for _ in range(60):
            x = random.randint(0, w)
            y = random.randint(40, h - 40)
            speed = random.uniform(0.15, 0.7)
            b = random.randint(10, 28)
            col = f"#{b:02x}{b:02x}{b:02x}"
            item = self.cv.create_oval(x - 1, y - 1, x + 1, y + 1, fill=col, outline="")
            self._particles.append(
                {
                    "item": item,
                    "x": float(x),
                    "y": float(y),
                    "vx": random.uniform(-0.2, 0.2),
                    "vy": speed,
                }
            )

    def _animate_particles(self):
        if self._done:
            return
        w, h = self.sw, self.sh
        for p in self._particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["y"] > h - 40:
                p["y"] = 40.0
            if p["x"] < 0:
                p["x"] = float(w)
            if p["x"] > w:
                p["x"] = 0.0
            x, y = p["x"], p["y"]
            try:
                self.cv.coords(p["item"], x - 1, y - 1, x + 1, y + 1)
            except Exception:
                pass
        self._jobs.append(self.root.after(38, self._animate_particles))

    def _init_sysinfo(self):
        x, y = self._sysinfo_x, self._sysinfo_y
        self.cv.create_text(
            x,
            y,
            text="[ SYSTEM DIAGNOSTICS ]",
            font=("Courier New", 8, "bold"),
            fill="#1e1e1e",
            anchor="nw",
        )
        self.cv.create_line(x, y + 14, x + 195, y + 14, fill="#111111", width=1)
        labels = [
            "CPU LOAD",
            "RAM USAGE",
            "NET I/O",
            "DISK R/W",
            "AUDIO DRV",
            "BUILD",
            "SECURITY",
        ]
        for i, lbl in enumerate(labels):
            yy = y + 22 + i * 17
            self.cv.create_text(
                x,
                yy,
                text=f"{lbl:<10}",
                font=("Courier New", 8),
                fill="#1c1c1c",
                anchor="nw",
            )
            val = self.cv.create_text(
                x + 105,
                yy,
                text="···",
                font=("Courier New", 8),
                fill="#1c1c1c",
                anchor="nw",
            )
            self._sysinfo_vals.append(val)

    def _animate_sysinfo(self):
        if self._done:
            return
        readouts = [
            f"{random.randint(1, 16)}%",
            f"{random.randint(38, 58)}%",
            f"{random.randint(0, 8)}.{random.randint(0, 9)} MB/s",
            f"{random.randint(1, 6)}%",
            "PYGAME  OK",
            "1.1.0",
            "AES-256  OK",
        ]
        for item, val in zip(self._sysinfo_vals, readouts):
            try:
                self.cv.itemconfig(item, text=val)
            except Exception:
                pass
        self._jobs.append(self.root.after(850, self._animate_sysinfo))

    def _init_stats(self):
        x, y = 16, 50
        self.cv.create_text(
            x,
            y,
            text="[ LIBRARY STATUS ]",
            font=("Courier New", 8, "bold"),
            fill="#1e1e1e",
            anchor="nw",
        )
        self.cv.create_line(x, y + 14, x + 150, y + 14, fill="#111111", width=1)
        rows = [
            ("TRACKS", str(self.n_tracks) if self.n_tracks else "EMPTY"),
            ("ENGINE", "PYGAME"),
            ("EQ", "BIQUAD IIR"),
            ("XFADE", "ENABLED"),
            ("HOTKEYS", "ACTIVE"),
            ("DISCORD", "STANDBY"),
        ]
        for i, (lbl, val) in enumerate(rows):
            yy = y + 22 + i * 17
            self.cv.create_text(
                x,
                yy,
                text=f"{lbl:<9}",
                font=("Courier New", 8),
                fill="#1a1a1a",
                anchor="nw",
            )
            self.cv.create_text(
                x + 76,
                yy,
                text=val,
                font=("Courier New", 8),
                fill="#1a1a1a",
                anchor="nw",
            )

    _STATUS_MSGS = [
        "INITIALIZING AUDIO SUBSYSTEM...",
        "LOADING TRACK METADATA...",
        "CONNECTING DISCORD RPC...",
        "VERIFYING SECURE CHANNEL...",
        "MOUNTING LIBRARY INDEX...",
        "CALIBRATING EQ FILTERS...",
        "ESTABLISHING LAST.FM LINK...",
        "STREAMING APIS ONLINE...",
        "READY.",
    ]
    _status_idx = 0

    def _animate_status_bar(self):
        if self._done:
            return
        msg = self._STATUS_MSGS[self._status_idx % len(self._STATUS_MSGS)]
        self._status_idx += 1
        try:
            self.cv.itemconfig(self._bot_item, text=f"//  {msg}")
        except Exception:
            pass
        self._jobs.append(self.root.after(1500, self._animate_status_bar))

    def _show_loading_bar(self, label="AUTHENTICATING"):
        if self._done:
            return
        self._add_line("")
        self._add_line(f"  {label}", "#444444")
        bar_y = self.term_y + len(self._line_items) * 18 + 4
        bw = 280
        self._bar_bg = self.cv.create_rectangle(
            self.term_x,
            bar_y,
            self.term_x + bw,
            bar_y + 7,
            outline="#1a1a1a",
            fill="#0a0a0a",
        )
        self._bar_fill = self.cv.create_rectangle(
            self.term_x, bar_y, self.term_x, bar_y + 7, outline="", fill="#252525"
        )
        self._bar_pct = self.cv.create_text(
            self.term_x + bw + 10,
            bar_y,
            text="0%",
            font=("Courier New", 8),
            fill="#333333",
            anchor="nw",
        )
        self._animate_bar(0, bw, bar_y)

    def _animate_bar(self, pct, bw, bar_y):
        if self._done:
            return
        pct = min(pct + random.randint(2, 8), 100)
        fw = int(bw * pct / 100)
        b = 18 + int(pct * 0.28)
        col = f"#{b:02x}{b:02x}{b:02x}"
        try:
            self.cv.coords(
                self._bar_fill, self.term_x, bar_y, self.term_x + fw, bar_y + 7
            )
            self.cv.itemconfig(self._bar_fill, fill=col)
            self.cv.itemconfig(self._bar_pct, text=f"{pct}%")
        except Exception:
            return
        if pct < 100:
            self._jobs.append(
                self.root.after(
                    random.randint(28, 75), lambda: self._animate_bar(pct, bw, bar_y)
                )
            )

    def _play_boot_audio(self):
        try:
            import os as _os
            import pygame as _pg

            if not _pg.get_init():
                _pg.init()
            if not _pg.mixer.get_init():
                _pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            candidates = []
            if getattr(sys, "frozen", False):
                candidates.append(_os.path.dirname(sys.executable))
            try:
                candidates.append(_os.path.dirname(_os.path.abspath(__file__)))
            except Exception:
                pass
            candidates.append(str(Path.home() / "Downloads"))
            candidates.append(str(Path.home() / "Downloads" / "dist"))
            for d in candidates:
                p = _os.path.join(d, "boot.mp3")
                if _os.path.exists(p):
                    _pg.mixer.music.load(p)
                    _pg.mixer.music.set_volume(1.0)
                    _pg.mixer.music.play()
                    return
        except Exception as e:
            print(f"[BOOT] audio error: {e}")

    def _blink(self):
        if self._done:
            return
        col = "#e8e8e8" if self._cursor_blink_on else "#000000"
        try:
            self.cv.itemconfig(self._cursor_item, fill=col)
        except Exception:
            return
        self._cursor_blink_on = not self._cursor_blink_on
        self._jobs.append(self.root.after(500, self._blink))

    def _schedule(self):
        self._at(
            500, lambda: self._fade_item(self._status_item, "#2a2a2a", "#484848", 900)
        )
        self._at(1000, self._show_login_prompt)
        self._at(3000, self._type_credentials)
        self._at(3300, lambda: self._show_loading_bar("VERIFYING CREDENTIALS"))
        self._at(7000, self._access_granted)
        self._at(7900, self._show_system_init)
        self._at(9200, self._show_logo)
        self._at(13500, self._fade_logo_out)
        self._at(15000, self._finish)

    def _at(self, ms, fn):
        self._jobs.append(self.root.after(ms, fn))

    def _show_login_prompt(self):
        if self._done:
            return
        lines = [
            ("ENCOM OS  //  OTERNOS SECURE NODE  //  BUILD 1.1", "#3a3a3a"),
            ("━" * 52, "#1e1e1e"),
            ("", None),
            ("  AUTHENTICATION REQUIRED", "#888888"),
            ("  NODE: OTERNOS-PRIMARY  //  UPLINK: ACTIVE", "#2e2e2e"),
            ("", None),
        ]
        for i, (line, col) in enumerate(lines):
            self._at(i * 100, lambda l=line, c=col: self._add_line(l, c or "#000000"))
        self._at(len(lines) * 100 + 80, self._show_login_fields)

    def _show_login_fields(self):
        if self._done:
            return
        self._add_line("  LOGIN    :  _", "#c8c8c8")
        self._add_line("  PASSWORD :  _", "#c8c8c8")

    def _type_credentials(self):
        if self._done:
            return
        import os as _os

        items = self._line_items
        li = items[-2] if len(items) >= 2 else None
        pi = items[-1] if len(items) >= 1 else None
        uname = _os.environ.get("USERNAME", _os.environ.get("USER", "USER")).upper()
        if li:
            self._retype(li, "  LOGIN    :  ", f"  LOGIN    :  {uname}", 0)
        if pi:
            self._at(
                750,
                lambda: self._retype(
                    pi, "  PASSWORD :  ", "  PASSWORD :  ••••••••••", 0
                ),
            )

    def _retype(self, item, prefix, full, i):
        if self._done:
            return
        try:
            self.cv.itemconfig(item, text=full[: len(prefix) + i])
        except Exception:
            return
        if len(prefix) + i < len(full):
            self._jobs.append(
                self.root.after(
                    self.CHAR_DELAY, lambda: self._retype(item, prefix, full, i + 1)
                )
            )

    def _access_granted(self):
        if self._done:
            return
        self._add_line("", "#000000")
        self._add_line("  ✓  IDENTITY VERIFIED      CLEARANCE: LEVEL-5", "#555555")
        self._add_line("", "#000000")
        ag = self._add_line(
            "  ██  ACCESS GRANTED  ██", "#ffffff", font=("Courier New", 13, "bold")
        )
        self._flash_item(ag, 0)

    def _flash_item(self, item, step):
        if self._done or step > 7:
            return
        col = "#ffffff" if step % 2 == 0 else "#1e1e1e"
        try:
            self.cv.itemconfig(item, fill=col)
        except Exception:
            return
        self._jobs.append(
            self.root.after(130, lambda: self._flash_item(item, step + 1))
        )

    def _show_system_init(self):
        if self._done:
            return
        lines = [
            ("", None),
            ("  MOUNTING AUDIO ENGINE       [ PYGAME 2.6 ]", "#2e2e2e"),
            ("  LOADING LIBRARY INDEX       [ OK ]", "#2e2e2e"),
            (f"  TRACKS INDEXED              [ {self.n_tracks} ]", "#383838"),
            ("  DISCORD RPC                 [ STANDBY ]", "#2e2e2e"),
            ("  HOTKEYS                     [ REGISTERED ]", "#2e2e2e"),
        ]
        for i, (line, col) in enumerate(lines):
            self._at(i * 150, lambda l=line, c=col: self._add_line(l, c or "#000000"))

    def _show_logo(self):
        if self._done:
            return
        for item in self._line_items:
            try:
                self.cv.itemconfig(item, fill="#000000")
            except Exception:
                pass
        try:
            self.cv.itemconfig(self._cursor_item, fill="#000000")
        except Exception:
            pass
        for item in [self._bar_bg, self._bar_fill, self._bar_pct]:
            if item:
                try:
                    self.cv.itemconfig(item, fill="#000000", outline="#000000")
                except Exception:
                    pass
        tag = (
            f"{self.n_tracks} TRACKS  //  PYGAME ENGINE  //  v1.1"
            if self.n_tracks
            else "PYGAME ENGINE  //  v1.1"
        )
        try:
            self.cv.itemconfig(self._tag_item, text=tag)
        except Exception:
            pass
        self._fade_logo_in(0)

    def _fade_logo_in(self, step):
        if self._done:
            return
        steps = 35
        t = step / steps
        v = int(t * 228)
        v2 = int(t * 90)
        v3 = int(t * 45)
        col = f"#{v:02x}{v:02x}{min(255, v + 20):02x}"
        col2 = f"#{v2:02x}{v2:02x}{v2:02x}"
        col3 = f"#{v3:02x}{v3:02x}{v3:02x}"
        try:
            self.cv.itemconfig(self._logo_item, fill=col)
            self.cv.itemconfig(self._sub_item, fill=col2)
            self.cv.itemconfig(self._tag_item, fill=col3)
        except Exception:
            return
        if step < steps:
            self._jobs.append(self.root.after(14, lambda: self._fade_logo_in(step + 1)))
        else:
            self._at(800, lambda: self._glitch_logo(4))

    def _glitch_logo(self, n):
        if self._done or n <= 0:
            return
        r = random.randint(200, 255)
        g = random.randint(200, 255)
        b = random.randint(220, 255)
        try:
            self.cv.itemconfig(self._logo_item, fill=f"#{r:02x}{g:02x}{b:02x}")
        except Exception:
            return
        self._jobs.append(self.root.after(55, lambda: self._restore_logo(n)))

    def _restore_logo(self, n):
        if self._done:
            return
        try:
            self.cv.itemconfig(self._logo_item, fill="#e4e4fc")
        except Exception:
            return
        self._jobs.append(self.root.after(110, lambda: self._glitch_logo(n - 1)))

    def _fade_logo_out(self, step=0):
        if self._done:
            return
        steps = 35
        t = 1 - step / steps
        v = int(t * 228)
        v2 = int(t * 90)
        v3 = int(t * 45)
        col = f"#{v:02x}{v:02x}{min(255, v + 20):02x}"
        col2 = f"#{v2:02x}{v2:02x}{v2:02x}"
        col3 = f"#{v3:02x}{v3:02x}{v3:02x}"
        try:
            self.cv.itemconfig(self._logo_item, fill=col)
            self.cv.itemconfig(self._sub_item, fill=col2)
            self.cv.itemconfig(self._tag_item, fill=col3)
        except Exception:
            return
        if step < steps:
            self._jobs.append(
                self.root.after(14, lambda: self._fade_logo_out(step + 1))
            )

    def _add_line(self, text, color="#c8c8c8", font=("Courier New", 11)):
        if self._done:
            return None
        y = self.term_y + len(self._line_items) * 18
        item = self.cv.create_text(
            self.term_x, y, text=text, font=font, fill=color, anchor="nw"
        )
        self._line_items.append(item)
        self.cv.coords(
            self._cursor_item, self.term_x, self.term_y + len(self._line_items) * 18
        )
        return item

    def _fade_item(self, item, from_col, to_col, duration_ms=600):
        steps = 20
        delay = duration_ms // steps

        def _step(i=0):
            if self._done or i > steps:
                return
            t = i / steps
            r1, g1, b1 = (
                int(from_col[1:3], 16),
                int(from_col[3:5], 16),
                int(from_col[5:7], 16),
            )
            r2, g2, b2 = (
                int(to_col[1:3], 16),
                int(to_col[3:5], 16),
                int(to_col[5:7], 16),
            )
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            try:
                self.cv.itemconfig(item, fill=f"#{r:02x}{g:02x}{b:02x}")
            except Exception:
                return
            self._jobs.append(self.root.after(delay, lambda: _step(i + 1)))

        _step()

    def _finish(self):
        if self._done:
            return
        self._done = True
        for j in self._jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        try:
            import pygame as _pg
            _pg.mixer.music.stop()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        self.on_done()
