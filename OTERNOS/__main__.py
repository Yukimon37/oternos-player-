"""
__main__.py — OTERNOS PLAYER
Entry point. Run with: python -m oternos  OR  void_player.exe
"""

import sys

# ── Fix Windows console encoding so emoji in tracebacks don't hard-crash ──────
for _s in (sys.stdout, sys.stderr):
    try:
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# ─────────────────────────────────────────────────────────────────────────────

# ── Boot/init subprocess mode (must be first, before any Tk imports) ─────────
if "--boot-only" in sys.argv or "--init-only" in sys.argv or "--player-only" in sys.argv:
    if getattr(sys, "frozen", False):
        from oternos.boot import run_boot_only_mode
    else:
        from .boot import run_boot_only_mode
    run_boot_only_mode()
    sys.exit(0)
# ───────────────────────────────────────────────────────────────────────────────────
import tkinter as tk
import json
from pathlib import Path

if getattr(sys, "frozen", False):
    from oternos.boot import TronBoot, _focused_on_entry, run_html_boot, run_html_init
    from oternos.player import VoidPlayer
    from oternos.utils import log_exception
else:
    from .boot import TronBoot, _focused_on_entry, run_html_boot, run_html_init
    from .player import VoidPlayer
    from .utils import log_exception


def _apply_dwm_fixes(root, app):
    """
    Safe native-feel window setup:
      - DWM drop shadow
      - Dark mode title bar
      - Rounded corners (Win11)
      - Force taskbar button (overrideredirect removes it)
    """
    try:
        import ctypes
        import ctypes.wintypes as wt

        user32  = ctypes.windll.user32
        dwmapi  = ctypes.windll.dwmapi

        # ── Get the real top-level HWND ──────────────────────────────────
        # winfo_id() is the inner child HWND under overrideredirect.
        # GA_ROOT (2) walks up to the actual top-level window.
        GA_ROOT = 2
        inner = root.winfo_id()
        hwnd  = user32.GetAncestor(inner, GA_ROOT) or inner
        app._hwnd = hwnd

        # ── 1. Drop shadow ───────────────────────────────────────────────
        class MARGINS(ctypes.Structure):
            _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int),
                        ("top",  ctypes.c_int), ("bottom", ctypes.c_int)]
        try:
            dwmapi.DwmExtendFrameIntoClientArea(
                hwnd, ctypes.byref(MARGINS(1, 1, 1, 1)))
        except Exception:
            pass

        # ── 2. Dark mode (DWMWA_USE_IMMERSIVE_DARK_MODE) ────────────────
        for attr_id in (20, 19):
            try:
                dwmapi.DwmSetWindowAttribute(
                    hwnd, attr_id, ctypes.byref(ctypes.c_int(1)), 4)
                break
            except Exception:
                pass

        # ── 3. Rounded corners Win11 (DWMWA_WINDOW_CORNER_PREFERENCE) ───
        try:
            dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
        except Exception:
            pass

        # ── 4. Force taskbar button ──────────────────────────────────────
        # overrideredirect strips WS_EX_APPWINDOW and sets WS_EX_TOOLWINDOW.
        # We flip those flags then do a hide/show cycle so Explorer re-registers
        # the window in the taskbar.
        GWL_EXSTYLE      = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW  = 0x00040000
        SW_HIDE          = 0
        SW_SHOW          = 5
        try:
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            # hide then immediately show — forces Explorer to notice
            user32.ShowWindow(hwnd, SW_HIDE)
            user32.ShowWindow(hwnd, SW_SHOW)
        except Exception:
            pass

        # ── 5. Force frame redraw ────────────────────────────────────────
        SWP_NOMOVE       = 0x0002
        SWP_NOSIZE       = 0x0001
        SWP_NOZORDER     = 0x0004
        SWP_FRAMECHANGED = 0x0020
        try:
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    except Exception as exc:
        try:
            log_exception("dwm_fixes_failed", exc)
        except Exception:
            pass


def _is_headless() -> bool:
    """Return True when no display server is available (e.g. Railway containers)."""
    import os
    # Explicit opt-in/opt-out via environment variable
    headless_env = os.environ.get("OTERNOS_HEADLESS", "").strip().lower()
    if headless_env in {"1", "true", "yes"}:
        return True
    if headless_env in {"0", "false", "no"}:
        return False
    # Railway and most CI/container environments set no DISPLAY / WAYLAND_DISPLAY
    has_display = bool(
        os.environ.get("DISPLAY", "").strip()
        or os.environ.get("WAYLAND_DISPLAY", "").strip()
    )
    if not has_display:
        return True
    return False


def _run_discord_bot_headless() -> None:
    """Run the Discord bot directly, bypassing all Tkinter/GUI code."""
    try:
        if getattr(sys, "frozen", False):
            from oternos.discord_bot import main as discord_main
        else:
            from .discord_bot import main as discord_main
    except ImportError as exc:
        raise SystemExit(
            f"Could not import discord_bot: {exc}\n"
            "Make sure discord.py is installed: pip install discord.py"
        ) from exc
    raise SystemExit(discord_main())


def main():
    if _is_headless():
        _run_discord_bot_headless()
        return

    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.update()

    def _launch(skip_edex=False):
        root.withdraw()
        app = VoidPlayer(root)

        # ── Load all patches ─────────────────────────────────────────────
        try:
            if getattr(sys, "frozen", False):
                from oternos.patches import load_all as _load_patches
            else:
                from .patches import load_all as _load_patches
            _load_patches(app)
        except Exception as _pe:
            try:
                log_exception("patch_loader", _pe)
            except Exception:
                pass
        # ────────────────────────────────────────────────────────────────

        root.update_idletasks()
        root.overrideredirect(True)

        # ── eDEX init sequence ────────────────────────────────────────────
        # Skipped if HTML boot already ran (skip_edex=True)
        _edex_on = app.settings.get("edex_enabled", True) and not skip_edex
        if _edex_on:
            # ── Init overlay FIRST, then reveal player ─────────────────────
            # Run init in a background thread (it's a blocking subprocess).
            # When it finishes, use root.after() to show the player on the
            # main Tkinter thread. This ensures: boot→init→player.
            _track_count = len(getattr(app, "library", []))

            def _show_player():
                try:
                    root.deiconify()
                    root.after(300, lambda: _apply_dwm_fixes(root, app))
                except Exception:
                    pass

            def _init_then_show():
                try:
                    run_html_init(track_count=_track_count)
                except Exception:
                    pass
                root.after(0, _show_player)

            import threading as _it
            _it.Thread(target=_init_then_show, daemon=True).start()
        else:
            try:
                import tkinter as _tk
                from oternos.utils import C as _C

                _overlay = _tk.Frame(root, bg=_C["bg"])
                _overlay.place(x=0, y=0, relwidth=1.0, relheight=1.0)
                _cv = _tk.Canvas(_overlay, bg=_C["bg"], highlightthickness=0)
                _cv.place(x=0, y=0, relwidth=1.0, relheight=1.0)
                _lines = []

                # ── Blip sound setup ──────────────────────────────────────
                _blip_sounds = []
                try:
                    import pygame as _pg
                    import os as _os
                    import random as _random
                    _blip_dirs = [
                        _os.path.join(_os.path.dirname(__file__), "blips"),
                        _os.path.join(getattr(sys, "_MEIPASS", ""), "oternos", "blips"),
                        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "blips"),
                    ]
                    for _bd in _blip_dirs:
                        if _os.path.isdir(_bd):
                            if not _pg.mixer.get_init():
                                _pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=256)
                            for _i in range(5):
                                _fp = _os.path.join(_bd, f"blip_{_i}.wav")
                                if _os.path.exists(_fp):
                                    _s = _pg.mixer.Sound(_fp)
                                    _s.set_volume(0.3)
                                    _blip_sounds.append(_s)
                            break
                except Exception:
                    pass

                def _blip():
                    try:
                        if _blip_sounds:
                            _random.choice(_blip_sounds).play()
                    except Exception:
                        pass

                def _redraw():
                    try:
                        _cv.delete("all")
                        W = root.winfo_width() or 900
                        H = root.winfo_height() or 600
                        cx, cy = W // 2, H // 2 - 20
                        bw = min(600, W - 80)
                        bh = 240
                        bx = cx - bw // 2
                        by = cy - bh // 2
                        _cv.create_rectangle(bx, by, bx + bw, by + bh, outline="#1e1e1e", width=1, fill=_C["bg"])
                        _cv.create_rectangle(bx + 2, by + 2, bx + bw - 2, by + bh - 2, outline="#141414", width=1)
                        _cv.create_rectangle(bx, by, bx + bw, by + 26, fill="#0c0c0c", outline="")
                        _cv.create_text(bx + 12, by + 13, text="OTERNOS // SYSTEM INITIALIZATION",
                                        font=("Courier New", 8, "bold"), fill="#888888", anchor="w")
                        for dx, dy in [(6, 6), (bw - 6, 6), (6, bh - 6), (bw - 6, bh - 6)]:
                            _cv.create_rectangle(bx + dx - 1, by + dy - 1, bx + dx + 1, by + dy + 1,
                                                 fill="#1a1a1a", outline="")
                        _cv.create_line(bx, by + 27, bx + bw, by + 27, fill="#161616", width=1)
                        y = by + 42
                        for text, color in _lines[-7:]:
                            _cv.create_text(bx + 18, y, text=text, font=("Courier New", 8), fill=color, anchor="w")
                            y += 22
                        import time as _t
                        if int(_t.monotonic() * 2) % 2 == 0:
                            _cv.create_text(bx + 18, y, text="_", font=("Courier New", 8), fill="#ffffff", anchor="w")
                        _cv.create_line(bx, by + bh - 24, bx + bw, by + bh - 24, fill="#0f0f0f", width=1)
                        _cv.create_text(cx, by + bh - 12,
                                        text=f"VOID PLAYER v1.1  ·  {len(getattr(app, 'library', []))} TRACKS  ·  INITIALIZING",
                                        font=("Courier New", 6), fill="#666666", anchor="center")
                    except Exception:
                        pass

                def _blink():
                    if _overlay.winfo_exists():
                        _redraw()
                        root.after(500, _blink)

                def _add(text, color="#cccccc", delay=55):
                    _lines.append(("", color))
                    idx = len(_lines) - 1
                    def _type(i=0):
                        if not _overlay.winfo_exists():
                            return
                        if i < len(text):
                            _lines[idx] = (text[:i + 1], color)
                            if text[i] != " ":
                                _blip()
                            _redraw()
                            root.after(delay, lambda: _type(i + 1))
                    _type()

                def _ok():
                    if _lines:
                        t, _ = _lines[-1]
                        if not t.endswith("[ OK ]"):
                            _lines[-1] = (t + "  [ OK ]", "#ffffff")
                    _redraw()

                def _slideup(offset=0):
                    if not _overlay.winfo_exists():
                        return
                    if offset >= 20:
                        try:
                            _overlay.destroy()
                        except Exception:
                            pass
                        try:
                            app._status_matrix.push("OTERNOS ONLINE")
                        except Exception:
                            pass
                        root.deiconify()
                        root.after(300, lambda: _apply_dwm_fixes(root, app))
                        return
                    t = offset / 20
                    ease = t * t * (3 - 2 * t)
                    try:
                        _overlay.place(x=0, y=int(-(root.winfo_height() * ease)), relwidth=1.0, relheight=1.0)
                    except Exception:
                        pass
                    root.after(16, lambda: _slideup(offset + 1))

                root.update_idletasks()
                root.update()

                root.after(100, _blink)
                _seq = [
                    (0,     lambda: _add("> BOOT SEQUENCE STARTED", "#ffffff")),
                    (1565,  lambda: _ok()),
                    (1865,  lambda: _add("> INITIALIZING AUDIO ENGINE...")),
                    (3815,  lambda: _ok()),
                    (4115,  lambda: _add("> SCANNING LIBRARY INDEX...")),
                    (5900,  lambda: _ok()),
                    (6200,  lambda: _add("> MOUNTING UI SUBSYSTEMS...")),
                    (7985,  lambda: _ok()),
                    (8285,  lambda: _add("> ESTABLISHING VISUALIZER...")),
                    (10125, lambda: _ok()),
                    (10425, lambda: _add("> LOADING PATCH MODULES...")),
                    (12155, lambda: _add("> ALL SYSTEMS NOMINAL", "#ffffff")),
                    (13610, lambda: _add("> LAUNCHING INTERFACE...", "#ffffff")),
                    (15530, lambda: _slideup()),
                ]
                for _d, _f in _seq:
                    root.after(_d, _f)

            except Exception:
                root.deiconify()
                root.after(300, lambda: _apply_dwm_fixes(root, app))
                root.update()
        # ────────────────────────────────────────────────────────────────

        root.bind("<MouseWheel>", app._route_scroll)

    _n_tracks = 0
    _boot_fs = True
    _boot_enabled = True
    try:
        _d = json.loads(Path.home().joinpath(".voidplayer.json").read_text())
        _n_tracks = len(_d.get("library", []))
        _boot_fs = _d.get("settings", {}).get("boot_fullscreen", True)
        _boot_enabled = _d.get("settings", {}).get("boot_enabled", True)
    except Exception:
        pass

    if _boot_enabled:
        # ── Try HTML boot in a background thread (non-blocking for Tk mainloop) ──
        def _try_html_boot():
            ok = run_html_boot(
                on_done=lambda: root.after(0, lambda: _launch(skip_edex=True)),
                track_count=_n_tracks,
                fullscreen=_boot_fs,
            )
            if not ok:
                # HTML boot unavailable — fall back to tkinter TronBoot
                root.after(0, lambda: TronBoot(
                    root, on_done=_launch,
                    track_count=_n_tracks, fullscreen=_boot_fs
                ))
        import threading as _threading
        _threading.Thread(target=_try_html_boot, daemon=True).start()
    else:
        root.after(0, _launch)
    root.mainloop()


if __name__ == "__main__":
    main()
