"""
__main__.py — OTERNOS PLAYER
Entry point. Run with: python -m oternos  OR  void_player.exe
"""

import sys
import tkinter as tk
import json
from pathlib import Path

# When frozen by PyInstaller, sys.frozen is True and relative imports break.
# PyInstaller flattens the package, so top-level imports work there.
# When running via `python -m oternos`, relative imports are required.
if getattr(sys, "frozen", False):
    from oternos.boot import TronBoot, _focused_on_entry
    from oternos.player import VoidPlayer
    from oternos.diagnostics import log_exception
else:
    from .boot import TronBoot, _focused_on_entry
    from .player import VoidPlayer
    from .diagnostics import log_exception


def _apply_dwm_fixes(root, app):
    """
    DWM-only compositing fixes — no SetWindowLong, no second layer.
    DwmExtendFrameIntoClientArea(-1): drop shadow + fixes ghost trails on drag.
    """
    try:
        import ctypes

        hwnd = root.winfo_id()
        dwmapi = ctypes.windll.dwmapi

        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_int),
                ("right", ctypes.c_int),
                ("top", ctypes.c_int),
                ("bottom", ctypes.c_int),
            ]

        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(MARGINS(-1, -1, -1, -1)))

        # Dark mode taskbar thumbnail
        dark = ctypes.c_int(1)
        try:
            dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), 4)
        except Exception:
            pass

        # Windows 11 rounded corners
        try:
            dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
        except Exception:
            pass

        app._hwnd = hwnd
    except Exception as exc:
        try:
            log_exception("dwm_fixes_failed", exc)
        except Exception:
            pass


def main():
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.update()

    def _launch():
        root.withdraw()
        app = VoidPlayer(root)
        root.update_idletasks()
        root.overrideredirect(True)
        root.deiconify()

        # Apply DWM fixes after window is fully visible
        root.after(50, lambda: _apply_dwm_fixes(root, app))

        def _guard(fn):
            def _handler(e):
                if not _focused_on_entry(root):
                    fn()

            return _handler

        root.bind("<MouseWheel>", app._route_scroll)
        # All other hotkeys are registered inside VoidPlayer.__init__
        # with proper entry-focus guards and correct seek vs skip behaviour.

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
        TronBoot(root, on_done=_launch, track_count=_n_tracks, fullscreen=_boot_fs)
    else:
        root.after(0, _launch)
    root.mainloop()


if __name__ == "__main__":
    main()
